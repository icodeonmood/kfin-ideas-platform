"""`delivery.tick`, daily (§4.9 to §4.11): reminders and escalations for deliveries in flight. Each sends at most
once per item per day (or once in all, for escalations). Notifications carry IDs and codes only.

- A measurement due within 3 days, or overdue, and not yet filled: the owner is reminded (at most weekly).
- A measurement filled but not confirmed for 5 working days: the sponsor is reminded (at most weekly).
- Fix track (§4.10): every Friday the owner gets a check-in; an overdue milestone tells its owner, the delivery's
  owner and the sponsor (once); a plan more than 10 working days late goes to the core committee chair (once).
- Build track (§4.9): blocked for more than 10 working days flags it to the sponsor (once per block).
"""

from __future__ import annotations

import datetime as dt
from typing import Any
from zoneinfo import ZoneInfo

from comms.route import emit
from core.db import Conn
from core.logging import get_logger
from delivery.service import _role_users
from sla.calendar import add_working_days

log = get_logger("delivery.jobs")
IST = ZoneInfo("Asia/Kolkata")
WEEK = dt.timedelta(days=7)


def _remind_due(conn: Conn, now: dt.datetime, today: dt.date) -> int:
    rows = conn.execute(
        "SELECT m.id, m.mark, m.delivery_id, d.subject_id, d.owner_user_id FROM delivery_measurements m "
        "JOIN deliveries d ON d.id = m.delivery_id WHERE m.filled_at IS NULL AND m.due_at <= %s "
        "AND d.state IN ('shipped', 'resolved') AND (m.reminded_on IS NULL OR m.reminded_on <= %s)",
        (now + dt.timedelta(days=3), today - WEEK),
    ).fetchall()
    for r in rows:
        if r["owner_user_id"]:
            emit(conn, "delivery.measure_due", {"delivery_id": r["delivery_id"], "subject_id": r["subject_id"],
                                                "mark": r["mark"], "current_owner_ids": [str(r["owner_user_id"])]})  # fmt: skip
        conn.execute("UPDATE delivery_measurements SET reminded_on = %s WHERE id = %s", (today, r["id"]))
    return len(rows)


def _remind_confirm(conn: Conn, now: dt.datetime, today: dt.date) -> int:
    rows = conn.execute(
        "SELECT m.id, m.mark, m.filled_at, m.delivery_id, d.subject_id, d.sponsor_user_id FROM delivery_measurements m "
        "JOIN deliveries d ON d.id = m.delivery_id WHERE m.filled_at IS NOT NULL AND m.confirmed_at IS NULL "
        "AND d.state IN ('shipped', 'resolved') AND (m.reminded_on IS NULL OR m.reminded_on <= %s)",
        (today - WEEK,),
    ).fetchall()
    sent = 0
    for r in rows:
        if add_working_days(r["filled_at"], 5) > now or not r["sponsor_user_id"]:
            continue
        emit(conn, "delivery.measure_to_confirm", {"delivery_id": r["delivery_id"], "subject_id": r["subject_id"],
                                                   "mark": r["mark"], "current_owner_ids": [str(r["sponsor_user_id"])]})  # fmt: skip
        conn.execute("UPDATE delivery_measurements SET reminded_on = %s WHERE id = %s", (today, r["id"]))
        sent += 1
    return sent


def _fix_checkins(conn: Conn, today: dt.date) -> int:
    if today.weekday() != 4:  # Fridays (§4.10)
        return 0
    rows = conn.execute(
        "SELECT id, subject_id, owner_user_id FROM deliveries WHERE track = 'fix' AND state = 'in_delivery' "
        "AND owner_user_id IS NOT NULL"
    ).fetchall()
    for r in rows:
        emit(conn, "delivery.fix_checkin", {"delivery_id": r["id"], "subject_id": r["subject_id"],
                                            "current_owner_ids": [str(r["owner_user_id"])]})  # fmt: skip
    return len(rows)


def _overdue_milestones(conn: Conn, now: dt.datetime, today: dt.date) -> tuple[int, int]:
    rows = conn.execute(
        "SELECT m.id, m.due_on, m.owner_user_id, m.overdue_sent_on, m.escalated_on, d.id AS delivery_id, "
        "d.subject_id, d.owner_user_id AS d_owner, d.sponsor_user_id FROM delivery_milestones m "
        "JOIN deliveries d ON d.id = m.delivery_id WHERE m.status = 'open' AND m.due_on < %s "
        "AND d.track = 'fix' AND d.state = 'in_delivery'",
        (today,),
    ).fetchall()
    overdue = escalated = 0
    chairs: list[str] | None = None
    for r in rows:
        refs: dict[str, Any] = {"delivery_id": r["delivery_id"], "subject_id": r["subject_id"]}
        if r["overdue_sent_on"] is None:
            people = sorted({str(u) for u in (r["owner_user_id"], r["d_owner"], r["sponsor_user_id"]) if u})
            emit(conn, "delivery.overdue", {**refs, "reason": "milestone", "current_owner_ids": people})
            conn.execute(
                "UPDATE delivery_milestones SET overdue_sent_on = %s WHERE id = %s", (today, r["id"])
            )
            overdue += 1
        due = dt.datetime.combine(r["due_on"], dt.time(18, 0), tzinfo=IST)
        if r["escalated_on"] is None and add_working_days(due, 10) <= now:
            chairs = chairs if chairs is not None else _role_users(conn, "core_chair")
            if chairs:  # no chair yet: try again on the next run rather than mark it escalated (BLD-127)
                emit(
                    conn, "delivery.overdue", {**refs, "reason": "plan_late", "escalation_target_ids": chairs}
                )
                conn.execute(
                    "UPDATE delivery_milestones SET escalated_on = %s WHERE id = %s", (today, r["id"])
                )
                escalated += 1
    return overdue, escalated


def _blocked(conn: Conn, now: dt.datetime) -> int:
    rows = conn.execute(
        "SELECT id, subject_id, sponsor_user_id, blocked_since FROM deliveries WHERE state = 'in_delivery' "
        "AND gate_status = 'blocked' AND blocked_since IS NOT NULL AND blocked_flagged_at IS NULL"
    ).fetchall()
    flagged = 0
    for r in rows:
        if add_working_days(r["blocked_since"], 10) > now:
            continue
        if r["sponsor_user_id"]:
            emit(conn, "delivery.overdue", {"delivery_id": r["id"], "subject_id": r["subject_id"],
                                            "reason": "blocked", "current_owner_ids": [str(r["sponsor_user_id"])]})  # fmt: skip
        conn.execute("UPDATE deliveries SET blocked_flagged_at = %s WHERE id = %s", (now, r["id"]))
        flagged += 1
    return flagged


def tick(conn: Conn, now: dt.datetime | None = None) -> dict[str, int]:
    now = now or dt.datetime.now(dt.UTC)
    today = now.astimezone(IST).date()
    with conn.transaction():
        overdue, escalated = _overdue_milestones(conn, now, today)
        counts = {
            "measure_due": _remind_due(conn, now, today),
            "measure_to_confirm": _remind_confirm(conn, now, today),
            "fix_checkins": _fix_checkins(conn, today),
            "milestones_overdue": overdue,
            "plans_escalated": escalated,
            "blocked_flagged": _blocked(conn, now),
        }
    log.info("delivery.tick", **counts)
    return counts
