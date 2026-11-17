"""Team-up requests on a shared idea, and the lead's answer to them and to draft merge requests (L-TEAMUP,
A-API.team-up, S-H2B, C-SHEET-TEAMUP).

One request id answers for both tables (BLD-F010): `POST /team-up/:id/answer` and `DELETE /team-up/:id` look the
id up in `teamup_requests`, then in `merge_requests`, so the lead's Inbox reader has one way to answer either.
Agents never answer: only the idea's lead can (V-ACC.similar/8, non-negotiable 5).
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass
from typing import Any

import psycopg

from core.db import Conn
from onepc.enums import CLOSED_STATUSES
from teamup import adapters, rules
from teamup.merging import apply_lead_merge, join_crew
from teamup.rules import Answer, Kind
from teamup.store import (
    Person,
    Refused,
    actor,
    audit,
    audited,
    code_of,
    crew_codes,
    crew_role,
    entity_of,
    is_closed,
    lead_code,
    load_draft,
    load_idea,
    person_by_code,
    remember,
    remembered,
    require_code,
    seal,
    unseal,
    user_of,
)
from teamup.store import now as clock_now

ROUTE_SEND = "POST /ideas/:id/team-up"


@dataclass
class Req:
    """A team-up request or a draft merge request, read the same way."""

    kind: Kind
    row: dict[str, Any]
    idea: dict[str, Any]  # the lead's idea, whatever its status now
    brought: list[dict[str, Any]]  # the ideas brought along; a draft merge request brings its draft

    @property
    def id(self) -> str:
        return str(self.row["id"])

    @property
    def table(self) -> str:
        return "teamup_requests" if self.kind == "teamup" else "merge_requests"

    @property
    def state(self) -> str:
        return str(self.row["state"])

    @property
    def waiting(self) -> bool:
        return self.state == rules.WAITING[self.kind]

    @property
    def teamup_state(self) -> str:
        return self.state if self.kind == "teamup" else rules.AS_TEAMUP_STATE[self.state]


def _idea_row(conn: Conn, idea_uuid: Any) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM ideas WHERE id = %s", (idea_uuid,)).fetchone()
    if row is None:
        raise Refused(404, "not_found")
    return dict(row)


def load_request(conn: Conn, request_id: str, *, lock: bool = False) -> Req:
    """BLD-F010: a team-up request, else a draft merge request, by id; 404 when neither."""
    try:
        uuid.UUID(request_id)
    except ValueError:
        raise Refused(404, "not_found") from None
    suffix = " FOR UPDATE" if lock else ""
    row = conn.execute(f"SELECT * FROM teamup_requests WHERE id = %s{suffix}", (request_id,)).fetchone()  # noqa: S608
    if row is not None:
        brought = conn.execute(
            "SELECT i.* FROM teamup_brought b JOIN ideas i ON i.id = b.idea_uuid WHERE b.request_id = %s "
            "ORDER BY i.shared_at NULLS LAST, i.id",
            (request_id,),
        ).fetchall()
        return Req("teamup", dict(row), _idea_row(conn, row["idea_uuid"]), [dict(b) for b in brought])
    row = conn.execute(f"SELECT * FROM merge_requests WHERE id = %s{suffix}", (request_id,)).fetchone()  # noqa: S608
    if row is not None:
        return Req(
            "merge", dict(row), _idea_row(conn, row["other_idea_uuid"]), [_idea_row(conn, row["draft_uuid"])]
        )
    raise Refused(404, "not_found")


# --- closing with the idea (L-TEAMUP.states) -------------------------------------------------------------------
def close_requests_for(conn: Conn, idea_uuid: Any, at: dt.datetime | None = None) -> int:
    """Waiting requests on an idea that closed (withdrawn, not picked, not now, merged away) close with it.
    A draft merge request has no `closed` state (E-ENUMS.teamup), so it becomes `withdrawn` and the draft is back to
    normal (BLD-F016). The lead's "Needs you" items are resolved."""
    t = at or clock_now()
    ids = [
        str(r["id"])
        for r in conn.execute(
            "UPDATE teamup_requests SET state = 'closed', answered_at = %s WHERE idea_uuid = %s AND state = 'sent' "
            "RETURNING id",
            (t, idea_uuid),
        ).fetchall()
    ]
    ids += [
        str(r["id"])
        for r in conn.execute(
            "UPDATE merge_requests SET state = 'withdrawn', answered_at = %s "
            "WHERE other_idea_uuid = %s AND state = 'waiting' RETURNING id",
            (t, idea_uuid),
        ).fetchall()
    ]
    for rid in ids:
        adapters.resolve(conn, rid)
    if ids:
        audit(conn, "system", "teamup.closed_with_idea", f"idea_uuid:{idea_uuid}", after={"closed": len(ids)})
    return len(ids)


def settle(conn: Conn, idea: dict[str, Any]) -> None:
    """Close what is still waiting on an idea that has closed, so every read agrees (lazy, idempotent)."""
    if is_closed(str(idea["status"])):
        with conn.transaction():
            close_requests_for(conn, idea["id"])


# --- shapes ----------------------------------------------------------------------------------------------------
def _byline(conn: Conn, idea: dict[str, Any], now: dt.datetime) -> str:
    """ "Kavya Menon, Investor service, Hyderabad. Shared Saturday." (S-H2B.reader/3)."""
    p = person_by_code(conn, idea["contributor_code"])
    who = ", ".join(x for x in (p.name, idea.get("area") or p.area, idea.get("city") or p.city) if x)
    shared = rules.shared_label(idea.get("shared_at"), now)
    return f"{who}. {shared}".strip() if shared else f"{who}."


def idea_ref(
    conn: Conn, idea: dict[str, Any], now: dt.datetime | None = None, *, full: bool = False
) -> dict[str, Any]:
    """E-ENTITIES IdeaRef (a draft has no reference: its row id, status `draft`). With `full`, the masked summary
    and byline the lead's reader shows; never the sharer's own words (P-PRODUCT.privacy)."""
    ref = idea.get("idea_id")
    out: dict[str, Any] = {
        "id": ref or str(idea["id"]),
        "title": idea.get("title") or "",
        "status": idea["status"],
    }
    if ref:
        out["meta"] = rules.status_meta(str(ref), str(idea["status"]))
    if full:
        out["summary"] = idea.get("summary") or ""
        out["byline"] = _byline(conn, idea, now or clock_now())
        out["shared_at"] = idea["shared_at"].isoformat() if idea.get("shared_at") else None
    return out


def request_json(conn: Conn, req: Req, *, full: bool = False) -> dict[str, Any]:
    """E-ENTITIES TeamUpRequest, plus `request` ('teamup' or 'merge'). A draft merge request reads with team-up
    states. Only its two parties ever get one (the requester and the lead)."""
    t = clock_now()
    out: dict[str, Any] = {
        "id": req.id,
        "request": req.kind,
        "idea_id": req.idea.get("idea_id"),
        "from": person_by_code(conn, req.row["from_code"]).as_json(),
        "note": unseal(req.row["note_encrypted"], req.table, "note_encrypted", req.id) or "",
        "brought": [idea_ref(conn, b, t, full=full) for b in req.brought],
        "state": req.teamup_state,
        "sent_at": req.row["sent_at"].isoformat(),
    }
    reason = unseal(req.row["lead_reason_encrypted"], req.table, "lead_reason_encrypted", req.id)
    if reason:
        out["lead_reason"] = reason
    if req.row["answered_at"] is not None:
        out["answered_at"] = req.row["answered_at"].isoformat()
    return out


def _actions(brings: bool) -> list[tuple[str, str, str | None, str | None]]:
    return [(a["label"], a["style"], None, f"teamup.answer.{a['answer']}") for a in rules.answers_for(brings)]


def tell_lead(conn: Conn, req_id: str, kind: Kind, idea: dict[str, Any], brought: int, sender: str) -> None:
    """`teamup_request` to the lead, under "Needs you", with the three answers (refs: request_id, request,
    brought). The dedupe key lets lane A resolve it when the request is withdrawn, answered or closed."""
    lead_user = user_of(conn, lead_code(conn, idea))
    adapters.tell(
        conn, "teamup_request", [lead_user] if lead_user else [], idea_uuid=str(idea["id"]), sender=sender,
        needs_you=True, actions=_actions(brought > 0),
        refs={"request_id": req_id, "request": kind, "brought": brought}, dedupe_key=adapters.request_key(req_id),
    )  # fmt: skip


# --- A-API.team-up ---------------------------------------------------------------------------------------------
def own_open_ideas(conn: Conn, code: str, exclude: Any = None) -> list[dict[str, Any]]:
    """V-FIELDS.teamup/2: the person's own shared ideas that are not closed, newest first."""
    rows = conn.execute(
        "SELECT * FROM ideas WHERE contributor_code = %s AND status <> 'draft' AND NOT (status = ANY(%s)) "
        "AND id IS DISTINCT FROM %s ORDER BY shared_at DESC NULLS LAST, id",
        (code, list(CLOSED_STATUSES), exclude),
    ).fetchall()
    return [dict(r) for r in rows]


def _closest(conn: Conn, target: Any, own: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The person's own idea closest to this one: a similar-ideas link if there is one, else their newest."""
    if not own:
        return None
    ids = [o["id"] for o in own]
    row = conn.execute(
        "SELECT CASE WHEN idea_uuid = %s THEN other_idea_uuid ELSE idea_uuid END AS mine FROM similar_links "
        "WHERE (idea_uuid = %s AND other_idea_uuid = ANY(%s)) OR (other_idea_uuid = %s AND idea_uuid = ANY(%s)) "
        "ORDER BY strength = 'close' DESC, rank, updated_at DESC LIMIT 1",
        (target, target, ids, target, ids),
    ).fetchone()
    if row is not None:
        for o in own:
            if o["id"] == row["mine"]:
                return o
    return own[0]


def draft_note(conn: Conn, ref: str, user_id: str) -> dict[str, Any]:
    """`GET /ideas/:id/team-up/draft-note`: the pre-filled note (L-TEAMUP.rules/2, BLD-F011) and the person's own
    shared ideas that can be brought (none is selected, C-SHEET-TEAMUP.compose/4)."""
    idea = load_idea(conn, ref)
    code = require_code(conn, user_id)
    me = person_by_code(conn, code)
    own = own_open_ideas(conn, code, exclude=idea["id"])
    closest = _closest(conn, idea["id"], own)
    lead = person_by_code(conn, lead_code(conn, idea))
    return {
        "note": rules.draft_note(
            area=me.area, role=me.role_title, closest_title=closest["title"] if closest else None
        ),
        "own_ideas": [idea_ref(conn, o) for o in own],
        "idea": {"id": idea["idea_id"], "title": idea["title"] or ""},
        "lead": lead.as_json(),
        "min_chars": adapters.note_min(),
        "max_chars": rules.NOTE_MAX,
    }


def _latest_mine(conn: Conn, idea: dict[str, Any], code: str) -> Req | None:
    """The person's latest request on this idea: a team-up request or a draft merge request."""
    row = conn.execute(
        "SELECT id, sent_at FROM teamup_requests WHERE idea_uuid = %s AND from_code = %s "
        "UNION ALL SELECT id, sent_at FROM merge_requests WHERE other_idea_uuid = %s AND from_code = %s "
        "ORDER BY sent_at DESC LIMIT 1",
        (idea["id"], code, idea["id"], code),
    ).fetchone()
    return load_request(conn, str(row["id"])) if row else None


def waiting_from(conn: Conn, idea_uuid: Any, code: str) -> bool:
    """L-TEAMUP.rules/4: one open request per person per idea, counting a draft merge request to it."""
    row = conn.execute(
        "SELECT 1 FROM teamup_requests WHERE idea_uuid = %s AND from_code = %s AND state = 'sent' "
        "UNION ALL SELECT 1 FROM merge_requests WHERE other_idea_uuid = %s AND from_code = %s AND state = 'waiting'",
        (idea_uuid, code, idea_uuid, code),
    ).fetchone()
    return row is not None


def after_for(conn: Conn, req: Req, role: str | None) -> dict[str, object] | None:
    """What the screen that opened the sheet shows now (C-SHEET-TEAMUP.after; L-MERGE.request/4–8)."""
    lead = person_by_code(conn, lead_code(conn, req.idea))
    reason = unseal(req.row["lead_reason_encrypted"], req.table, "lead_reason_encrypted", req.id)
    ref = str(req.idea.get("idea_id") or "")
    if req.kind == "merge":
        return rules.draft_after(req.state, lead_first=lead.first_name, lead_ref=ref, reason=reason)
    if req.state.startswith("approved_") and role is None:
        return None  # they have left the crew since: back to "Team up"
    return rules.requester_after(req.state, lead_first=lead.first_name, lead_ref=ref, reason=reason,
                                 brought=len(req.brought))  # fmt: skip


def my_state(conn: Conn, ref: str, user_id: str) -> dict[str, Any]:
    """`GET /ideas/:id/team-up` (BLD-F015): this idea's team-up state for the signed-in person, so every screen
    that shows the idea agrees: "Waiting for {lead}" with Withdraw (V-ACC.teamup/4), on the crew, or Team up."""
    idea = load_idea(conn, ref)
    settle(conn, idea)
    code = code_of(conn, user_id)
    role = crew_role(conn, idea["id"], code) if code else None
    lead = person_by_code(conn, lead_code(conn, idea))
    mine = _latest_mine(conn, idea, code) if code else None
    if role is not None:
        why: str | None = "already_on_crew"
    elif is_closed(str(idea["status"])):
        why = "idea_closed"
    elif mine is not None and mine.waiting:
        why = "already_requested"
    else:
        why = None
    return {
        "idea_id": idea["idea_id"],
        "lead": lead.as_json(),
        "me": role,
        "crew_count": len(crew_codes(conn, idea["id"])),
        "can_request": why is None and code is not None,
        "why_not": why,
        "request": request_json(conn, mine) if mine else None,
        "after": after_for(conn, mine, role) if mine else None,
    }


def _brought_rows(conn: Conn, raw: Any, code: str, target: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list) or not all(isinstance(x, str) for x in raw):
        raise Refused(422, "brought_invalid", "Choose from your own shared ideas.", "brought_idea_ids")
    out: dict[str, dict[str, Any]] = {}
    for ref in raw:
        try:
            row = load_idea(conn, ref)
        except Refused:
            raise Refused(
                422, "brought_invalid", "Choose from your own shared ideas.", "brought_idea_ids"
            ) from None
        if row["contributor_code"] != code or is_closed(str(row["status"])) or row["id"] == target:
            raise Refused(422, "brought_invalid", "Choose from your own shared ideas.", "brought_idea_ids")
        out[str(row["id"])] = row
    return list(out.values())


def send(
    conn: Conn, ref: str, user_id: str, body: dict[str, Any], idempotency_key: str | None = None
) -> dict[str, Any]:
    """`POST /ideas/:id/team-up` `{note, brought_idea_ids, draft_id?}` (L-TEAMUP.rules/1–4). Returns the
    TeamUpRequest and the sheet's "Sent" state. Errors: note_too_short (30), already_requested, already_on_crew,
    idea_closed. `draft_id` marks "Keep mine separate" from Check it on that draft's similar ideas (V-ACC.similar/7)."""
    note = str(body.get("note") or "")
    made = remembered(conn, user_id, idempotency_key, ROUTE_SEND)
    if made is not None:
        req = load_request(conn, made)
        return {**request_json(conn, req), "after": after_for(conn, req, None)}
    idea = load_idea(conn, ref)
    settle(conn, idea)
    with audited(conn), conn.transaction():
        idea = load_idea(conn, ref, lock=True)
        code = require_code(conn, user_id)
        lead = person_by_code(conn, lead_code(conn, idea))
        if is_closed(str(idea["status"])):
            raise Refused(409, "idea_closed", "This idea is no longer open to team up.")
        if crew_role(conn, idea["id"], code) is not None:
            raise Refused(409, "already_on_crew", "You’re on the crew.")
        if waiting_from(conn, idea["id"], code):
            raise Refused(409, "already_requested", f"Waiting for {lead.first_name}")
        problem = rules.check_note(note, adapters.note_min())
        if problem:
            raise Refused(problem.status, problem.code, problem.message, problem.field)
        brought = _brought_rows(conn, body.get("brought_idea_ids"), code, idea["id"])
        masked, _ = adapters.hide(conn, str(idea["id"]), note.strip())
        rid = str(uuid.uuid4())
        t = clock_now()
        try:
            with conn.transaction():
                conn.execute(
                    "INSERT INTO teamup_requests (id, idea_uuid, from_code, note_encrypted, sent_at) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (rid, idea["id"], code, seal(masked, "teamup_requests", "note_encrypted", rid), t),
                )
        except psycopg.errors.UniqueViolation:
            raise Refused(409, "already_requested", f"Waiting for {lead.first_name}") from None
        for b in brought:
            conn.execute("INSERT INTO teamup_brought (request_id, idea_uuid) VALUES (%s, %s)", (rid, b["id"]))
        draft_id = body.get("draft_id")
        if isinstance(draft_id, str) and draft_id:
            # "Keep mine separate" from Check it (L-SIMILAR.rules/8, V-ACC.similar/7): the draft is marked, which
            # Check it's summary and the reviewer's page read ("kept it separate"), and the link's outcome is kept
            # for L-AUDIT.metrics.
            draft = load_draft(conn, draft_id, code)
            if draft["status"] == "draft":
                conn.execute("UPDATE ideas SET kept_separate = true WHERE id = %s", (draft["id"],))
            conn.execute(
                "UPDATE similar_links SET outcome = 'kept_separate' WHERE idea_uuid = %s AND other_idea_uuid = %s",
                (draft["id"], idea["id"]),
            )
        tell_lead(conn, rid, "teamup", idea, len(brought), user_id)
        audit(conn, actor(user_id), "teamup.request", entity_of(idea),
              after={"request_id": rid, "brought": len(brought), "from_draft": bool(draft_id)})  # fmt: skip
        remember(conn, user_id, idempotency_key, ROUTE_SEND, {"ref": ref, **body}, rid)
        req = load_request(conn, rid)
        return {**request_json(conn, req), "after": after_for(conn, req, None)}


def read(conn: Conn, request_id: str, user_id: str) -> dict[str, Any]:
    """`GET /team-up/:id` (BLD-F015): the request for its two parties only. The lead gets the reader's words and the
    answers still open (S-H2B.reader); after answering, the result line (S-H2B.states). The requester gets what
    their screen shows (C-SHEET-TEAMUP.after)."""
    req = load_request(conn, request_id)
    code = code_of(conn, user_id)
    is_lead = code is not None and lead_code(conn, req.idea) == code
    is_from = code is not None and req.row["from_code"] == code
    if not (is_lead or is_from):
        raise Refused(404, "not_found")
    if req.waiting and is_closed(str(req.idea["status"])):
        settle(conn, req.idea)
        req = load_request(conn, request_id)
    out = request_json(conn, req, full=is_lead)
    if is_lead:
        who = person_by_code(conn, req.row["from_code"])
        out["reader"] = rules.reader_words(who.name, who.first_name, len(req.brought))
        out["answers"] = rules.answers_for(bool(req.brought)) if req.waiting else []
        out.update(_answered(req, who, out.get("lead_reason")))
    if is_from:
        out["after"] = after_for(conn, req, crew_role(conn, req.idea["id"], code) if code else None)
    return out


_ANSWER_OF: dict[str, Answer] = {
    "approved_merged": "merge",
    "approved_team_only": "team_only",
    "declined": "decline",
}


def _answered(req: Req, who: Person, reason: str | None) -> dict[str, Any]:
    """S-H2B.states for an answered request, shown in place (no Undo)."""
    ans = _ANSWER_OF.get(req.teamup_state)
    if ans is None:
        return {}
    hello = None if ans == "decline" else rules.say_hello(who.first_name, str(req.idea["idea_id"]))
    return {"result": rules.lead_result(ans, who.first_name, len(req.brought), reason), "say_hello": hello}


def withdraw(conn: Conn, request_id: str, user_id: str) -> dict[str, Any]:
    """`DELETE /team-up/:id`: the requester withdraws a waiting request (L-TEAMUP.rules/3, L-MERGE.request/8)."""
    with audited(conn), conn.transaction():
        req = load_request(conn, request_id, lock=True)
        code = require_code(conn, user_id)
        if req.row["from_code"] != code:
            raise Refused(404, "not_found")
        if req.state != "withdrawn":
            if not req.waiting:
                raise Refused(409, "not_waiting", "This request has already been answered.")
            conn.execute(f"UPDATE {req.table} SET state = 'withdrawn' WHERE id = %s", (req.id,))  # noqa: S608
            adapters.resolve(conn, req.id)
            audit(conn, actor(user_id), f"{'teamup' if req.kind == 'teamup' else 'merge_request'}.withdraw",
                  entity_of(req.brought[0] if req.kind == "merge" else req.idea),
                  after={"request_id": req.id})  # fmt: skip
        req = load_request(conn, request_id)
        return {**request_json(conn, req), "after": after_for(conn, req, None)}


def _not_waiting(req: Req, who: Person) -> Refused:
    if req.state == "withdrawn":
        return Refused(409, "not_waiting", f"{who.first_name} withdrew this request.")
    if req.state == "closed":
        return Refused(409, "idea_closed", "This idea is no longer open to team up.")
    return Refused(409, "not_waiting", "You’ve answered this request already.")


def _open_brought(req: Req) -> list[dict[str, Any]]:
    """Ideas brought that can still merge: still the requester's, still a draft (merge request) or not closed."""
    out = []
    for b in req.brought:
        if b["contributor_code"] != req.row["from_code"]:
            continue
        if req.kind == "merge":
            if b["status"] == "draft" and b["archived_at"] is None:
                out.append(b)
        elif b["status"] != "draft" and not is_closed(str(b["status"])):
            out.append(b)
    return out


def answer(conn: Conn, request_id: str, user_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """`POST /team-up/:id/answer` `{answer: 'merge'|'team_only'|'decline', reason?}`: the lead only.

    Merge it: the requester joins the crew and every idea brought merges into the lead's (L-MERGE.effects, via
    `apply_lead_merge`). Team up only / Approve: the requester joins; anything brought stays separate. Decline:
    nothing changes; an optional reason goes to the requester, masked. The requester is told at once
    (L-TEAMUP.rules/7). Returns the request, the lead's result line (S-H2B.states) and "Say hello to {requester}"."""
    choice = body.get("answer")
    if choice not in rules.ANSWERS:
        raise Refused(422, "answer_required", "Choose an answer.", "answer")
    ans: Answer = choice
    reason = str(body.get("reason") or "").strip() if ans == "decline" else ""
    peek = load_request(conn, request_id)
    if peek.waiting and is_closed(str(peek.idea["status"])):
        settle(conn, peek.idea)
        raise Refused(409, "idea_closed", "This idea is no longer open to team up.")
    with audited(conn), conn.transaction():
        # the lead's idea first, then the request: the same order as a merge, so answers cannot deadlock
        conn.execute("SELECT 1 FROM ideas WHERE id = %s FOR UPDATE", (peek.idea["id"],))
        req = load_request(conn, request_id, lock=True)
        code = code_of(conn, user_id)
        if code is None or lead_code(conn, req.idea) != code:
            raise Refused(
                403, "not_lead", "Only the lead of this idea can answer.",
                audit=(actor(user_id), "teamup.answer_refused", entity_of(req.idea),
                       {"request_id": req.id, "answer": ans}),
            )  # fmt: skip
        who = person_by_code(conn, req.row["from_code"])
        if not req.waiting:
            raise _not_waiting(req, who)
        if is_closed(str(req.idea["status"])):
            raise Refused(409, "idea_closed", "This idea is no longer open to team up.")
        mergeable = _open_brought(req)
        if ans == "merge":
            if not req.brought:
                raise Refused(422, "nothing_brought",
                              f"Nothing was brought to merge. Approve puts {who.first_name} on your crew.", "answer")  # fmt: skip
            if not mergeable:
                raise Refused(409, "brought_not_open", "That idea is no longer open to merge.")
        if reason:
            problem = rules.check_reason(reason)
            if problem:
                raise Refused(problem.status, problem.code, problem.message, problem.field)
        t = clock_now()
        state = (rules.TEAMUP_STATE_FOR if req.kind == "teamup" else rules.MERGE_STATE_FOR)[ans]
        masked_reason = adapters.hide(conn, str(req.idea["id"]), reason)[0] if reason else None
        conn.execute(
            f"UPDATE {req.table} SET state = %s, lead_reason_encrypted = %s, answered_by_code = %s, "  # noqa: S608
            "answered_at = %s WHERE id = %s",
            (state, seal(masked_reason, req.table, "lead_reason_encrypted", req.id) if masked_reason else None,
             code, t, req.id),
        )  # fmt: skip
        requester = str(req.row["from_code"])
        teamup_id = req.id if req.kind == "teamup" else None
        lead_uuid = str(req.idea["id"])
        merged = 0
        if ans == "merge":
            adapters.say(conn, lead_uuid, "teamup.approved_merged", author_code=code,
                         payload={"request_id": req.id, "request": req.kind}, at=t)  # fmt: skip
            note = unseal(req.row["note_encrypted"], req.table, "note_encrypted", req.id) or ""
            for b in mergeable:
                apply_lead_merge(
                    conn, lead_uuid=lead_uuid, merged_uuid=b["id"], by_code=code, requester_code=requester,
                    note_masked=note, teamup_request_id=teamup_id,
                    merge_request_id=req.id if req.kind == "merge" else None, at=t,
                )  # fmt: skip
                merged += 1
        elif ans == "team_only":
            adapters.say(conn, lead_uuid, "teamup.approved_team_only", author_code=code,
                         payload={"request_id": req.id, "request": req.kind}, at=t)  # fmt: skip
            join_crew(conn, req.idea, [requester], via="teamup", at=t, teamup_request_id=teamup_id,
                      payload={"request_id": req.id})  # fmt: skip
        adapters.resolve(conn, req.id)
        tell_requester(conn, req, ans, bool(masked_reason), user_id)
        audit(conn, actor(user_id), "teamup.answer", entity_of(req.idea),
              after={"request_id": req.id, "request": req.kind, "answer": ans, "merged": merged,
                     "has_reason": bool(masked_reason)})  # fmt: skip
        done = load_request(conn, request_id)
        return {
            "request": request_json(conn, done, full=True),
            "result": rules.lead_result(ans, who.first_name, len(req.brought), masked_reason),
            "say_hello": None
            if ans == "decline"
            else rules.say_hello(who.first_name, str(req.idea["idea_id"])),
        }


def tell_requester(conn: Conn, req: Req, ans: Answer, has_reason: bool, sender: str) -> None:
    """`teamup_answer` to the requester at once (L-TEAMUP.rules/7). refs: request_id, request, answer,
    has_reason; never the reason itself (it is read in the app)."""
    ref = str(req.idea["idea_id"])
    actions: list[tuple[str, str, str | None, str | None]] = []
    if ans == "merge":
        actions = [("See the merged idea", "primary", f"/ideas/{ref}", None)]
    elif ans == "team_only":
        actions = [("Say hello", "primary", f"/ideas/{ref}/conversation", None)]
    to = user_of(conn, str(req.row["from_code"]))
    adapters.tell(
        conn, "teamup_answer", [to] if to else [], idea_uuid=str(req.idea["id"]), sender=sender, actions=actions,
        refs={"request_id": req.id, "request": req.kind, "answer": ans, "has_reason": has_reason},
    )  # fmt: skip
