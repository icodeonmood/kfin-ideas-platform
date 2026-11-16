"""Time limits (B6, AT-B6-07): the review timer is 5 working days by `rules/calendar.md`; reminders at 50% and
80%; a breach escalates to the core committee chair (or committee) and adds a history line; `needs_info` pauses
the review timer; no answer in 7 working days withdraws the idea with a way back."""

from __future__ import annotations

import datetime as dt
import json
import secrets
import uuid
from collections.abc import Iterator
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from comms.route import route
from comms.send import message_for
from sla import engine
from tests import helpers

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


@pytest.fixture
def seeded(
    item: Any, company_repo: Any, test_database: str, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Any]:
    """Messages rendered from this checkout's templates (a fresh copy of the seed), not the local stack's repo."""
    from comms import render, templates
    from comms import route as route_module

    settings = helpers.settings_for(company_repo, test_database)
    for module in (route_module, render, templates):
        monkeypatch.setattr(module, "get_settings", lambda: settings)
    templates._load.cache_clear()
    yield item
    templates._load.cache_clear()


def jobs(db: Any, event: str) -> list[dict[str, Any]]:
    return [
        r["payload"]
        for r in db.execute("SELECT payload FROM jobs WHERE type = 'comms.route' ORDER BY id").fetchall()
        if r["payload"]["event"] == event
    ]


def test_review_timer_reminders_and_breach(seeded: Any) -> None:
    db, users, rid, _ = seeded
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
    # BLD-157: sent the moment the limit passes, so it gives the limit, not "0 days late"; nobody had picked the
    # item up, so no reviewer from the desk is named as its owner.
    assert breach["owner_user_id"] is None and breach["stage"] == "review"
    assert "has passed its time limit of 5 working days" in body and "working day(s)" not in body
    assert "Nobody on the review desk has picked it up yet." in body and "Reviewer Person" not in body


def test_an_overdue_item_names_only_the_reviewer_handling_it(seeded: Any) -> None:
    db, users, rid, _ = seeded
    db.execute("UPDATE review_items SET assigned_to = %s WHERE id = %s", (users["reviewer"]["id"], int(rid)))
    tid = engine.start(db, "review_item", rid, "review", now=MONDAY)
    due = db.execute("SELECT due_at FROM sla_timers WHERE id = %s", (tid,)).fetchone()["due_at"]
    engine.tick(db, now=due + dt.timedelta(hours=1))
    breach = jobs(db, "sla.breached")[0]["refs"]
    assert breach["owner_user_id"] == users["reviewer"]["id"]
    _, body, _ = message_for(db, users["chair"]["id"], "sla.breached", "sla-breached", breach)
    assert "It is with Reviewer Person." in body and "Nobody on the review desk" not in body


def test_an_overdue_committee_step_reads_as_words_not_a_number(seeded: Any) -> None:
    """BLD-157: a committee step is named by what it is and the group's name, and links to the committee."""
    db, users, _rid, _ = seeded
    cl = f"CL-9{secrets.randbelow(1000):03d}"
    db.execute(
        "INSERT INTO clusters (id, distinct_contributors, title) VALUES (%s, 2, %s) ON CONFLICT (id) DO UPDATE "
        "SET title = EXCLUDED.title",
        (cl, "Branch forms wait in the outward register"),
    )
    qid = db.execute(
        "INSERT INTO review_items (item_type, ref_id) VALUES ('qualify', %s) RETURNING id", (cl,)
    ).fetchone()["id"]
    refs = {"stage": "qualify", "entity_type": "review_item", "entity_id": str(qid), "item_label": cl,
            "limit_wd": 10, "owner_user_id": None, "current_owner_ids": [], "escalation_target_ids": []}  # fmt: skip
    subject, body, _ = message_for(db, users["chair"]["id"], "sla.breached", "sla-breached", refs)
    assert (
        subject
        == "Overdue: The readiness check for the group \u201cBranch forms wait in the outward register\u201d"
    )
    assert cl not in subject + body and "/review" in body
    refs = {"stage": "scoring_round", "entity_type": "scoring_round", "entity_id": "999999", "limit_wd": 10}
    subject, body, _ = message_for(db, users["chair"]["id"], "sla.breached", "sla-breached", refs)
    assert subject == "Overdue: Committee scoring for a group" and "/committee" in body
    assert "999999" not in subject + body


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


# --- B6 review regressions -------------------------------------------------------------------------------------


def test_pause_and_resume_count_working_time_only(item: Any) -> None:
    """Paused on Friday, resumed on Monday: the one working day that was left is still left (not three)."""
    db, _users, rid, _ = item
    tid = engine.start(db, "review_item", rid, "review", now=MONDAY)  # due Mon 23 Nov 10:00
    engine.pause(db, "review_item", rid, "review", now=MONDAY + dt.timedelta(days=4))  # Fri 20 Nov 10:00
    engine.resume(db, "review_item", rid, "review", now=MONDAY + dt.timedelta(days=7))  # Mon 23 Nov 10:00
    row = db.execute("SELECT due_at, paused_total FROM sla_timers WHERE id = %s", (tid,)).fetchone()
    assert row["due_at"].astimezone(IST) == dt.datetime(2026, 11, 24, 10, 0, tzinfo=IST)
    assert row["paused_total"] == dt.timedelta(days=1)  # the weekend is not counted as pause


def test_the_veto_window_closes_quietly(item: Any) -> None:
    db, _users, rid, _ = item
    tid = engine.start(db, "review_item", rid, "veto_window", now=MONDAY)
    due = db.execute("SELECT due_at FROM sla_timers WHERE id = %s", (tid,)).fetchone()["due_at"]
    counts = engine.tick(db, now=due + dt.timedelta(minutes=1))
    assert counts["expired"] == 1 and counts["breaches"] == 0
    assert db.execute("SELECT state FROM sla_timers WHERE id = %s", (tid,)).fetchone()["state"] == "stopped"
    assert jobs(db, "sla.breached") == [] and jobs(db, "sla.reminder") == []


def test_an_answer_that_lands_first_wins_over_the_withdrawal(item: Any) -> None:
    """The needs_info timer is due, but the person has answered (the idea is no longer waiting): no withdrawal."""
    db, _users, _rid, idea_uuid = item
    tid = engine.start(db, "idea", "IDEA-2026-000951", "needs_info", now=MONDAY)
    due = db.execute("SELECT due_at FROM sla_timers WHERE id = %s", (tid,)).fetchone()["due_at"]
    db.execute("UPDATE ideas SET stage = 'scanned' WHERE id = %s", (idea_uuid,))  # answered
    counts = engine.tick(db, now=due + dt.timedelta(minutes=1))
    assert counts["withdrawn"] == 0
    assert db.execute("SELECT stage FROM ideas WHERE id = %s", (idea_uuid,)).fetchone()["stage"] == "scanned"
    assert jobs(db, "idea.withdrawn_no_answer") == []

    # And a timer stopped by the answer is never looked at again.
    t2 = engine.start(db, "idea", "IDEA-2026-000951", "needs_info", now=MONDAY)
    engine.stop(db, "idea", "IDEA-2026-000951", "needs_info")
    engine.tick(db, now=due + dt.timedelta(days=1))
    assert db.execute("SELECT state FROM sla_timers WHERE id = %s", (t2,)).fetchone()["state"] == "stopped"


def test_a_timer_kind_with_no_rule_is_skipped_and_the_rest_still_run(item: Any) -> None:
    """BLD-A182: the 1% Club cut-over lets other lanes add timer kinds with their own sweeps. One the engine has no
    rule for stays running and is skipped by ID; the timers behind it are still handled."""
    db, _users, rid, _ = item
    db.execute(
        "INSERT INTO sla_timers (entity_type, entity_id, stage, started_at, due_at) "
        "VALUES ('idea', 'IDEA-2026-000952', 'impact_30', %s, %s)",
        (MONDAY - dt.timedelta(days=40), MONDAY - dt.timedelta(days=10)),
    )
    tid = engine.start(db, "review_item", rid, "veto_window", now=MONDAY)
    due = db.execute("SELECT due_at FROM sla_timers WHERE id = %s", (tid,)).fetchone()["due_at"]
    counts = engine.tick(db, now=due + dt.timedelta(minutes=1))
    assert counts["skipped"] == 1 and counts["expired"] == 1
    rows = db.execute(
        "SELECT stage, state FROM sla_timers WHERE entity_id IN ('IDEA-2026-000952', %s)", (rid,)
    ).fetchall()
    states = {r["stage"]: r["state"] for r in rows}
    assert states == {"impact_30": "running", "veto_window": "stopped"}
