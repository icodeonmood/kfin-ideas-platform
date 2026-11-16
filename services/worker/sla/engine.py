"""Time limits (§3.6, AT-B6-07). Timers live in `sla_timers`, limits in `rules/sla.md`, working days in
`rules/calendar.md`.

- `start` sets the due time `limit_wd` working days ahead; `stop` ends a timer when its stage ends.
- `pause`/`resume`: `needs_info` pauses the review timer; on resume the due time moves on by the pause.
- `tick` (every minute, from the worker's ticker): reminders to the current owner at each `remind_at` share of
  the limit (50% and 80% for review), and on breach the timer turns `breached`, the escalation target is told
  (`sla.breached`) and the idea's history gets a line. A `needs_info` breach withdraws the idea; the person can
  reopen it from the message.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from psycopg.types.json import Jsonb

from comms.route import emit
from core.config import get_settings
from core.db import Conn
from core.logging import get_logger
from rules import load_rule
from sla.calendar import add_working_days, add_working_seconds, working_seconds

log = get_logger("sla")


def _rules() -> dict[str, Any]:
    return dict(load_rule(get_settings().company_repo_path, "sla").data)


def _rule(stage: str) -> dict[str, Any]:
    return dict(_rules()[stage])


def start(conn: Conn, entity_type: str, entity_id: str, stage: str, now: dt.datetime | None = None) -> int:
    now = now or dt.datetime.now(dt.UTC)
    due = add_working_days(now, int(_rule(stage)["limit_wd"]))
    row = conn.execute(
        "INSERT INTO sla_timers (entity_type, entity_id, stage, started_at, due_at) VALUES (%s, %s, %s, %s, %s) "
        "RETURNING id",
        (entity_type, entity_id, stage, now, due),
    ).fetchone()
    assert row is not None
    return int(row["id"])


def _open(conn: Conn, entity_type: str, entity_id: str, stage: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM sla_timers WHERE entity_type = %s AND entity_id = %s AND stage = %s "
        "AND state IN ('running', 'paused') ORDER BY id DESC LIMIT 1 FOR UPDATE",
        (entity_type, entity_id, stage),
    ).fetchone()
    return dict(row) if row else None


def stop(conn: Conn, entity_type: str, entity_id: str, stage: str) -> None:
    conn.execute(
        "UPDATE sla_timers SET state = 'stopped', stopped_at = now() WHERE entity_type = %s AND entity_id = %s "
        "AND stage = %s AND state IN ('running', 'paused')",
        (entity_type, entity_id, stage),
    )


def pause(conn: Conn, entity_type: str, entity_id: str, stage: str, now: dt.datetime | None = None) -> None:
    conn.execute(
        "UPDATE sla_timers SET state = 'paused', paused_at = %s WHERE entity_type = %s AND entity_id = %s "
        "AND stage = %s AND state = 'running'",
        (now or dt.datetime.now(dt.UTC), entity_type, entity_id, stage),
    )


def resume(conn: Conn, entity_type: str, entity_id: str, stage: str, now: dt.datetime | None = None) -> None:
    """Pick up where the timer stopped: the working time that was left at the pause is left now (B6 review)."""
    now = now or dt.datetime.now(dt.UTC)
    rows = conn.execute(
        "SELECT id, paused_at, due_at, paused_total FROM sla_timers WHERE entity_type = %s AND entity_id = %s "
        "AND stage = %s AND state = 'paused' FOR UPDATE",
        (entity_type, entity_id, stage),
    ).fetchall()
    for r in rows:
        left = working_seconds(r["paused_at"], r["due_at"])
        paused = working_seconds(r["paused_at"], now)
        conn.execute(
            "UPDATE sla_timers SET state = 'running', due_at = %s, paused_total = paused_total + make_interval(secs => %s), "
            "paused_at = NULL WHERE id = %s",
            (add_working_seconds(now, left), paused, r["id"]),
        )


def _fraction(t: dict[str, Any], now: dt.datetime) -> float:
    """Share of the limit used, in working time (a weekend does not bring a reminder closer)."""
    if now >= t["due_at"]:
        return 1.0
    paused = t["paused_total"].total_seconds()
    total = working_seconds(t["started_at"], t["due_at"]) - paused
    spent = working_seconds(t["started_at"], now) - paused
    return max(0.0, spent / total) if total > 0 else 1.0


def _owner_and_idea(conn: Conn, t: dict[str, Any]) -> tuple[list[str], str | None, str | None]:
    """Who hears about the timer (the assigned reviewer, else the whole desk), which idea it is about, and who is
    handling it. The last is None while nobody has picked the item up: a message never names a reviewer picked
    from the desk as its owner (BLD-157)."""
    if t["entity_type"] == "review_item":
        row = conn.execute(
            "SELECT assigned_to, ref_id FROM review_items WHERE id = %s", (int(t["entity_id"]),)
        ).fetchone()
        if row is None:
            return [], None, None
        if row["assigned_to"]:
            return [str(row["assigned_to"])], row["ref_id"], str(row["assigned_to"])
        desk = conn.execute(
            "SELECT DISTINCT g.user_id FROM role_grants g JOIN users u ON u.id = g.user_id "
            "WHERE g.role = 'reviewer' AND g.valid_to IS NULL AND u.active"
        ).fetchall()
        return [str(r["user_id"]) for r in desk], row["ref_id"], None
    if t["entity_type"] == "idea":
        return [], t["entity_id"], None
    return [], None, None


def _escalation(conn: Conn, target: str | None) -> list[str]:
    if not target:
        return []
    roles = ["core_chair", "core_committee"] if target == "core_chair" else [target]
    for role in roles:  # the chair if one is named, else the core committee
        rows = conn.execute(
            "SELECT DISTINCT g.user_id FROM role_grants g JOIN users u ON u.id = g.user_id "
            "WHERE g.role = %s AND g.valid_to IS NULL AND u.active",
            (role,),
        ).fetchall()
        if rows:
            return [str(r["user_id"]) for r in rows]
    return []


def tick(conn: Conn, now: dt.datetime | None = None) -> dict[str, int]:
    now = now or dt.datetime.now(dt.UTC)
    counts = {"reminders": 0, "breaches": 0, "withdrawn": 0, "expired": 0, "skipped": 0}
    rules = _rules()
    ids = [
        r["id"]
        for r in conn.execute("SELECT id FROM sla_timers WHERE state = 'running' ORDER BY id").fetchall()
    ]
    for timer_id in ids:
        with conn.transaction():
            # Lock and re-read: an answer or a decision may have stopped this timer since the list was taken.
            row = conn.execute(
                "SELECT * FROM sla_timers WHERE id = %s AND state = 'running' FOR UPDATE", (timer_id,)
            ).fetchone()
            if row is None:
                continue
            t = dict(row)
            if t["stage"] not in rules:
                # A timer kind with no rule in rules/sla.md: another lane's clock with its own sweep (the 1% Club
                # cut-over added several), or a rule removed by mistake. Leave it running, say so by ID, and carry
                # on with the rest, rather than stop every timer behind it (BLD-A182).
                log.warning("sla.timer_without_rule", timer_id=timer_id, stage=t["stage"])
                counts["skipped"] += 1
                continue
            rule = dict(rules[t["stage"]])
            f = _fraction(t, now)
            is_deadline = bool(rule.get("escalate_to") or rule.get("remind_at") or rule.get("on_breach"))
            if f >= 1 and not is_deadline:
                # A window, not a deadline (the veto window): it simply closes, with no breach and no message.
                conn.execute(
                    "UPDATE sla_timers SET state = 'stopped', stopped_at = %s WHERE id = %s", (now, timer_id)
                )
                counts["expired"] += 1
                continue
            owners, idea_id, handler = _owner_and_idea(conn, t)
            sent = [float(x) for x in t["reminders_sent"] or []]
            for share in [float(x) for x in rule.get("remind_at") or []]:
                if f >= share and share not in sent and f < 1:
                    conn.execute(
                        "UPDATE sla_timers SET reminders_sent = array_append(reminders_sent, %s) WHERE id = %s",
                        (share, timer_id),
                    )
                    emit(
                        conn,
                        "sla.reminder",
                        {
                            "timer_id": timer_id,
                            "share": share,
                            "current_owner_ids": owners,
                            "idea_id": idea_id,
                        },
                    )
                    counts["reminders"] += 1
            if f < 1:
                continue
            conn.execute(
                "UPDATE sla_timers SET state = 'breached', escalated_at = %s WHERE id = %s", (now, timer_id)
            )
            if rule.get("on_breach") == "withdraw_with_reopen" and t["entity_type"] == "idea":
                moved = conn.execute(
                    "UPDATE ideas SET stage = 'withdrawn' WHERE idea_id = %s AND stage = 'needs_info'",
                    (t["entity_id"],),
                ).rowcount
                if moved:  # only if still waiting for an answer
                    emit(conn, "idea.withdrawn_no_answer", {"idea_id": t["entity_id"]})
                    counts["withdrawn"] += 1
            else:
                emit(
                    conn,
                    "sla.breached",
                    {
                        "timer_id": timer_id, "item_label": idea_id or t["entity_id"],
                        "days_late": max(0, (now - t["due_at"]).days), "limit_wd": rule.get("limit_wd"),
                        "current_owner_ids": owners, "escalation_target_ids": _escalation(conn, rule.get("escalate_to")),
                        "owner_user_id": handler, "idea_id": idea_id, "stage": t["stage"],
                        "entity_type": t["entity_type"], "entity_id": t["entity_id"],
                    },
                )  # fmt: skip
            if idea_id:
                conn.execute(
                    "INSERT INTO outbox (event_type, aggregate_id, actor, payload) VALUES ('idea.stage_changed', %s, "
                    "'process:sla', %s)",
                    (idea_id, Jsonb({"history": [{"event": f"{t['stage']}_overdue", "by": "process:sla"}]})),
                )
            counts["breaches"] += 1
            log.warning("sla.breached", timer_id=timer_id, stage_name=t["stage"])
    return counts
