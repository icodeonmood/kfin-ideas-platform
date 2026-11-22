"""A sharer asks, from an unsent draft, for it to be merged into a shared idea (L-MERGE.request, A-API.drafts).

Merging is always a request: only the other idea's lead accepts it, through the same answer as a team-up request
(`requests.answer`, BLD-F010). The request carries the note and the draft's masked title and summary, read from
the draft (BLD-F014); the draft is shared with no one else by this. While it waits the draft is held: lane C's
Submit refuses with `merge_waiting`, using `waiting_merge_request` below.
"""

from __future__ import annotations

import uuid
from typing import Any

import psycopg

from core.db import Conn
from teamup import adapters, rules
from teamup.requests import Req, end_sent_drafts, ended, load_request, settle, tell_lead, waiting_from, words
from teamup.store import (
    Refused,
    actor,
    audit,
    audited,
    code_of,
    hidden_from,
    is_closed,
    lead_code,
    lead_seen_by,
    load_draft,
    load_idea_for,
    lock_ideas,
    remember,
    remembered,
    require_code,
    seal,
    unseal,
)
from teamup.store import now as clock_now

ROUTE_ASK = "POST /drafts/:id/merge-request"


def _latest(conn: Conn, draft_uuid: Any) -> Req | None:
    row = conn.execute(
        "SELECT id FROM merge_requests WHERE draft_uuid = %s ORDER BY sent_at DESC, id LIMIT 1", (draft_uuid,)
    ).fetchone()
    return load_request(conn, str(row["id"])) if row else None


def waiting_merge_request(conn: Conn, draft_uuid: Any) -> str | None:
    """The id of the draft's waiting merge request, if any: Submit is unavailable while it waits
    (L-MERGE.request/4; lane C's `merge_waiting`)."""
    row = conn.execute(
        "SELECT id FROM merge_requests WHERE draft_uuid = %s AND state = 'waiting'", (draft_uuid,)
    ).fetchone()
    return str(row["id"]) if row else None


def merge_request_json(conn: Conn, req: Req | None, user_id: str) -> dict[str, Any]:
    """E-ENTITIES Draft.merge_request `{other_idea_id, state, note, lead_reason?}`, plus the request id, the lead
    and what Check it shows (`after`, L-MERGE.request/4–8). `{state: 'none'}` when there has been none. Only the
    draft's owner (`user_id`) reads it; the lead is named to them only as DEC-104 allows (BLD-F029). The owner
    typed the ask, so `note` is their own words (lane C's sealed copy, BLD-F097); the lead's reason is masked.
    Whether the reader typed the ask is read from `user_id` against the request's `from_code`, never assumed, so
    anyone else reads it masked (DEC-103, BLD-F098)."""
    if req is None:
        return {"state": "none", "after": None}
    lead = lead_seen_by(conn, req.idea, user_id, str(req.row["from_code"]))
    reason = unseal(req.row["lead_reason_encrypted"], "merge_requests", "lead_reason_encrypted", req.id)
    typed_it = code_of(conn, user_id) == str(req.row["from_code"])
    out: dict[str, Any] = {
        "id": req.id,
        "other_idea_id": req.idea["idea_id"],
        "state": req.state,
        "note": words(conn, req, "note", mine=typed_it) or "",
        "lead": lead.ref,
        "after": rules.draft_after(
            req.state, lead_first=lead.first, lead_ref=str(req.idea["idea_id"]), reason=reason
        ),
    }
    if reason:
        out["lead_reason"] = reason
    return out


def state(conn: Conn, draft_id: str, user_id: str) -> dict[str, Any]:
    """`GET /drafts/:id/merge-request` (BLD-F015): the draft's latest merge request, for its owner."""
    draft = load_draft(conn, draft_id, require_code(conn, user_id))
    req = _latest(conn, draft["id"])
    if req is not None and ended(req):  # the idea closed, or this draft was sent or archived (BLD-F024)
        settle(conn, req.idea)
        req = _latest(conn, draft["id"])
    return merge_request_json(conn, req, user_id)


def ask(
    conn: Conn, draft_id: str, user_id: str, body: dict[str, Any], idempotency_key: str | None = None
) -> dict[str, Any]:
    """`POST /drafts/:id/merge-request` `{other_idea_id, note}`: "Ask {lead} to merge mine in" (L-MERGE.request/1–4).
    Returns the draft's merge request in state `waiting`. Errors: note_too_short (30), already_requested,
    already_on_crew (they lead that idea), idea_closed, draft_closed, not_found (a withdrawn idea, BLD-E011),
    key_reused (BLD-F026)."""
    code = require_code(conn, user_id)
    asked = {"draft": draft_id, **body}
    made = remembered(conn, user_id, idempotency_key, ROUTE_ASK, asked)
    if made is not None:
        return merge_request_json(conn, load_request(conn, made), user_id)
    note = str(body.get("note") or "")
    with audited(conn), conn.transaction():
        draft = load_draft(conn, draft_id, code)
        other = load_idea_for(conn, str(body.get("other_idea_id") or ""), code)
        # lane C's lock on both ideas first, in uuid order, then their rows in the same order (BLD-B247, BLD-F097):
        # the ask goes through lane C's hide below, which takes the draft's again (re-entrant)
        adapters.lock_hide(conn, draft["id"], other["id"])
        locked = lock_ideas(conn, draft["id"], other["id"])
        draft, other = locked[str(draft["id"])], locked[str(other["id"])]
        if hidden_from(conn, other, code):  # withdrawn while this waited for the lock
            raise Refused(404, "not_found")
        # the same key sent twice at once: the second waited for the lock, and returns the first
        made = remembered(conn, user_id, idempotency_key, ROUTE_ASK, asked)
        if made is not None:
            return merge_request_json(conn, load_request(conn, made), user_id)
        if draft["status"] != "draft" or draft["archived_at"] is not None:
            raise Refused(409, "draft_closed", "This draft has already been sent.")
        if is_closed(str(other["status"])):
            raise Refused(409, "idea_closed", "This idea is no longer open to merge.")
        lead_of_other = lead_code(conn, other)
        if lead_of_other == code:
            raise Refused(409, "already_on_crew", "You lead this idea.")
        # BLD-F029: "Waiting on the lead to merge" when the lead is not named to them
        lead = lead_seen_by(conn, other, user_id, code)
        # a request from a draft sent since does not count as open (BLD-F024)
        end_sent_drafts(conn, other["id"])
        if waiting_merge_request(conn, draft["id"]) or waiting_from(conn, other["id"], code):
            raise Refused(409, "already_requested", rules.waiting_on_merge(lead.first))
        problem = rules.check_note(note, adapters.note_min())
        if problem:
            raise Refused(problem.status, problem.code, problem.message, problem.field)
        # L-HIDE, DEC-103, BLD-F097: lane C's hide (patterns, then the gatekeeper) before the lead or anything else
        # sees the ask, under the draft (its owner typed it) and the merge request's id, made first
        rid = str(uuid.uuid4())
        masked, _ = adapters.hide(
            conn, str(draft["id"]), note.strip(), by=user_id, source_id=adapters.ask_id(rid)
        )
        try:
            with conn.transaction():
                conn.execute(
                    "INSERT INTO merge_requests (id, draft_uuid, other_idea_uuid, from_code, note_encrypted, sent_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (rid, draft["id"], other["id"], code, seal(masked, "merge_requests", "note_encrypted", rid),
                     clock_now()),
                )  # fmt: skip
        except psycopg.errors.UniqueViolation:
            raise Refused(409, "already_requested", rules.waiting_on_merge(lead.first)) from None
        # L-AUDIT.metrics; the reviewer's page reads it (V-ACC.similar/7 reads `kept_separate` the same way)
        conn.execute(
            "UPDATE similar_links SET outcome = 'merge_asked' WHERE idea_uuid = %s AND other_idea_uuid = %s",
            (draft["id"], other["id"]),
        )
        tell_lead(conn, rid, "merge", other, 1, user_id)
        audit(conn, actor(user_id), "merge_request.ask", f"draft:{draft['id']}",
              after={"request_id": rid, "other_idea_id": other["idea_id"]})  # fmt: skip
        remember(conn, user_id, idempotency_key, ROUTE_ASK, asked, rid)
        return merge_request_json(conn, load_request(conn, rid), user_id)


def withdraw(conn: Conn, draft_id: str, user_id: str) -> dict[str, Any]:
    """`DELETE /drafts/:id/merge-request`: the draft returns to normal (L-MERGE.request/8). Idempotent."""
    code = require_code(conn, user_id)
    draft = load_draft(conn, draft_id, code)
    rid = waiting_merge_request(conn, draft["id"])
    if rid is not None:
        from teamup.requests import withdraw as withdraw_request

        withdraw_request(conn, rid, user_id)
    latest = _latest(conn, draft["id"])
    if latest is None:
        raise Refused(404, "not_found")
    return merge_request_json(conn, latest, user_id)
