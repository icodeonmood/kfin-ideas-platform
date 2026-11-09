"""Draft, note, build and send an issue of The Ember (BLD-128). Refusals carry a safe code, never text."""

from __future__ import annotations

import datetime as dt
import secrets
from typing import Any
from zoneinfo import ZoneInfo

from psycopg.types.json import Jsonb

from comms.route import emit
from core import killswitch
from core.db import Conn
from ones.service import roles
from ones.text import OnesRefused, checked, seal, unseal

Refused = OnesRefused
IST = ZoneInfo("Asia/Kolkata")
MONTHS = (
    "January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
    "November", "December",
)  # fmt: skip
TOP_MANAGERS = 3


def month_label(month: dt.date) -> str:
    return f"{MONTHS[month.month - 1]} {month.year}"


def _month(value: Any, now: dt.datetime) -> dt.date:
    """'YYYY-MM' (or empty for this month in IST) to the first day of that month."""
    if value in (None, ""):
        local = now.astimezone(IST)
        return dt.date(local.year, local.month, 1)
    try:
        y, m = str(value).split("-")[:2]
        return dt.date(int(y), int(m), 1)
    except (ValueError, TypeError):
        raise Refused(422, "month_not_valid") from None


def _bounds(month: dt.date) -> tuple[dt.datetime, dt.datetime]:
    start = dt.datetime.combine(month, dt.time(0, 0), tzinfo=IST)
    nxt = dt.date(month.year + (month.month == 12), month.month % 12 + 1, 1)
    return start, dt.datetime.combine(nxt, dt.time(0, 0), tzinfo=IST)


def _audit(conn: Conn, actor: str, action: str, issue_id: int, after: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO audit_log (actor, action, entity, after) VALUES (%s, %s, %s, %s)",
        (f"user:{actor}", action, f"ember:{issue_id}", Jsonb(after)),
    )


def _issue(conn: Conn, issue_id: Any, *, lock: bool = False) -> dict[str, Any]:
    try:
        iid = int(issue_id)
    except (TypeError, ValueError):
        raise Refused(404, "not_found") from None
    sql = (
        "SELECT * FROM ember_issues WHERE id = %s FOR UPDATE"
        if lock
        else "SELECT * FROM ember_issues WHERE id = %s"
    )
    row = conn.execute(sql, (iid,)).fetchone()
    if row is None:
        raise Refused(404, "not_found")
    return dict(row)


def can_edit(have: set[str]) -> bool:
    return bool(have & {"admin", "core_chair"})


# --- Building an issue -------------------------------------------------------------------------------------------


def one_card(o: dict[str, Any]) -> dict[str, Any]:
    return {
        "induction_no": int(o["induction_no"]), "number": o["number"], "name": o["name"], "tier": o["tier"],
        "tier_name": o["tier_name"], "tier_colour": o["tier_colour"], "founding": o["founding"], "line": o["line"],
        "brief": o["brief"], "measures": o["measures"],
    }  # fmt: skip


def public_label(conn: Conn, subject_type: str, subject_id: str) -> str | None:
    """A delivery's label for an org-wide issue (Ember review): an idea only if everyone may see it; a group by name
    only if every member is org-visible, otherwise just its size. None means leave it out."""
    from delivery.views import _label

    if subject_type == "idea":
        row = conn.execute("SELECT visibility FROM ideas WHERE idea_id = %s", (subject_id,)).fetchone()
        return _label(conn, subject_type, subject_id) if row and row["visibility"] == "org" else None
    row = conn.execute(
        "SELECT count(*) AS n, coalesce(bool_and(visibility = 'org'), false) AS org FROM ideas WHERE cluster_id = %s",
        (subject_id,),
    ).fetchone()
    if not row or not row["n"]:
        return None
    return _label(conn, subject_type, subject_id) if row["org"] else f"A group of {int(row['n'])} ideas"


def as_sent(built: dict[str, Any], note: str) -> dict[str, Any]:
    """What is kept for the archive: Ones as references only (induction numbers), never names or briefs."""
    return {
        **built, "note": note,
        "impact": [{"induction_no": o["induction_no"]} for o in built["impact"]],
        "new_ones": [{"induction_no": o["induction_no"]} for o in built["new_ones"]],
    }  # fmt: skip


def resolve(conn: Conn, content: dict[str, Any]) -> dict[str, Any]:
    """A sent issue with its Ones read live (Ember review, DPDPA): names and briefs follow today's consent, so a
    withdrawal hides the name from the archive too. Older issues that stored names show numbers only."""
    from ones.views import public

    ones = public(conn)
    live = {int(o["induction_no"]): o for o in ones["ones"]}

    def cards(refs: list[dict[str, Any]], need_measures: bool) -> list[dict[str, Any]]:
        out = []
        for ref in refs or []:
            n = ref.get("induction_no")
            o = live.get(int(n)) if n is not None else None
            if o is not None and (o["measures"] or not need_measures):
                out.append(one_card(o))
            elif n is None and ref.get("number") is not None:  # stored before this fix: no name, ever
                out.append({**{k: ref.get(k) for k in ("number", "tier", "tier_name", "tier_colour", "founding",
                                                        "measures")}, "name": None, "line": None, "brief": None})  # fmt: skip
        return out

    return {
        **content,
        "ones_paused": ones["paused"],
        "impact": cards(content.get("impact") or [], True),
        "new_ones": cards(content.get("new_ones") or [], False),
    }


def build(conn: Conn, month: dt.date) -> dict[str, Any]:
    """Every section of the month's issue, from what everyone may already see."""
    from ones.views import _public_measures, public
    from views.common import IN_GARAGE, PICKED, PUBLIC_STAGES, SHIPPED, taxonomy_names

    start, end = _bounds(month)
    ones = public(conn)
    listed = ones["ones"]
    new_nos = {
        int(r["induction_no"])
        for r in conn.execute(
            "SELECT induction_no FROM ones WHERE status = 'active' AND inducted_at >= %s AND inducted_at < %s",
            (start, end),
        ).fetchall()
    }

    impact = [one_card(o) for o in listed if o["measures"]]
    new_ones = [one_card(o) for o in listed if int(o["induction_no"]) in new_nos]

    shipped = []
    for d in conn.execute(
        "SELECT id, subject_type, subject_id, track, state FROM deliveries WHERE (shipped_at >= %s AND shipped_at < %s) "
        "OR (resolved_at >= %s AND resolved_at < %s) ORDER BY coalesce(shipped_at, resolved_at), id",
        (start, end, start, end),
    ).fetchall():
        label = public_label(conn, d["subject_type"], d["subject_id"])
        if label is not None:
            shipped.append({"label": label, "words": "Fixed" if d["track"] == "fix" else "Shipped"})
    results = []
    for m in conn.execute(
        "SELECT m.mark, m.results, m.finance_confirmed_at, d.subject_type, d.subject_id FROM delivery_measurements m "
        "JOIN deliveries d ON d.id = m.delivery_id WHERE m.confirmed_at >= %s AND m.confirmed_at < %s "
        "ORDER BY m.confirmed_at, m.id",
        (start, end),
    ).fetchall():
        raw = {
            k: {**v, "finance_confirmed": m["finance_confirmed_at"] is not None} if k == "money" else v
            for k, v in (m["results"] or {}).items()
            if k in ("time", "money", "effort", "scale") and isinstance(v, dict)
        }
        measures = _public_measures(raw)
        label = public_label(conn, m["subject_type"], m["subject_id"])
        if measures and label is not None:
            results.append({"label": label, "mark": "30 days" if m["mark"] == "day_30" else "90 days",
                            "measures": measures})  # fmt: skip

    _, lob_names = taxonomy_names()
    by_lob = [
        {
            "lob": lob_names.get(r["lob"], "Other teams"),
            "shared": int(r["shared"]),
            "picked": int(r["picked"]),
        }
        for r in conn.execute(
            # Picked this month: when an idea first reached a picked (or later) stage, from its stage history.
            "SELECT lob, count(*) FILTER (WHERE submitted_at >= %s AND submitted_at < %s AND stage = ANY(%s)) "
            "AS shared, count(*) FILTER (WHERE picked_at >= %s AND picked_at < %s) AS picked FROM ("
            "SELECT i.lobs, i.stage, i.submitted_at, (SELECT min(h.at) FROM idea_stage_history h "
            "WHERE h.idea_uuid = i.id AND h.to_stage = ANY(%s)) AS picked_at FROM ideas i "
            "WHERE i.visibility = 'org' AND i.stage <> 'draft') x, unnest(x.lobs) AS lob GROUP BY lob ORDER BY lob",
            (start, end, list(PUBLIC_STAGES), start, end, list(PICKED + IN_GARAGE + SHIPPED)),
        ).fetchall()
        if int(r["shared"]) or int(r["picked"])
    ]

    managers = [
        str(r["name"])
        for r in conn.execute(
            "SELECT mgr.name, count(DISTINCT i.idea_id) AS n FROM users u JOIN users mgr ON mgr.id = u.manager_user_id "
            "JOIN contributor_map cm ON cm.user_id = u.id JOIN ideas i ON i.contributor_code = cm.contributor_code "
            "LEFT JOIN comms_prefs c ON c.user_id = u.id WHERE u.active AND mgr.active "
            "AND coalesce(c.manager_notes, true) AND i.visibility = 'org' AND i.stage = ANY(%s) "
            "AND i.submitted_at >= %s AND i.submitted_at < %s GROUP BY mgr.id, mgr.name ORDER BY n DESC, mgr.name "
            "LIMIT %s",
            (list(PUBLIC_STAGES), start, end, TOP_MANAGERS),
        ).fetchall()
    ]
    return {
        "month": month.isoformat(), "month_label": month_label(month), "ones_paused": ones["paused"],
        "impact": impact, "new_ones": new_ones, "shipped": shipped, "results": results, "by_lob": by_lob,
        "managers": managers, "picked_in_month": True, "coming_soon": [],
    }  # fmt: skip


# --- Actions -----------------------------------------------------------------------------------------------------


def draft(conn: Conn, actor: str, body: dict[str, Any], now: dt.datetime | None = None) -> dict[str, Any]:
    """An admin opens the month's draft (or gets the one already open)."""
    now = now or dt.datetime.now(dt.UTC)
    if "admin" not in roles(conn, actor):
        raise Refused(403, "forbidden")
    month = _month(body.get("month"), now)
    with conn.transaction():
        row = conn.execute(
            "INSERT INTO ember_issues (month, created_by) VALUES (%s, %s) ON CONFLICT (month) DO NOTHING RETURNING id",
            (month, actor),
        ).fetchone()
        if row is None:
            existing = conn.execute("SELECT id FROM ember_issues WHERE month = %s", (month,)).fetchone()
            assert existing is not None
            return {"id": int(existing["id"]), "created": False}
        _audit(conn, actor, "ember.drafted", int(row["id"]), {"month": month.isoformat()})
    return {"id": int(row["id"]), "created": True}


def set_note(conn: Conn, actor: str, issue_id: Any, body: dict[str, Any]) -> dict[str, Any]:
    """The core committee chair (or an admin) types the note "What the committee looks for". Checked like any
    text everyone will read: patterns, no colleague or client names, then the gatekeeper (before any lock)."""
    if not can_edit(roles(conn, actor)):
        raise Refused(
            404, "not_found"
        )  # drafts are only for the chair and admins: to anyone else there is none
    issue = _issue(conn, issue_id)
    if issue["state"] == "sent":
        raise Refused(409, "already_sent")
    note = checked(conn, body.get("note"), min_chars=20, max_chars=600, max_words=90, public=True)
    with conn.transaction():
        issue = _issue(conn, issue["id"], lock=True)
        if issue["state"] == "sent":
            raise Refused(409, "already_sent")
        conn.execute(  # a changed note needs the chair's approval again (Ember review)
            "UPDATE ember_issues SET chair_note_encrypted = %s, chair_note_by = %s, state = 'draft', "
            "note_approved_by = NULL, note_approved_at = NULL, ready_token = NULL WHERE id = %s",
            (seal(note, f"ember:{issue['id']}:note"), actor, issue["id"]),
        )
        _audit(conn, actor, "ember.note_saved", int(issue["id"]), {"was_ready": issue["state"] == "ready"})
    return {"id": int(issue["id"]), "note_saved": True}


def approve_note(conn: Conn, actor: str, issue_id: Any, now: dt.datetime | None = None) -> dict[str, Any]:
    """The core committee chair signs the note (Ember review): the issue becomes `ready` and gets a confirm token
    that the send must carry. An admin may draft the note; only the chair makes it the chair's."""
    now = now or dt.datetime.now(dt.UTC)
    if "core_chair" not in roles(conn, actor):
        raise Refused(403, "chair_only")
    with conn.transaction():
        issue = _issue(conn, issue_id, lock=True)
        if issue["state"] != "draft":
            raise Refused(409, "already_sent" if issue["state"] == "sent" else "already_ready")
        if not unseal(issue["chair_note_encrypted"], f"ember:{issue['id']}:note"):
            raise Refused(422, "note_required")
        conn.execute(
            "UPDATE ember_issues SET state = 'ready', note_approved_by = %s, note_approved_at = %s, ready_token = %s "
            "WHERE id = %s",
            (actor, now, secrets.token_urlsafe(24), issue["id"]),
        )
        _audit(conn, actor, "ember.note_approved", int(issue["id"]), {})
    return {"id": int(issue["id"]), "state": "ready"}


def send(
    conn: Conn, actor: str, issue_id: Any, body: dict[str, Any] | None = None, now: dt.datetime | None = None
) -> dict[str, Any]:
    """An admin sends a `ready` issue to everyone, carrying the confirm token from the chair's approval. The admin
    may not be the person who wrote or approved the note (Ember review). What it says is kept for the archive,
    with Ones stored as references so names follow live consent."""
    now = now or dt.datetime.now(dt.UTC)
    body = body or {}
    if "admin" not in roles(conn, actor):
        raise Refused(403, "forbidden")
    if not killswitch.is_on("ember.send", conn):
        raise Refused(503, "ember_paused")
    if not killswitch.is_on("ones.public", conn):
        raise Refused(503, "ones_paused")  # the issue names Ones: nothing about them goes out while they rest
    with conn.transaction():
        issue = _issue(conn, issue_id, lock=True)
        if issue["state"] == "sent":
            raise Refused(409, "already_sent")
        if issue["state"] != "ready":
            raise Refused(409, "not_ready")
        if actor in (str(issue["chair_note_by"]), str(issue["note_approved_by"])):
            raise Refused(403, "own_note")
        token = str(body.get("confirm_token") or "")
        if not issue["ready_token"] or not secrets.compare_digest(token, str(issue["ready_token"])):
            raise Refused(409, "confirm_stale")
        note = unseal(issue["chair_note_encrypted"], f"ember:{issue['id']}:note")
        if not note:
            raise Refused(422, "note_required")
        content = as_sent(build(conn, issue["month"]), note)
        conn.execute(
            "UPDATE ember_issues SET state = 'sent', content = %s, sent_by = %s, sent_at = %s, "
            "chair_note_encrypted = NULL, ready_token = NULL WHERE id = %s",
            (Jsonb(content), actor, now, issue["id"]),
        )
        emit(conn, "ember.issue", {"issue_id": int(issue["id"])})
        _audit(conn, actor, "ember.sent", int(issue["id"]), {"month": issue["month"].isoformat()})
    return {"id": int(issue["id"]), "state": "sent"}


# --- Reading -----------------------------------------------------------------------------------------------------


def archive(conn: Conn) -> dict[str, Any]:
    rows = conn.execute(
        "SELECT id, month, sent_at FROM ember_issues WHERE state = 'sent' ORDER BY month DESC"
    ).fetchall()
    return {
        "issues": [
            {"id": int(r["id"]), "month_label": month_label(r["month"]), "sent_at": r["sent_at"].isoformat()}
            for r in rows
        ]
    }


def view(conn: Conn, viewer: str, issue_id: Any) -> dict[str, Any]:
    """A sent issue for anyone signed in; a draft (built live, with its note) only for the chair and admins."""
    issue = _issue(conn, issue_id)
    if issue["state"] == "sent":
        return {
            "id": int(issue["id"]),
            "state": "sent",
            "sent_at": issue["sent_at"].isoformat(),
            "note_approved": True,
            **resolve(conn, issue["content"]),
        }
    have = roles(conn, viewer)
    if not can_edit(have):
        raise Refused(404, "not_found")
    note = unseal(issue["chair_note_encrypted"], f"ember:{issue['id']}:note")
    ready = issue["state"] == "ready"
    own = viewer in (str(issue["chair_note_by"]), str(issue["note_approved_by"]))
    can_send = "admin" in have and ready and not own
    return {
        "id": int(issue["id"]), "state": issue["state"], "note": note, "note_approved": ready,
        "can_approve_note": "core_chair" in have and issue["state"] == "draft" and bool(note),
        "can_send": can_send, "confirm_token": issue["ready_token"] if can_send else None,
        "own_note": "admin" in have and ready and own,
        "ember_paused": not killswitch.is_on("ember.send", conn), **build(conn, issue["month"]),
    }  # fmt: skip


def current_draft(conn: Conn, viewer: str) -> dict[str, Any]:
    """The newest draft, if there is one, for the chair and admins."""
    if not can_edit(roles(conn, viewer)):
        return {"id": None}  # other committee members see no draft (the chair writes the note)
    row = conn.execute(
        "SELECT id FROM ember_issues WHERE state IN ('draft', 'ready') ORDER BY month DESC LIMIT 1"
    ).fetchone()
    return {"id": int(row["id"]) if row else None}
