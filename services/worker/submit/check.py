"""L-SUBMIT.send/3: "Checked and matched", in the background after Submit (and after a restore).

The final hidden-detail pass runs on what others will read (title, summary, how often, the fix), and similar ideas
are matched. Then the idea moves `checking → with_review_desk` (E-ENUMS.idea-machine: an automatic move on the
completion of a check, not an agent's verdict, non-negotiable 5) and the sharer is told it reached the review desk
(`L-INBOX.kinds` "Sent to the review desk", through lane A's `notify.post`, inside this transaction).

When the job gives up after its retries, the idea still goes to the desk: a slow matcher never holds an idea back.
"""

from __future__ import annotations

from typing import Any

import notify
from core.db import Conn
from core.logging import get_logger
from submit import adapters

log = get_logger("submit.check")

PUBLIC_TEXT = ("title", "summary", "often")


def _final_pass(conn: Conn, idea: dict[str, Any]) -> int:
    """Mask anything a customer detail pattern still finds in the shared text; the count of details hidden now."""
    uid = str(idea["id"])
    changes: dict[str, str] = {}
    hidden = 0
    for column in PUBLIC_TEXT:
        text = idea.get(column)
        if not text:
            continue
        m = adapters.mask_text(conn, uid, str(text), source="edit", source_id=f"{uid}:check:{column}")
        if m.found:
            changes[column] = m.text
            hidden += len(m.found)
            for f in m.found:
                conn.execute(
                    "INSERT INTO hidden_details (idea_uuid, source, source_id, span_start, span_end, kind, masked) "
                    "VALUES (%s, 'edit', %s, %s, %s, %s, %s)",
                    (uid, f"{uid}:check:{column}", f["start"], f["end"], f["kind"], f["masked"]),
                )
    for column, text in changes.items():
        conn.execute(f"UPDATE ideas SET {column} = %s WHERE id = %s", (text, uid))  # noqa: S608 - fixed names
    return hidden


def run(conn: Conn, idea_uuid: str, *, gave_up: bool = False) -> None:
    with conn.transaction():
        row = conn.execute("SELECT * FROM ideas WHERE id = %s FOR UPDATE", (idea_uuid,)).fetchone()
        if row is None or row["status"] != "checking":
            return  # withdrawn meanwhile, or already with the desk
        idea = dict(row)
        hidden = _final_pass(conn, idea)
        similar = None if gave_up else adapters.find_similar(conn, idea_uuid, found_while="checking")
        conn.execute(
            "UPDATE ideas SET status = 'with_review_desk' WHERE id = %s AND status = 'checking'", (idea_uuid,)
        )
        sharer = conn.execute(
            "SELECT user_id FROM contributor_map WHERE contributor_code = %s", (idea["contributor_code"],)
        ).fetchone()
        if sharer is not None:
            ref = str(idea["idea_id"])
            notify.post(
                conn,
                "sent_to_desk",
                [str(sharer["user_id"])],
                idea_id=idea_uuid,
                actions=[notify.Action("Open the idea", style="primary", to=f"/ideas/{ref}")],
                refs={"ref": ref},
                dedupe_key=f"sent_to_desk:{idea_uuid}:{(idea['restored_at'] or idea['shared_at']).isoformat()}",
            )
        log.info(
            "submit.checked",
            idea_uuid=idea_uuid,
            hidden=hidden,
            similar=similar if similar is not None else -1,
            gave_up=gave_up,
        )
