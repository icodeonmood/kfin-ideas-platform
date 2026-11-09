"""Solution write-ups other teams can adopt (BLD-133).

Once a delivery has shipped or been resolved, its owner (or an admin) drafts a short write-up: what it does,
where it runs, the result and how another team can adopt it (who to talk to by role, never by name). The text
will be shown to everyone, so every part passes the patterns, the gatekeeper and the colleague and client
detector before it is saved; it is stored sealed. The owner submits it; the named sponsor approves it (never the
person who submitted it) or sends it back. Approval gives it the next free SOL- number and queues
`solution.published`; the repo writer writes `solutions/SOL-NNNN.md` and the indexer makes it an "Already
running" match that the adoption request flow (B5) works on. Publishing can be paused with `solutions.publish`.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

from psycopg.types.json import Jsonb

from comms.route import emit
from core import killswitch
from core.config import get_settings
from core.db import Conn
from delivery import service
from ones.service import roles
from ones.text import checked, seal_json, unseal_json
from repo_writer.render_docs import doc_problem, solution_doc

OPEN_STATES = ("shipped", "resolved", "closed")
PARTS: dict[str, tuple[int, int]] = {  # (min chars, max chars)
    "title": (5, 80),
    "what_it_does": (20, 600),
    "where_it_runs": (5, 300),
    "result": (10, 400),
    "how_to_adopt": (20, 600),
}
STATE_WORDS = {
    "draft": "Draft",
    "submitted": "With the sponsor",
    "approved": "Published",
    "sent_back": "Sent back for changes",
}


def _row(conn: Conn, delivery_id: int, *, lock: bool = False) -> dict[str, Any] | None:
    if lock:
        row = conn.execute(
            "SELECT * FROM solution_writeups WHERE delivery_id = %s FOR UPDATE", (delivery_id,)
        )
    else:
        row = conn.execute("SELECT * FROM solution_writeups WHERE delivery_id = %s", (delivery_id,))
    found = row.fetchone()
    return dict(found) if found else None


def _may_draft(have: set[str], d: dict[str, Any], actor: str) -> bool:
    return d["state"] in OPEN_STATES and ("admin" in have or actor == str(d.get("owner_user_id")))


def save(conn: Conn, actor: str, delivery_id: Any, body: dict[str, Any]) -> dict[str, Any]:
    d = service._delivery(conn, delivery_id)
    have = roles(conn, actor)
    if not _may_draft(have, d, actor):
        raise service.Refused(403, "owner_only")
    parts: dict[str, str] = {}
    for key, (lo, hi) in PARTS.items():  # checked before the transaction: the gatekeeper is a model call
        try:
            parts[key] = checked(conn, body.get(key), min_chars=lo, max_chars=hi, public=True)
        except service.Refused as exc:
            raise service.Refused(exc.status, f"{exc.code}:{key}") from None
    with conn.transaction():
        d = service._delivery(conn, d["id"], lock=True)
        current = _row(conn, d["id"], lock=True)
        if current and current["state"] in ("submitted", "approved"):
            raise service.Refused(409, "writeup_locked")
        if current is None:
            row = conn.execute(
                "INSERT INTO solution_writeups (delivery_id, parts_encrypted, drafted_by) VALUES (%s, %s, %s) "
                "RETURNING id",
                (d["id"], b"", actor),
            ).fetchone()
            assert row is not None
            wid = row["id"]
        else:
            wid = current["id"]
        conn.execute(  # everyone who ever wrote any of it is kept, and none of them may approve it (BLD-142)
            "UPDATE solution_writeups SET parts_encrypted = %s, state = 'draft', drafted_by = %s, "
            "contributors = CASE WHEN %s = ANY(contributors) THEN contributors ELSE contributors || %s::uuid END "
            "WHERE id = %s",
            (seal_json(parts, f"writeup:{wid}"), actor, actor, actor, wid),
        )
        service._audit(conn, actor, "delivery.writeup_saved", f"delivery:{d['id']}", {"writeup": wid})
    return {"id": wid, "state": "draft"}


def submit(conn: Conn, actor: str, delivery_id: Any, now: dt.datetime | None = None) -> dict[str, Any]:
    now = now or dt.datetime.now(dt.UTC)
    d = service._delivery(conn, delivery_id)
    if not _may_draft(roles(conn, actor), d, actor):
        raise service.Refused(403, "owner_only")
    with conn.transaction():
        w = _row(conn, d["id"], lock=True)
        if w is None or w["state"] != "draft":
            raise service.Refused(409, "nothing_to_submit")
        conn.execute(
            "UPDATE solution_writeups SET state = 'submitted', submitted_by = %s, submitted_at = %s, "
            "contributors = CASE WHEN %s = ANY(contributors) THEN contributors ELSE contributors || %s::uuid END "
            "WHERE id = %s",
            (actor, now, actor, actor, w["id"]),
        )
        service._audit(conn, actor, "delivery.writeup_submitted", f"delivery:{d['id']}", {"writeup": w["id"]})
        if d["sponsor_user_id"]:
            emit(
                conn,
                "delivery.writeup_submitted",
                {
                    "delivery_id": d["id"],
                    "subject_id": d["subject_id"],
                    "current_owner_ids": [str(d["sponsor_user_id"])],
                },
            )
    return {"id": w["id"], "state": "submitted"}


def _sponsor_decides(conn: Conn, d: dict[str, Any], w: dict[str, Any] | None, actor: str) -> dict[str, Any]:
    if actor != str(d.get("sponsor_user_id")) or not (roles(conn, actor) & service.SPONSOR_ROLES):
        raise service.Refused(403, "sponsor_only")
    if w is None or w["state"] != "submitted":
        raise service.Refused(409, "not_submitted")
    if actor in _writers(w):
        raise service.Refused(403, "own_submission")  # nobody approves what they wrote (BLD-126, BLD-142)
    return w


def _writers(w: dict[str, Any]) -> set[str]:
    return {str(x) for x in (w.get("contributors") or [])} | {
        str(x) for x in (w.get("drafted_by"), w.get("submitted_by")) if x
    }


def _repo_has(sol: str) -> bool:
    return (Path(get_settings().company_repo_path) / "solutions" / f"{sol}.md").exists()


def approve(conn: Conn, actor: str, delivery_id: Any, now: dt.datetime | None = None) -> dict[str, Any]:
    now = now or dt.datetime.now(dt.UTC)
    if not killswitch.is_on("solutions.publish", conn):
        raise service.Refused(503, "publishing_paused")
    d = service._delivery(conn, delivery_id)
    with conn.transaction():
        w = _sponsor_decides(conn, d, _row(conn, d["id"], lock=True), actor)
        while True:  # the next free number, skipping any the product team added by hand
            n = conn.execute("SELECT next_number('SOL', 'all') AS n").fetchone()["n"]  # type: ignore[index]
            if n > 9999:
                raise service.Refused(409, "solution_numbers_full")
            sol = f"SOL-{n:04d}"
            if not _repo_has(sol):
                break
        # The repo writer's exact check, now: anything it would refuse is refused here instead (BLD-143).
        rel, text, _title = solution_doc(conn, w, sol, now)
        if doc_problem(text, rel, list(get_settings().kfin_domains)):
            raise service.Refused(422, "writeup_needs_changes")
        conn.execute(
            "UPDATE solution_writeups SET state = 'approved', approved_by = %s, approved_at = %s, solution_id = %s "
            "WHERE id = %s",
            (actor, now, sol, w["id"]),
        )
        conn.execute(  # who approved is in audit_log; the outbox (and the git history) names the process only
            "INSERT INTO outbox (event_type, aggregate_id, actor, payload) VALUES ('solution.published', %s, "
            "'process:solution-approval', %s)",
            (sol, Jsonb({"writeup_id": w["id"]})),
        )
        service._audit(
            conn,
            actor,
            "delivery.writeup_approved",
            f"delivery:{d['id']}",
            {"writeup": w["id"], "solution": sol},
        )
        emit(
            conn,
            "delivery.writeup_decided",
            {"delivery_id": d["id"], "subject_id": d["subject_id"], "current_owner_ids": [str(w["submitted_by"])],
             "decision": "approved", "solution_id": sol},
        )  # fmt: skip
    return {"id": w["id"], "state": "approved", "solution_id": sol}


def send_back(conn: Conn, actor: str, delivery_id: Any) -> dict[str, Any]:
    d = service._delivery(conn, delivery_id)
    with conn.transaction():
        w = _sponsor_decides(conn, d, _row(conn, d["id"], lock=True), actor)
        conn.execute("UPDATE solution_writeups SET state = 'sent_back' WHERE id = %s", (w["id"],))
        service._audit(conn, actor, "delivery.writeup_sent_back", f"delivery:{d['id']}", {"writeup": w["id"]})
        emit(
            conn,
            "delivery.writeup_decided",
            {"delivery_id": d["id"], "subject_id": d["subject_id"], "current_owner_ids": [str(w["submitted_by"])],
             "decision": "sent_back"},
        )  # fmt: skip
    return {"id": w["id"], "state": "sent_back"}


def view(conn: Conn, d: dict[str, Any], viewer_id: str, have: set[str]) -> dict[str, Any] | None:
    """For the delivery page: the parts for the people on the delivery, the state for everyone who can see it."""
    w = _row(conn, d["id"])
    may_draft = _may_draft(have, d, viewer_id)
    if w is None:
        return {"state": None, "state_words": "Not started", "parts": None, "solution_id": None,
                "can_edit": may_draft, "can_submit": False, "can_decide": False} if may_draft or \
            d["state"] in OPEN_STATES else None  # fmt: skip
    parts = unseal_json(w["parts_encrypted"], f"writeup:{w['id']}") if w["parts_encrypted"] else None
    sponsor = viewer_id == str(d.get("sponsor_user_id")) and bool(have & service.SPONSOR_ROLES)
    return {
        "state": w["state"], "state_words": STATE_WORDS[w["state"]], "parts": parts,
        "solution_id": w["solution_id"],
        "can_edit": may_draft and w["state"] in ("draft", "sent_back"),
        "can_submit": may_draft and w["state"] == "draft",
        "can_decide": sponsor and w["state"] == "submitted" and viewer_id not in _writers(w),
    }  # fmt: skip
