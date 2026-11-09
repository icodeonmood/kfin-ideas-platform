"""The Ones module: proposals, approvals and the admin member's carry-out (DEC-040, DEC-042, DEC-044, DEC-045,
DEC-067, DEC-073, DEC-076, DEC-082, DEC-084).

Every change goes through a proposal:
- **Propose.** A core committee member or the CEO (sponsor) proposes an inclusion; core committee members propose
  removals, tier changes and legend numbers. A One proposes their own impact brief.
- **Approve.** The chair approves (never their own proposal), or any core committee member records a majority
  reached at a meeting, with its date. Agents never approve anything (non-negotiable 5).
- **Carry out.** The admin member carries it out, which writes the change and sends the message. An impact brief
  takes effect on approval: there is nothing to carry out.

A tier change also needs the committee's message to the One (required), and may carry the CEO's and colleagues'
(DEC-084). Every message passes the checks in `ones.text` before it is stored. Every step is audited with IDs and
codes only; no text is ever logged.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from comms.route import emit
from core.db import Conn
from ones import numbers
from ones.text import OnesRefused, checked, checked_parts, seal, seal_json, unseal

KINDS = ("include", "remove", "tier_up", "tier_down", "impact_brief", "legend")
WAYS_IN = ("accepted_idea", "sponsored", "founding")
MESSAGE_FROM = ("committee", "ceo", "peer")
MEASURE_UNITS: dict[str, tuple[str, ...]] = {
    "time": ("hours a month", "days a year"),
    "money": ("rupees a year", "rupees a month"),
    "effort": ("errors avoided a month", "corrections avoided a month", "calls avoided a month"),
    "scale": ("investors", "distributors", "colleagues", "transactions a month", "folios a month"),
}
MAX_MEASURE = 10**12


def roles(conn: Conn, user_id: str) -> set[str]:
    """The person's live grants. The web app checked the capability; the worker checks again (defence in depth)."""
    rows = conn.execute(
        "SELECT g.role FROM role_grants g JOIN users u ON u.id = g.user_id WHERE g.user_id = %s AND u.active "
        "AND g.valid_from <= now() AND (g.valid_to IS NULL OR g.valid_to > now())",
        (user_id,),
    ).fetchall()
    return {str(r["role"]) for r in rows}


def _need(conn: Conn, user_id: str, allowed: set[str]) -> set[str]:
    have = roles(conn, user_id)
    if not have & allowed:
        raise OnesRefused(403, "forbidden")
    return have


def _audit(conn: Conn, actor: str, action: str, entity: str, after: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO audit_log (actor, action, entity, after) VALUES (%s, %s, %s, %s)",
        (f"user:{actor}", action, entity, Jsonb(after)),
    )


def _user_by_email(conn: Conn, email: str) -> str:
    row = conn.execute(
        "SELECT id FROM users WHERE lower(email) = lower(%s) AND active", (email.strip(),)
    ).fetchone()
    if row is None:
        raise OnesRefused(404, "person_not_found")
    return str(row["id"])


def _one(conn: Conn, one_id: int, *, lock: bool = False) -> dict[str, Any]:
    if lock:
        row = conn.execute("SELECT * FROM ones WHERE id = %s FOR UPDATE", (one_id,)).fetchone()
    else:
        row = conn.execute("SELECT * FROM ones WHERE id = %s", (one_id,)).fetchone()
    if row is None:
        raise OnesRefused(404, "not_found")
    return dict(row)


def _int(value: Any, code: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise OnesRefused(400, code) from None


# --- Propose ---------------------------------------------------------------------------------------------------


def propose(conn: Conn, actor: str, body: dict[str, Any], now: dt.datetime | None = None) -> dict[str, Any]:
    """A committee member's (or the CEO's) proposal. Text checks run first, outside any transaction."""
    now = now or dt.datetime.now(dt.UTC)
    kind = body.get("kind")
    if kind not in KINDS or kind == "impact_brief":
        raise OnesRefused(400, "kind_required")
    have = _need(conn, actor, {"core_committee", "core_chair", "ceo"})
    if kind != "include" and not have & {"core_committee", "core_chair"}:
        raise OnesRefused(403, "forbidden")  # the CEO sponsors inclusions; the committee handles the rest

    reason = checked(conn, body.get("reason"), min_chars=10, max_chars=400)
    title = None
    way_in = idea_id = None
    tier_to = None
    one: dict[str, Any] | None = None
    if kind == "include":
        way_in = body.get("way_in")
        if way_in not in WAYS_IN:
            raise OnesRefused(400, "way_in_required")
        subject = _user_by_email(conn, str(body.get("email") or ""))
        if way_in == "accepted_idea":
            idea_id = str(body.get("idea_id") or "").strip().upper()
            owner = conn.execute(
                "SELECT 1 FROM ideas i JOIN contributor_map m ON m.contributor_code = i.contributor_code "
                "WHERE i.idea_id = %s AND m.user_id = %s",
                (idea_id, subject),
            ).fetchone()
            if owner is None:
                raise OnesRefused(422, "idea_not_theirs")
        else:
            title = checked(conn, body.get("title"), min_chars=10, max_chars=120)
        current = conn.execute("SELECT status FROM ones WHERE user_id = %s", (subject,)).fetchone()
        if current and current["status"] == "active":
            raise OnesRefused(409, "already_a_one")
    else:
        one = _one(conn, _int(body.get("one_id"), "one_required"))
        if one["status"] != "active":
            raise OnesRefused(409, "not_active")
        subject = str(one["user_id"])
        if kind in ("tier_up", "tier_down"):
            tier_to = _int(body.get("tier_to"), "tier_required")
            if (
                not 1 <= tier_to <= 7
                or (kind == "tier_up") != (tier_to > one["tier"])
                or tier_to == one["tier"]
            ):
                raise OnesRefused(422, "tier_not_valid")
        legend = conn.execute("SELECT 1 FROM one_legend_numbers WHERE one_id = %s", (one["id"],)).fetchone()
        if kind == "legend" and legend:
            raise OnesRefused(409, "already_a_legend")
    if subject == actor:
        raise OnesRefused(409, "own_proposal")

    with conn.transaction():
        try:
            row = conn.execute(
                "INSERT INTO one_proposals (kind, one_id, subject_user_id, way_in, idea_id, tier_to, proposed_by, "
                "proposed_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                (kind, one["id"] if one else None, subject, way_in, idea_id, tier_to, actor, now),
            ).fetchone()
        except psycopg.errors.UniqueViolation:
            raise OnesRefused(409, "already_proposed") from None
        assert row is not None
        pid = int(row["id"])
        conn.execute(
            "UPDATE one_proposals SET reason_encrypted = %s, text_encrypted = %s WHERE id = %s",
            (seal(reason, f"one_proposal:{pid}:reason"), seal(title, f"one_proposal:{pid}:text"), pid),
        )
        _audit(
            conn,
            actor,
            "ones.proposed",
            f"one_proposal:{pid}",
            {"kind": kind, "way_in": way_in, "tier_to": tier_to},
        )
    return {"id": pid, "state": "proposed"}


def propose_brief(conn: Conn, user_id: str, text: Any, now: dt.datetime | None = None) -> dict[str, Any]:
    """A One proposes their own impact brief (up to 30 words); the committee approves it (DEC-073)."""
    now = now or dt.datetime.now(dt.UTC)
    one = conn.execute("SELECT * FROM ones WHERE user_id = %s AND status = 'active'", (user_id,)).fetchone()
    if one is None:
        raise OnesRefused(403, "not_a_one")
    brief = checked(conn, text, min_chars=10, max_chars=240, max_words=30)
    with conn.transaction():
        # A new draft replaces one still waiting for the committee.
        conn.execute(
            "UPDATE one_proposals SET state = 'withdrawn' WHERE subject_user_id = %s AND kind = 'impact_brief' "
            "AND state = 'proposed'",
            (user_id,),
        )
        row = conn.execute(
            "INSERT INTO one_proposals (kind, one_id, subject_user_id, proposed_by, proposed_at) "
            "VALUES ('impact_brief', %s, %s, %s, %s) RETURNING id",
            (one["id"], user_id, user_id, now),
        ).fetchone()
        assert row is not None
        pid = int(row["id"])
        conn.execute(
            "UPDATE one_proposals SET text_encrypted = %s WHERE id = %s",
            (seal(brief, f"one_proposal:{pid}:text"), pid),
        )
        _audit(conn, user_id, "ones.brief_proposed", f"one_proposal:{pid}", {"one_id": one["id"]})
    return {"id": pid, "state": "proposed"}


# --- Messages for a tier change (DEC-084) -------------------------------------------------------------------------


def add_message(
    conn: Conn, actor: str, proposal_id: int, body: dict[str, Any], now: dt.datetime | None = None
) -> dict[str, Any]:
    """A message to the One for a tier change: the committee's (required before carry-out), the CEO's (optional)
    or a colleague's (optional, invited from the console)."""
    now = now or dt.datetime.now(dt.UTC)
    who = body.get("from")
    if who not in MESSAGE_FROM:
        raise OnesRefused(400, "from_required")
    p = conn.execute("SELECT * FROM one_proposals WHERE id = %s", (proposal_id,)).fetchone()
    if p is None or p["kind"] not in ("tier_up", "tier_down"):
        raise OnesRefused(404, "not_found")
    if p["state"] not in ("proposed", "approved"):
        raise OnesRefused(409, "not_open")
    have = roles(conn, actor)
    if who == "committee" and not have & {"core_committee", "core_chair"}:
        raise OnesRefused(403, "forbidden")
    if who == "ceo" and "ceo" not in have:
        raise OnesRefused(403, "forbidden")
    if who == "peer":
        invited = conn.execute(
            "SELECT 1 FROM one_message_invites WHERE proposal_id = %s AND user_id = %s", (proposal_id, actor)
        ).fetchone()
        if invited is None:
            raise OnesRefused(403, "not_invited")
    if str(p["subject_user_id"]) == actor:
        raise OnesRefused(409, "own_proposal")
    text = checked(conn, body.get("text"), min_chars=10, max_chars=600)
    with conn.transaction():
        try:
            row = conn.execute(
                "INSERT INTO one_messages (proposal_id, author_user_id, author_role, written_at) "
                "VALUES (%s, %s, %s, %s) RETURNING id",
                (proposal_id, actor, who, now),
            ).fetchone()
        except psycopg.errors.UniqueViolation:
            raise OnesRefused(409, "already_written") from None
        assert row is not None
        mid = int(row["id"])
        conn.execute(
            "UPDATE one_messages SET text_encrypted = %s WHERE id = %s",
            (seal(text, f"one_message:{mid}"), mid),
        )
        _audit(
            conn, actor, "ones.message_added", f"one_proposal:{proposal_id}", {"from": who, "message_id": mid}
        )
    return {"id": mid}


def invite_peer(conn: Conn, actor: str, proposal_id: int, email: str) -> dict[str, Any]:
    """A committee member invites a colleague to write a message for the One's tier change."""
    _need(conn, actor, {"core_committee", "core_chair"})
    p = conn.execute("SELECT * FROM one_proposals WHERE id = %s", (proposal_id,)).fetchone()
    if p is None or p["kind"] not in ("tier_up", "tier_down"):
        raise OnesRefused(404, "not_found")
    if p["state"] not in ("proposed", "approved"):
        raise OnesRefused(409, "not_open")
    peer = _user_by_email(conn, email)
    if peer == str(p["subject_user_id"]):
        raise OnesRefused(409, "own_proposal")
    with conn.transaction():
        conn.execute(
            "INSERT INTO one_message_invites (proposal_id, user_id, invited_by) VALUES (%s, %s, %s) "
            "ON CONFLICT DO NOTHING",
            (proposal_id, peer, actor),
        )
        emit(conn, "ones.message_invited", {"current_owner_ids": [peer], "proposal_id": proposal_id})
        _audit(conn, actor, "ones.peer_invited", f"one_proposal:{proposal_id}", {"invited": peer})
    return {"invited": True}


# --- Approve, decline, withdraw --------------------------------------------------------------------------------


def decide(
    conn: Conn, actor: str, proposal_id: int, body: dict[str, Any], now: dt.datetime | None = None
) -> dict[str, Any]:
    """Approve or decline: the chair, or a core committee member recording a meeting majority with its date."""
    now = now or dt.datetime.now(dt.UTC)
    verdict, how = body.get("verdict"), body.get("how")
    if verdict not in ("approve", "decline") or how not in ("chair", "majority"):
        raise OnesRefused(400, "verdict_required")
    have = _need(conn, actor, {"core_committee", "core_chair"})
    meeting_on: dt.date | None = None
    if how == "chair" and "core_chair" not in have:
        raise OnesRefused(403, "chair_only")
    if how == "majority":
        try:
            meeting_on = dt.date.fromisoformat(str(body.get("meeting_on") or ""))
        except ValueError:
            raise OnesRefused(400, "meeting_date_required") from None
        if meeting_on > now.date() or meeting_on < now.date() - dt.timedelta(days=90):
            raise OnesRefused(422, "meeting_date_not_valid")
    with conn.transaction():
        p = conn.execute("SELECT * FROM one_proposals WHERE id = %s FOR UPDATE", (proposal_id,)).fetchone()
        if p is None:
            raise OnesRefused(404, "not_found")
        if p["state"] != "proposed":
            raise OnesRefused(409, "not_open")
        if how == "chair" and str(p["proposed_by"]) == actor:
            raise OnesRefused(409, "own_proposal")  # the chair never approves their own proposal alone
        if str(p["subject_user_id"]) == actor:
            raise OnesRefused(409, "own_proposal")
        state = "approved" if verdict == "approve" else "declined"
        conn.execute(
            "UPDATE one_proposals SET state = %s, approval = %s, meeting_on = %s, decided_by = %s, decided_at = %s "
            "WHERE id = %s",
            (state, how, meeting_on, actor, now, proposal_id),
        )
        _audit(conn, actor, f"ones.{state}", f"one_proposal:{proposal_id}", {"kind": p["kind"], "how": how})
        if state == "approved" and p["kind"] == "impact_brief":
            _apply_brief(conn, dict(p), now)  # a brief takes effect on approval (DEC-073)
            conn.execute(
                "UPDATE one_proposals SET state = 'carried_out', carried_out_by = %s, carried_out_at = %s "
                "WHERE id = %s",
                (actor, now, proposal_id),
            )
            state = "carried_out"
    return {"id": proposal_id, "state": state}


def withdraw(conn: Conn, actor: str, proposal_id: int) -> dict[str, Any]:
    with conn.transaction():
        p = conn.execute("SELECT * FROM one_proposals WHERE id = %s FOR UPDATE", (proposal_id,)).fetchone()
        if p is None:
            raise OnesRefused(404, "not_found")
        if str(p["proposed_by"]) != actor:
            raise OnesRefused(403, "forbidden")
        if p["state"] not in ("proposed", "approved"):
            raise OnesRefused(409, "not_open")
        conn.execute("UPDATE one_proposals SET state = 'withdrawn' WHERE id = %s", (proposal_id,))
        _audit(conn, actor, "ones.withdrawn", f"one_proposal:{proposal_id}", {"kind": p["kind"]})
    return {"id": proposal_id, "state": "withdrawn"}


def _apply_brief(conn: Conn, p: dict[str, Any], now: dt.datetime) -> None:
    text = unseal(p["text_encrypted"], f"one_proposal:{p['id']}:text")
    if text is None:
        raise OnesRefused(409, "brief_unreadable")
    conn.execute(
        "UPDATE ones SET brief_encrypted = %s, brief_approved_at = %s WHERE id = %s",
        (seal(text, f"one:{p['one_id']}:brief"), now, p["one_id"]),
    )


# --- Carry out ----------------------------------------------------------------------------------------------------


def carry_out(conn: Conn, actor: str, proposal_id: int, now: dt.datetime | None = None) -> dict[str, Any]:
    """The admin member carries out an approved proposal: the change, its audit row and the message, at once."""
    now = now or dt.datetime.now(dt.UTC)
    _need(conn, actor, {"admin"})
    with conn.transaction():
        p = conn.execute("SELECT * FROM one_proposals WHERE id = %s FOR UPDATE", (proposal_id,)).fetchone()
        if p is None:
            raise OnesRefused(404, "not_found")
        p = dict(p)
        if p["state"] != "approved" or p["kind"] == "impact_brief":
            raise OnesRefused(409, "not_approved")
        if str(p["subject_user_id"]) == actor:
            raise OnesRefused(409, "own_proposal")
        out: dict[str, Any]
        if p["kind"] == "include":
            out = _induct(conn, p, now)
        elif p["kind"] == "remove":
            out = _retire(conn, p, now)
        elif p["kind"] in ("tier_up", "tier_down"):
            out = _change_tier(conn, p, now)
        else:
            out = _legend(conn, p, now)
        conn.execute(
            "UPDATE one_proposals SET state = 'carried_out', carried_out_by = %s, carried_out_at = %s WHERE id = %s",
            (actor, now, proposal_id),
        )
        _audit(conn, actor, "ones.carried_out", f"one_proposal:{proposal_id}", {"kind": p["kind"], **out})
    return {"id": proposal_id, "state": "carried_out", **out}


def _induct(conn: Conn, p: dict[str, Any], now: dt.datetime) -> dict[str, Any]:
    user = str(p["subject_user_id"])
    existing = conn.execute("SELECT * FROM ones WHERE user_id = %s FOR UPDATE", (user,)).fetchone()
    if existing and existing["status"] == "active":
        raise OnesRefused(409, "already_a_one")
    title = unseal(p["text_encrypted"], f"one_proposal:{p['id']}:text")
    if existing:
        one_id = int(existing["id"])  # a returning One comes back to the same record and keeps their spark
        number = numbers.next_number(conn, one_id, now)
        conn.execute(
            "UPDATE ones SET status = 'active', number = %s, way_in = %s, idea_id = %s, title_encrypted = %s, "
            "inducted_at = %s, swap_until = %s, retired_at = NULL, announced_at = NULL WHERE id = %s",
            (number, p["way_in"], p["idea_id"], seal(title, f"one:{one_id}:title"), now,
             now + numbers.SWAP_WINDOW, one_id),
        )  # fmt: skip
    else:
        n = conn.execute("SELECT next_number('ONE', '') AS n").fetchone()
        assert n is not None
        number = numbers.next_number(conn, 0, now)
        row = conn.execute(
            "INSERT INTO ones (induction_no, user_id, number, way_in, idea_id, inducted_at, swap_until) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (n["n"], user, number, p["way_in"], p["idea_id"], now, now + numbers.SWAP_WINDOW),
        ).fetchone()
        assert row is not None
        one_id = int(row["id"])
        conn.execute(
            "UPDATE ones SET title_encrypted = %s WHERE id = %s", (seal(title, f"one:{one_id}:title"), one_id)
        )
    numbers.wear(conn, one_id, number, "allocated", now)
    conn.execute("UPDATE one_proposals SET one_id = %s WHERE id = %s", (one_id, p["id"]))
    emit(conn, "ones.inducted", {"current_owner_ids": [user], "one_id": one_id})
    return {"one_id": one_id, "number": number}


def _retire(conn: Conn, p: dict[str, Any], now: dt.datetime) -> dict[str, Any]:
    one = _one(conn, int(p["one_id"]), lock=True)
    if one["status"] != "active":
        raise OnesRefused(409, "not_active")
    numbers.release(conn, one["id"], now)
    conn.execute(
        "UPDATE ones SET status = 'retired', number = NULL, retired_at = %s WHERE id = %s", (now, one["id"])
    )
    emit(
        conn,
        "ones.removed",
        {"current_owner_ids": [str(one["user_id"])], "one_id": one["id"], "proposal_id": p["id"]},
    )
    return {"one_id": one["id"], "number": one["number"]}


def _change_tier(conn: Conn, p: dict[str, Any], now: dt.datetime) -> dict[str, Any]:
    one = _one(conn, int(p["one_id"]), lock=True)
    if one["status"] != "active":
        raise OnesRefused(409, "not_active")
    has_committee_message = conn.execute(
        "SELECT 1 FROM one_messages WHERE proposal_id = %s AND author_role = 'committee'", (p["id"],)
    ).fetchone()
    if has_committee_message is None:
        raise OnesRefused(409, "committee_message_required")  # DEC-084
    conn.execute("UPDATE ones SET tier = %s WHERE id = %s", (p["tier_to"], one["id"]))
    conn.execute(
        "INSERT INTO one_glow_ups (one_id, proposal_id, tier_from, tier_to, created_at) VALUES (%s, %s, %s, %s, %s)",
        (one["id"], p["id"], one["tier"], p["tier_to"], now),
    )
    emit(
        conn,
        "ones.tier_changed",
        {"current_owner_ids": [str(one["user_id"])], "one_id": one["id"], "proposal_id": p["id"]},
    )
    return {"one_id": one["id"], "tier_from": one["tier"], "tier_to": p["tier_to"]}


def _legend(conn: Conn, p: dict[str, Any], now: dt.datetime) -> dict[str, Any]:
    one = _one(conn, int(p["one_id"]), lock=True)
    if one["status"] != "active" or one["number"] is None:
        raise OnesRefused(409, "not_active")
    this_year = conn.execute(
        "SELECT 1 FROM one_legend_numbers WHERE date_part('year', retired_on) = %s", (now.year,)
    ).fetchone()
    if this_year:
        raise OnesRefused(409, "legend_this_year")  # at most one a year (DEC-041)
    conn.execute(
        "INSERT INTO one_legend_numbers (number, one_id, retired_on) VALUES (%s, %s, %s)",
        (one["number"], one["id"], now.date()),
    )
    return {"one_id": one["id"], "number": one["number"]}


def induct_from_decision(
    conn: Conn, idea_id: str, decided_by: str, meeting_on: dt.date, now: dt.datetime | None = None
) -> int | None:
    """For the committee flow: when the core committee accepts an idea after its presentation, its owner is
    proposed as a One with that decision as the approval (a majority at the meeting). The admin member still
    carries it out. Returns the proposal ID, or None if the owner is already a One or already proposed. Call it
    inside the decision's own transaction."""
    now = now or dt.datetime.now(dt.UTC)
    owner = conn.execute(
        "SELECT m.user_id FROM ideas i JOIN contributor_map m ON m.contributor_code = i.contributor_code "
        "WHERE i.idea_id = %s",
        (idea_id,),
    ).fetchone()
    if owner is None:
        return None
    user = str(owner["user_id"])
    active = conn.execute("SELECT 1 FROM ones WHERE user_id = %s AND status = 'active'", (user,)).fetchone()
    if active:
        return None
    row = conn.execute(
        "INSERT INTO one_proposals (kind, subject_user_id, way_in, idea_id, proposed_by, proposed_at, state, "
        "approval, meeting_on, decided_by, decided_at) VALUES ('include', %s, 'accepted_idea', %s, %s, %s, "
        "'approved', 'majority', %s, %s, %s) ON CONFLICT DO NOTHING RETURNING id",
        (user, idea_id, decided_by, now, meeting_on, decided_by, now),
    ).fetchone()
    if row is None:
        return None
    _audit(conn, decided_by, "ones.proposed_from_decision", f"one_proposal:{row['id']}", {"idea_id": idea_id})
    return int(row["id"])


# --- The One's own choices ---------------------------------------------------------------------------------------


def swap_number(conn: Conn, user_id: str, number: Any, now: dt.datetime | None = None) -> dict[str, Any]:
    """A One chooses a free number within 30 days of induction, first come first served (DEC-067)."""
    now = now or dt.datetime.now(dt.UTC)
    # Membership first, so a non-One never learns what a valid body looks like (BLD-108).
    if not conn.execute("SELECT 1 FROM ones WHERE user_id = %s AND status = 'active'", (user_id,)).fetchone():
        raise OnesRefused(403, "not_a_one")
    n = _int(number, "number_required")
    if not numbers.LOW <= n <= numbers.HIGH:
        raise OnesRefused(422, "number_out_of_range")
    try:
        with conn.transaction():
            one = conn.execute(
                "SELECT * FROM ones WHERE user_id = %s AND status = 'active' FOR UPDATE", (user_id,)
            ).fetchone()
            if one is None:
                raise OnesRefused(403, "not_a_one")
            if now > one["swap_until"]:
                raise OnesRefused(409, "swap_window_closed")
            if conn.execute("SELECT 1 FROM one_legend_numbers WHERE one_id = %s", (one["id"],)).fetchone():
                raise OnesRefused(409, "legend_number")
            if one["number"] == n:
                return {"number": n}
            if not numbers.is_free(conn, n, one["id"], now):
                raise OnesRefused(409, "number_taken")
            numbers.wear(conn, one["id"], n, "chosen", now)
            conn.execute("UPDATE ones SET number = %s WHERE id = %s", (n, one["id"]))
            _audit(conn, user_id, "ones.number_changed", f"one:{one['id']}", {"from": one["number"], "to": n})
    except psycopg.errors.UniqueViolation:
        raise OnesRefused(409, "number_taken") from None  # someone claimed it in the same moment
    return {"number": n}


def glow_up_seen(conn: Conn, user_id: str, glow_id: int, now: dt.datetime | None = None) -> bool:
    """The One has watched their glow-up; it does not play again."""
    now = now or dt.datetime.now(dt.UTC)
    row = conn.execute(
        "UPDATE one_glow_ups g SET seen_at = %s FROM ones o WHERE g.id = %s AND g.one_id = o.id AND o.user_id = %s "
        "AND g.seen_at IS NULL RETURNING g.id",
        (now, glow_id, user_id),
    ).fetchone()
    return row is not None


# --- Admin member: measures, screens, announcements ----------------------------------------------------------------


def set_measures(conn: Conn, actor: str, one_id: int, body: dict[str, Any]) -> dict[str, Any]:
    """Measured impact (DEC-071), entered by the admin member. Values and fixed units only, never free text. Money
    shows only once Finance has confirmed it."""
    _need(conn, actor, {"admin"})
    out: dict[str, Any] = {}
    for key, units in MEASURE_UNITS.items():
        m = body.get(key)
        if m in (None, {}):
            continue
        if not isinstance(m, dict) or m.get("unit") not in units:
            raise OnesRefused(422, f"{key}_not_valid")
        value = _int(m.get("value"), f"{key}_not_valid")
        if not 0 <= value <= MAX_MEASURE:
            raise OnesRefused(422, f"{key}_not_valid")
        out[key] = {"value": value, "unit": m["unit"]}
        if key == "money":
            out[key]["finance_confirmed"] = m.get("finance_confirmed") is True
    with conn.transaction():
        one = _one(conn, one_id, lock=True)
        conn.execute("UPDATE ones SET measures = %s WHERE id = %s", (Jsonb(out), one["id"]))
        _audit(conn, actor, "ones.measures_set", f"one:{one_id}", {"keys": sorted(out)})
    return {"measures": out}


def set_screen_mode(conn: Conn, actor: str, mode: Any) -> dict[str, Any]:
    """Static sky by default; ambient mode for events (DEC-069)."""
    have = _need(conn, actor, {"admin"})
    del have
    if mode not in ("static", "ambient"):
        raise OnesRefused(400, "mode_required")
    with conn.transaction():
        conn.execute(
            "UPDATE screen_settings SET mode = %s, changed_by = %s, changed_at = now() WHERE id",
            (mode, actor),
        )
        _audit(conn, actor, "ones.screen_mode", "screen_settings", {"mode": mode})
    return {"mode": mode}


def announce(conn: Conn, actor: str, now: dt.datetime | None = None) -> dict[str, Any]:
    """After a committee meeting: tell everyone about the Ones inducted since the last announcement (DEC-056)."""
    now = now or dt.datetime.now(dt.UTC)
    _need(conn, actor, {"admin"})
    with conn.transaction():
        rows = conn.execute(
            "SELECT id FROM ones WHERE status = 'active' AND announced_at IS NULL ORDER BY inducted_at, id FOR UPDATE"
        ).fetchall()
        ids = [int(r["id"]) for r in rows]
        if not ids:
            raise OnesRefused(409, "nothing_to_announce")
        conn.execute("UPDATE ones SET announced_at = %s WHERE id = ANY(%s)", (now, ids))
        emit(conn, "ones.announced", {"one_ids": ids})
        _audit(conn, actor, "ones.announced", "ones", {"one_ids": ids})
    return {"announced": len(ids)}


def award(
    conn: Conn, actor: str, one_id: int, body: dict[str, Any], now: dt.datetime | None = None
) -> dict[str, Any]:
    """The Ones Night (DEC-085): mark an impact award (time, money, effort or scale) for the year. The legend number
    goes through its own proposal."""
    now = now or dt.datetime.now(dt.UTC)
    _need(conn, actor, {"admin"})
    category = body.get("category")
    if category not in MEASURE_UNITS:
        raise OnesRefused(400, "category_required")
    year = _int(body.get("year") or now.year, "year_required")
    with conn.transaction():
        _one(conn, one_id)
        try:
            conn.execute(
                "INSERT INTO one_awards (one_id, year, category, awarded_by) VALUES (%s, %s, %s, %s)",
                (one_id, year, category, actor),
            )
        except psycopg.errors.UniqueViolation:
            raise OnesRefused(409, "award_given") from None
        _audit(conn, actor, "ones.award", f"one:{one_id}", {"year": year, "category": category})
    return {"one_id": one_id, "year": year, "category": category}


# --- The Showcase brief (DEC-086) -------------------------------------------------------------------------------

SHOWCASE_PARTS = ("idea", "proposed_impact", "progress", "impact_so_far", "timelines", "team", "help")


def save_showcase(
    conn: Conn, user_id: str, body: dict[str, Any], now: dt.datetime | None = None
) -> dict[str, Any]:
    """The One's own words for their Showcase brief. Parts left empty show what their record says."""
    now = now or dt.datetime.now(dt.UTC)
    one = conn.execute("SELECT id FROM ones WHERE user_id = %s AND status = 'active'", (user_id,)).fetchone()
    if one is None:
        raise OnesRefused(403, "not_a_one")
    parts = checked_parts(conn, body, SHOWCASE_PARTS)
    with conn.transaction():
        conn.execute(
            "INSERT INTO one_showcase_briefs (one_id, parts_encrypted, updated_at) VALUES (%s, %s, %s) "
            "ON CONFLICT (one_id) DO UPDATE SET parts_encrypted = excluded.parts_encrypted, updated_at = excluded.updated_at",
            (one["id"], seal_json(parts, f"one:{one['id']}:showcase"), now),
        )
        _audit(
            conn,
            user_id,
            "ones.showcase_saved",
            f"one:{one['id']}",
            {"filled": sorted(k for k, v in parts.items() if v)},
        )
    return {"saved": True}
