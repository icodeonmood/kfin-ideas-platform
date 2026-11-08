"""Time limits (B6, AT-B6-07): the review timer is 5 working days by `rules/calendar.md`; reminders at 50% and
80%; a breach escalates to the core committee chair (or committee) and adds a history line; `needs_info` pauses
the review timer; no answer in 7 working days withdraws the idea with a way back."""

from __future__ import annotations

import datetime as dt
import json
import secrets
import uuid
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from comms.route import route
from comms.send import message_for
from sla import engine

IST = ZoneInfo("Asia/Kolkata")
MONDAY = dt.datetime(2026, 11, 16, 10, 0, tzinfo=IST)


@pytest.fixture
def item(db: Any) -> Any:
    db.execute("DELETE FROM jobs")
    tag = secrets.token_hex(3)
    users = {}
    for role in ("owner", "reviewer", "chair"):
        u = db.execute(
            "INSERT INTO users (emp_id_hash, name, email, source) VALUES (%s, %s, %s, 'hr') RETURNING id",
            (f"test:{role}:{tag}", f"{role.title()} Person", f"{role}.{tag}@kfintech.example"),
        ).fetchone()
        code = f"CTR-{secrets.token_hex(3)}"
        db.execute("INSERT INTO contributor_map (contributor_code, user_id) VALUES (%s, %s)", (code, u["id"]))
        users[role] = {"id": str(u["id"]), "code": code}
    db.execute("INSERT INTO role_grants (user_id, role) VALUES (%s, 'reviewer')", (users["reviewer"]["id"],))
    db.execute(
        "INSERT INTO role_grants (user_id, role) VALUES (%s, 'core_committee')", (users["chair"]["id"],)
    )
    idea_uuid = str(uuid.uuid4())
    db.execute(
        "INSERT INTO ideas (id, idea_id, submission_id, stage, contributor_code, canvas, submitted_at) "
        "VALUES (%s, 'IDEA-2026-000951', 'SUB-2026-000951', 'scanned', %s, %s, now())",
        (
            idea_uuid,
            users["owner"]["code"],
            json.dumps({"one_line": "Forms wait a day", "neutral_summary": "Forms wait."}),
        ),
    )
    rid = db.execute(
        "INSERT INTO review_items (item_type, ref_id) VALUES ('idea', 'IDEA-2026-000951') RETURNING id"
    ).fetchone()["id"]
    return db, users, str(rid), idea_uuid


def jobs(db: Any, event: str) -> list[dict[str, Any]]:
    return [
        r["payload"]
        for r in db.execute("SELECT payload FROM jobs WHERE type = 'comms.route' ORDER BY id").fetchall()
        if r["payload"]["event"] == event
    ]


def test_review_timer_reminders_and_breach(item: Any) -> None:
    db, users, rid, _ = item
    tid = engine.start(db, "review_item", rid, "review", now=MONDAY)
    due = db.execute("SELECT due_at FROM sla_timers WHERE id = %s", (tid,)).fetchone()["due_at"]
    assert due.astimezone(IST) == dt.datetime(
        2026, 11, 23, 10, 0, tzinfo=IST
    )  # 5 working days, weekend skipped

    engine.tick(db, now=MONDAY + dt.timedelta(days=3, hours=12))  # past 50%, before 80%
    assert [
        float(x)
        for x in db.execute("SELECT reminders_sent FROM sla_timers WHERE id = %s", (tid,)).fetchone()[
            "reminders_sent"
        ]
    ] == [0.5]
    engine.tick(db, now=MONDAY + dt.timedelta(days=5, hours=12))  # past 80%
    engine.tick(db, now=MONDAY + dt.timedelta(days=5, hours=13))  # no repeat
    reminders = jobs(db, "sla.reminder")
    assert [r["refs"]["share"] for r in reminders] == [0.5, 0.8]
    assert reminders[0]["refs"]["current_owner_ids"] == [
        users["reviewer"]["id"]
    ]  # the desk, while unassigned

    engine.tick(db, now=due + dt.timedelta(hours=1))
    assert db.execute("SELECT state FROM sla_timers WHERE id = %s", (tid,)).fetchone()["state"] == "breached"
    breach = jobs(db, "sla.breached")[0]["refs"]
    assert breach["escalation_target_ids"] == [users["chair"]["id"]]
    history = db.execute(
        "SELECT payload FROM outbox WHERE aggregate_id = 'IDEA-2026-000951' AND event_type = 'idea.stage_changed'"
    ).fetchone()["payload"]
    assert history["history"][0]["event"] == "review_overdue"
    # Both messages render from their templates.
    assert route(db, "sla.reminder", reminders[0]["refs"]) == 1
    assert route(db, "sla.breached", breach) >= 2
    subject, body, _ = message_for(db, users["chair"]["id"], "sla.breached", "sla-breached", breach)
    assert "{{" not in subject + body and "IDEA-2026-000951" in subject + body


def test_needs_info_pauses_review_and_withdraws_after_seven_working_days(item: Any) -> None:
    db, users, rid, idea_uuid = item
    review = engine.start(db, "review_item", rid, "review", now=MONDAY)
    before = db.execute("SELECT due_at FROM sla_timers WHERE id = %s", (review,)).fetchone()["due_at"]
    engine.pause(db, "review_item", rid, "review", now=MONDAY + dt.timedelta(days=1))
    db.execute("UPDATE ideas SET stage = 'needs_info' WHERE id = %s", (idea_uuid,))
    info = engine.start(db, "idea", "IDEA-2026-000951", "needs_info", now=MONDAY + dt.timedelta(days=1))
    engine.tick(db, now=MONDAY + dt.timedelta(days=4))  # paused review timer is not checked
    assert db.execute("SELECT state FROM sla_timers WHERE id = %s", (review,)).fetchone()["state"] == "paused"
    engine.resume(db, "review_item", rid, "review", now=MONDAY + dt.timedelta(days=3))
    after = db.execute("SELECT due_at FROM sla_timers WHERE id = %s", (review,)).fetchone()["due_at"]
    assert after - before == dt.timedelta(days=2)  # the pause moved the due time on

    engine.pause(db, "review_item", rid, "review", now=MONDAY + dt.timedelta(days=3))
    due_info = db.execute("SELECT due_at FROM sla_timers WHERE id = %s", (info,)).fetchone()["due_at"]
    assert due_info.astimezone(IST).date() == dt.date(2026, 11, 26)  # Tue 17th + 7 working days
    engine.tick(db, now=due_info + dt.timedelta(minutes=5))
    assert (
        db.execute("SELECT stage FROM ideas WHERE id = %s", (idea_uuid,)).fetchone()["stage"] == "withdrawn"
    )
    withdrawn = jobs(db, "idea.withdrawn_no_answer")
    assert withdrawn and withdrawn[0]["refs"]["idea_id"] == "IDEA-2026-000951"
    _subject, body, _ = message_for(
        db, users["owner"]["id"], "idea.withdrawn_no_answer", "withdrawn-no-answer", withdrawn[0]["refs"]
    )
    assert "Forms wait a day" in body and "Reopen" in body
