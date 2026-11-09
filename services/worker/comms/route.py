"""Route an event to people (§3.7 steps 1–3, 6). `emit` is called inside the transaction that made the change
(it only queues a job); the `comms.route` job reads `comms/rules.md`, finds the recipients and writes one
notification per person and channel, holding non-urgent email through quiet hours, weekends and holidays and
capping it at one a day per person (the rest wait for the digest). In-app messages are delivered at once.
Notifications carry the event and IDs only (BLD-088).
"""

from __future__ import annotations

import datetime as dt
from typing import Any
from zoneinfo import ZoneInfo

from psycopg.types.json import Jsonb

from core.config import get_settings
from core.db import Conn
from core.logging import get_logger
from rules import load_rule

log = get_logger("comms")
IST = ZoneInfo("Asia/Kolkata")


def emit(conn: Conn, event: str, refs: dict[str, Any]) -> None:
    """Queue an event for routing. Refs are IDs and enums only (never text)."""
    conn.execute(
        "INSERT INTO jobs (type, payload) VALUES ('comms.route', %s)",
        (Jsonb({"event": event, "refs": refs}),),
    )


def _rules() -> dict[str, Any]:
    return dict(load_rule(get_settings().company_repo_path, "comms").data)


def _calendar() -> dict[str, Any]:
    return dict(load_rule(get_settings().company_repo_path, "calendar").data)


def next_send_time(now: dt.datetime, urgency: str) -> dt.datetime:
    """Immediate: now. Routine: now if inside working hours on a working day, else 08:00 IST on the next one."""
    if urgency == "immediate":
        return now
    cal = _calendar()
    quiet = cal.get("quiet_hours") or {"from": "20:00", "to": "08:00"}
    start_h, start_m = (int(x) for x in str(quiet["from"]).split(":"))
    end_h, end_m = (int(x) for x in str(quiet["to"]).split(":"))
    weekend = {
        ["mon", "tue", "wed", "thu", "fri", "sat", "sun"].index(d) for d in cal.get("weekend", ["sat", "sun"])
    }
    holidays = {dt.date.fromisoformat(str(h["date"])) for h in cal.get("holidays") or []}
    local = now.astimezone(IST)

    def open_day(d: dt.date) -> bool:
        return d.weekday() not in weekend and d not in holidays

    opens, closes = dt.time(end_h, end_m), dt.time(start_h, start_m)
    if open_day(local.date()) and opens <= local.time() < closes:
        return now
    day = local.date() if local.time() < opens else local.date() + dt.timedelta(days=1)
    while not open_day(day):
        day += dt.timedelta(days=1)
    return dt.datetime.combine(day, opens, tzinfo=IST)


def _users_for_codes(conn: Conn, codes: list[str]) -> list[str]:
    if not codes:
        return []
    rows = conn.execute(
        "SELECT DISTINCT m.user_id FROM contributor_map m JOIN users u ON u.id = m.user_id "
        "WHERE m.contributor_code = ANY(%s) AND u.active",
        (codes,),
    ).fetchall()
    return [str(r["user_id"]) for r in rows]


def _role_users(conn: Conn, role: str, scope: str | None = None) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT g.user_id FROM role_grants g JOIN users u ON u.id = g.user_id WHERE g.role = %s "
        "AND g.valid_to IS NULL AND u.active AND (%s::text IS NULL OR g.scope_id = %s)",
        (role, scope, scope),
    ).fetchall()
    return [str(r["user_id"]) for r in rows]


def recipients(conn: Conn, audience: str, refs: dict[str, Any]) -> list[str]:
    idea_id = refs.get("idea_id")
    if audience == "submitter" and idea_id:
        row = conn.execute("SELECT contributor_code FROM ideas WHERE idea_id = %s", (idea_id,)).fetchone()
        return _users_for_codes(conn, [row["contributor_code"]]) if row else []
    if audience == "existing_contributors":
        target = refs.get("target_id")
        rows = conn.execute(
            "SELECT DISTINCT contributor_code FROM idea_links WHERE coalesce(idea_id, cluster_id) = %s "
            "AND link_type IN ('originator', 'joiner') AND contributor_code <> %s",
            (target, refs.get("joiner_code") or ""),
        ).fetchall()
        return _users_for_codes(conn, [r["contributor_code"] for r in rows])
    if audience == "solution_owner":
        # Solution files name an owning team, not a person: its LOB committee, else the review desk (BLD-088).
        team = refs.get("owner_team")
        return (_role_users(conn, "lob_committee", team) if team else []) or _role_users(conn, "reviewer")
    if audience == "cluster_contributors" and refs.get("cluster_id"):
        rows = conn.execute(
            "SELECT contributor_code FROM ideas WHERE cluster_id = %s UNION SELECT contributor_code FROM idea_links "
            "WHERE cluster_id = %s AND link_type IN ('originator', 'joiner')",
            (refs["cluster_id"], refs["cluster_id"]),
        ).fetchall()
        return _users_for_codes(conn, [r["contributor_code"] for r in rows])
    if audience == "round_members":
        return [str(u) for u in refs.get("member_ids") or []]
    if audience in ("current_owner", "escalation_target"):
        return [str(u) for u in refs.get(f"{audience}_ids") or []]
    if audience == "everyone":  # org-wide announcements (DEC-056)
        return [str(r["id"]) for r in conn.execute("SELECT id FROM users WHERE active").fetchall()]
    return []


def _active(conn: Conn, user_id: str) -> bool:
    row = conn.execute("SELECT active FROM users WHERE id = %s", (user_id,)).fetchone()
    return bool(row and row["active"])


def route(conn: Conn, event: str, refs: dict[str, Any], now: dt.datetime | None = None) -> int:
    """Write the notifications for one event. Returns how many were written."""
    now = now or dt.datetime.now(dt.UTC)
    cfg = (_rules().get("events") or {}).get(event)
    if not cfg or not cfg.get("day_one"):
        log.info("comms.skipped", event_name=event)
        return 0
    people = sorted(
        {u for a in cfg.get("audiences") or [] for u in recipients(conn, a, refs) if _active(conn, u)}
    )
    if not people:
        return 0
    channels = list(cfg.get("channels") or [])
    urgency = "immediate" if cfg.get("urgency") == "immediate" else "routine"
    cap = int((_rules().get("limits") or {}).get("non_urgent_emails_per_person_per_day", 1))
    entry = conn.execute(
        "INSERT INTO comms_log (event, template_version, recipients, channel, state) "
        "VALUES (%s, %s, %s, %s, 'pending') RETURNING id",
        (event, str(cfg.get("template")), people, "in_app"),
    ).fetchone()
    assert entry is not None
    written = 0
    for user in people:
        base = (user, cfg["template"], Jsonb(refs), event, urgency, entry["id"])
        if "in_app" in channels:
            conn.execute(
                "INSERT INTO notifications (user_id, channel, template, payload, event, urgency, state, sent_at, "
                "comms_log_id) VALUES (%s, 'in_app', %s, %s, %s, %s, 'sent', now(), %s)",
                base,
            )
            written += 1
        email = "email" in channels
        digest = "digest" in channels
        if email:
            send_after = next_send_time(now, urgency)
            if urgency == "routine":
                day = send_after.astimezone(IST).date()
                already = conn.execute(
                    "SELECT count(*) AS n FROM notifications WHERE user_id = %s AND channel = 'email' "
                    "AND urgency = 'routine' AND (send_after AT TIME ZONE 'Asia/Kolkata')::date = %s",
                    (user, day),
                ).fetchone()
                if already and int(already["n"]) >= cap:
                    email, digest = False, True  # one non-urgent email a day; the rest wait for the digest
            if email:
                conn.execute(
                    "INSERT INTO notifications (user_id, channel, template, payload, event, urgency, state, "
                    "send_after, comms_log_id) VALUES (%s, 'email', %s, %s, %s, %s, 'queued', %s, %s)",
                    (user, cfg["template"], Jsonb(refs), event, urgency, send_after, entry["id"]),
                )
                written += 1
        if digest:
            conn.execute(
                "INSERT INTO notifications (user_id, channel, template, payload, event, urgency, state, comms_log_id) "
                "VALUES (%s, 'digest', %s, %s, %s, %s, 'held', %s)",
                base,
            )
            written += 1
    conn.execute("UPDATE comms_log SET state = 'sent', sent_at = now() WHERE id = %s", (entry["id"],))
    log.info("comms.routed", event_name=event, recipient_count=len(people), notification_count=written)
    return written
