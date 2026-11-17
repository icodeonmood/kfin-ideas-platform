"""L-SUBMIT.pre: what must be true before an idea can be sent, and the Send part's last look (S-05 part 7).

1. The draft is ready: a title, a summary and an area (`L-DRAFT.parts/7`; the area is part of the sorting).
2. The sorting is confirmed (`L-SORT.rules/2`).
3. No file is still uploading or being checked. A file in which a customer detail was found can be sent (DEC-107,
   which refines `L-SUBMIT.pre/3`): it opens only for the sharer, the review desk and the Ones Committee.
4. No merge request is waiting on a lead (`L-MERGE.request/4`); a merged draft is not sent at all.
5. The declaration is shown beside the button; pressing Submit is the acceptance (`submit.send` records it).
6. Everything else is optional: proof, a fix, who would help.

The first problem is what Submit says (A-API `POST /drafts/:id/submit` errors), with the field it belongs under.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from core.db import Conn
from submit import check, config, helpers, own, sorting
from submit.errors import Refused
from submit.words import join

TITLE_MAX = 70  # V-FIELDS.checkit/1
WAITING_FILE = ("uploading", "checking")
OLD_WAITING_FILE = ("quarantine", "processing", "awaiting_check")


def title_and_summary(conn: Conn, idea: dict[str, Any]) -> tuple[str, str]:
    """The masked title and summary: the draft's title part (as filled, or as the person changed it), else the
    columns."""
    row = conn.execute(
        "SELECT value FROM idea_parts WHERE idea_uuid = %s AND key = 'title' AND state IN ('filled', 'pinned')",
        (idea["id"],),
    ).fetchone()
    value = row["value"] if row and isinstance(row["value"], dict) else {}
    title = str(value.get("title") or idea.get("title") or "").strip()
    summary = str(value.get("summary") or idea.get("summary") or "").strip()
    return title, summary


def often(conn: Conn, idea: dict[str, Any]) -> str | None:
    row = conn.execute(
        "SELECT value FROM idea_parts WHERE idea_uuid = %s AND key = 'often' AND state IN ('filled', 'pinned')",
        (idea["id"],),
    ).fetchone()
    value = row["value"] if row and isinstance(row["value"], str) else idea.get("often")
    return str(value).strip() or None if value else None


def waiting_files(conn: Conn, idea_uuid: str) -> list[str]:
    rows = conn.execute(
        "SELECT id FROM attachments WHERE idea_uuid = %s AND kind = 'file' AND answer_id IS NULL "
        "AND conversation_entry_id IS NULL AND (file_state = ANY(%s) OR (file_state IS NULL AND state = ANY(%s))) "
        "ORDER BY created_at",
        (idea_uuid, list(WAITING_FILE), list(OLD_WAITING_FILE)),
    ).fetchall()
    return [str(r["id"]) for r in rows]


def _proof(conn: Conn, idea_uuid: str) -> tuple[int, int]:
    row = conn.execute(
        "SELECT count(*) FILTER (WHERE kind IN ('file', 'folder')) AS files, count(*) FILTER (WHERE kind = 'link') "
        "AS links FROM attachments WHERE idea_uuid = %s AND parent_id IS NULL AND answer_id IS NULL "
        "AND conversation_entry_id IS NULL AND coalesce(file_state, '') NOT IN ('upload_failed', 'too_big', "
        "'infected') AND state <> 'rejected'",
        (idea_uuid,),
    ).fetchone()
    return (int(row["files"]), int(row["links"])) if row else (0, 0)


def _count(n: int, one: str) -> str:
    return f"{n} {one}{'s' * (n != 1)}"


def _first_name(conn: Conn, contributor_code: str | None) -> str:
    if not contributor_code:
        return "the lead"
    row = conn.execute(
        "SELECT coalesce(u.first_name, split_part(u.name, ' ', 1)) AS first FROM contributor_map m "
        "JOIN users u ON u.id = m.user_id WHERE m.contributor_code = %s",
        (contributor_code,),
    ).fetchone()
    return str(row["first"]) if row and row["first"] else "the lead"


def waiting_merge(conn: Conn, idea_uuid: str) -> str | None:
    """The lead's first name when a merge request from this draft waits on them (L-MERGE.request/4)."""
    row = conn.execute(
        "SELECT o.contributor_code AS sharer, (SELECT c.contributor_code FROM crew_members c WHERE c.idea_uuid = "
        "o.id AND c.role = 'lead' AND c.left_at IS NULL) AS lead FROM merge_requests r JOIN ideas o ON o.id = "
        "r.other_idea_uuid WHERE r.draft_uuid = %s AND r.state = 'waiting'",
        (idea_uuid,),
    ).fetchone()
    if row is None:
        return None
    return _first_name(conn, row["lead"] or row["sharer"])


def fix_line(conn: Conn, idea_uuid: str) -> str | None:
    row = conn.execute(
        "SELECT how FROM idea_fix WHERE idea_uuid = %s AND included AND coalesce(how, '') <> ''", (idea_uuid,)
    ).fetchone()
    if row is None:
        return None
    how = " ".join(str(row["how"]).split())
    return how if len(how) <= 140 else how[:139].rstrip() + "…"


def problems(conn: Conn, idea: dict[str, Any], li: config.Lists) -> list[Refused]:
    """Everything that stops Submit, in the order Submit names them."""
    out: list[Refused] = []
    if idea["status"] == "merged":
        return [Refused(409, "merged", "This draft was merged into another idea. Nothing else to send.")]
    title, summary = title_and_summary(conn, idea)
    if not title or len(title) > TITLE_MAX:
        out.append(Refused(422, "not_ready", "Give it a title of a few words.", "title"))
    if not summary:
        out.append(Refused(422, "not_ready", "Say what happens, in a sentence or two.", "summary"))
    choices = sorting.current(conn, idea, li)
    if not sorting.is_confirmed(choices):
        out.append(Refused(422, "sorting_unconfirmed", sorting.UNCONFIRMED, "sorting"))
    elif not sorting.is_complete(choices):
        out.append(Refused(422, "sorting_unconfirmed", sorting.INCOMPLETE, "sorting"))
    for file_id in waiting_files(conn, str(idea["id"])):
        out.append(
            Refused(
                422, "file_blocked", "This file is still being checked. Wait a moment, or remove it.", file_id
            )
        )
    lead = waiting_merge(conn, str(idea["id"]))
    if lead:
        out.append(
            Refused(
                409,
                "merge_waiting",
                f"Waiting for {lead} to accept the merge. If {lead} declines, you can send yours on its own.",
            )
        )
    return out


def send_view(conn: Conn, key: str, user_id: str, *, now: dt.datetime) -> dict[str, Any]:
    """`GET /drafts/:id/send`: the Send part's summary rows, the declaration, the button's label and what would stop
    Submit now (S-05 part 7, L-SUBMIT.pre)."""
    idea, _code = own.load_own(conn, key, user_id)
    if idea["status"] not in ("draft", "merged"):
        raise Refused(409, "already_shared", "This idea has been sent.", ref=idea["idea_id"])
    li = config.lists()
    uid = str(idea["id"])
    title, _summary = title_and_summary(conn, idea)
    choices = sorting.current(conn, idea, li)
    found = problems(conn, idea, li)
    lead = waiting_merge(conn, uid)
    similar = conn.execute("SELECT count(*) AS n FROM similar_links WHERE idea_uuid = %s", (uid,)).fetchone()
    n_similar = int(similar["n"]) if similar else 0
    files, links = _proof(conn, uid)
    blocked = waiting_files(conn, uid)
    fix = fix_line(conn, uid)
    helpers_value = helpers.line(list(idea.get("helper_picks") or []), idea.get("helper_text"))
    if lead:
        similar_value = f"Waiting on {lead} to merge"
    elif n_similar:
        similar_value = _count(n_similar, "similar idea") + " found"
        if idea.get("kept_separate"):
            similar_value += ", kept yours separate"
    elif check.couldnt_check(conn, idea):
        similar_value = check.COULDNT_CHECK  # never "nobody has raised this" (L-SIMILAR.failure)
    else:
        similar_value = "Nobody has raised this yet"
    proof_bits = [_count(files, "file") if files else "", _count(links, "link") if links else ""]
    rows = [
        {"key": "title", "label": "Title", "value": title or None, "ok": bool(title), "step": "check:1"},
        {
            "key": "sorting",
            "label": "Sorting",
            "value": sorting.summary_line(choices),
            "ok": sorting.is_confirmed(choices) and sorting.is_complete(choices),
            "step": "check:2",
        },
        {
            "key": "similar",
            "label": "Similar ideas",
            "value": similar_value,
            "ok": lead is None,
            "step": "check:3",
        },
        {
            "key": "proof",
            "label": "Proof",
            "value": join([b for b in proof_bits if b]) or "None added",
            "ok": not blocked,
            "step": "check:4",
        },
        {"key": "fix", "label": "Your fix", "value": fix or "None added", "ok": True, "step": "check:5"},
        {
            "key": "helpers",
            "label": "Who would help",
            "value": helpers_value,
            "ok": True,
            "step": "check:6",
        },
    ]
    first = found[0] if found else None
    return {
        "id": uid,
        "rows": rows,
        "declaration": {"version": config.DECLARATION_VERSION, "text": config.DECLARATION["submit"]},
        "button": "Submit with my fix" if fix else "Submit",
        "ready": not found,
        "problems": [p.body()["error"] for p in found],
        **({"submit_says": first.body()["error"]} if first else {}),
        **(
            {"go_to": {"label": "Go to the sorting", "step": "check:2"}}
            if first and first.field == "sorting"
            else {}
        ),
    }
