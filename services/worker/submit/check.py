"""L-SUBMIT.send/3: "Checked and matched", in the background after Submit (and after a restore).

The final hidden-detail pass runs on what others will read (title, summary, how often), and similar ideas are
matched; whether they could be is kept in `ideas.similar_check` ('failed' reads "Couldn't check for similar ideas.
The review desk will.", never "none found", L-SIMILAR.failure). Then the idea moves `checking → with_review_desk` (E-ENUMS.idea-machine: an automatic move on the
completion of a check, not an agent's verdict, non-negotiable 5) and the sharer is told it reached the review desk
(`L-INBOX.kinds` "Sent to the review desk", through lane A's `notify.post`, inside this transaction).

When the job gives up after its retries, the idea still goes to the desk: a slow matcher never holds an idea back.
"""

from __future__ import annotations

import uuid
from typing import Any

import notify
from core.db import Conn
from core.logging import get_logger
from hide import core as hide_core
from submit import adapters

log = get_logger("submit.check")

PUBLIC_TEXT = ("title", "summary", "often")
COULDNT_CHECK = (
    "Couldn’t check for similar ideas. The review desk will."  # L-SIMILAR.failure, C-DRAFT-LOADER/2
)


def couldnt_check(conn: Conn, idea: dict[str, Any]) -> bool:
    """True when similar ideas could not be checked for this draft or idea (L-SIMILAR.failure): c/similar's latest
    run when its `similar_runs` is here (its retries after sharing write only there), else what the check recorded
    (`ideas.similar_check`), else, for a draft, its similar part having failed (C-DRAFT-LOADER/2)."""
    uid = str(idea["id"])
    here = conn.execute("SELECT to_regclass('public.similar_runs') IS NOT NULL AS here").fetchone()
    if here is not None and here["here"]:
        run = conn.execute("SELECT state FROM similar_runs WHERE idea_uuid = %s", (uid,)).fetchone()
        if run is not None:
            return bool(run["state"] == "failed")
    if idea.get("similar_check") is not None:
        return bool(idea["similar_check"] == "failed")
    if idea.get("status") == "draft":
        part = conn.execute(
            "SELECT state FROM idea_parts WHERE idea_uuid = %s AND key = 'similar'", (uid,)
        ).fetchone()
        return part is not None and part["state"] == "failed"
    return False


def _final_pass(conn: Conn, idea: dict[str, Any], by: str) -> int:
    """Mask anything a customer detail check still finds in the shared text; the count of details hidden now. Hide
    (or the adapter's fallback) stores each value and its `hidden_details` row; this keeps the masked copy only."""
    uid = str(idea["id"])
    changes: dict[str, str] = {}
    hidden = 0
    for column in PUBLIC_TEXT:
        text = idea.get(column)
        if not text:
            continue
        m = adapters.mask_text(conn, uid, str(text), by=by, source_id=None)
        hidden += m.hidden_count
        if m.text != text:
            changes[column] = m.text
    for column, text in changes.items():
        conn.execute(f"UPDATE ideas SET {column} = %s WHERE id = %s", (text, uid))  # noqa: S608 - fixed names
    return hidden


def run(conn: Conn, idea_uuid: str, *, gave_up: bool = False) -> None:
    with conn.transaction():
        # L-HIDE's lock first, then the row (BLD-C067, BLD-C228): the final pass reaches hide (`mask_text`), and lane
        # F's team-up takes hide's lock before the idea's row. Keyed by the lower-case uuid, as hide's own lock is.
        if hide_core.is_uuid(idea_uuid):
            hide_core.lock(conn, str(uuid.UUID(str(idea_uuid))))
        row = conn.execute("SELECT * FROM ideas WHERE id = %s FOR UPDATE", (idea_uuid,)).fetchone()
        if row is None or row["status"] != "checking":
            return  # withdrawn meanwhile, or already with the desk
        idea = dict(row)
        sharer = conn.execute(
            "SELECT user_id FROM contributor_map WHERE contributor_code = %s", (idea["contributor_code"],)
        ).fetchone()
        if sharer is not None:
            hidden = _final_pass(conn, idea, str(sharer["user_id"]))
        else:
            # Hide's `by` is the users.id of whoever typed the words, the one person who may read the values; with
            # no mapping there is nobody to give, so the pass is skipped (the words were masked when written).
            hidden = 0
            log.warning("submit.check_no_sharer", idea_uuid=idea_uuid)
        similar = None if gave_up else adapters.find_similar(conn, idea_uuid, found_while="checking")
        conn.execute(
            "UPDATE ideas SET status = 'with_review_desk', similar_check = %s WHERE id = %s AND status = 'checking'",
            ("failed" if similar is None else "done", idea_uuid),
        )
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
            similar=similar if similar is not None else -1,  # -1: couldn't check, never "none found"
            gave_up=gave_up,
        )
