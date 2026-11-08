"""Communication module v1 (B6, AT-B6-08): the eight day-one events land in the in-app inbox and in Mailpit,
rendered from `comms/templates/`; non-urgent email waits through quiet hours, weekends and holidays; at most
one non-urgent email a day per person (the rest go to the digest); plain text with no tracking; `comms.email`
off keeps email queued. Message text is never stored: notifications hold IDs only."""

from __future__ import annotations

import datetime as dt
import json
import secrets
import time
import urllib.request
import uuid
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from comms import emit
from comms.inbox import inbox
from comms.route import next_send_time, route
from comms.send import send_digests, send_due
from comms.templates import render_text
from core import killswitch
from core.crypto import encrypt_json
from jobs import handlers  # noqa: F401
from jobs.runner import run_one
from tests.helpers import tables_containing

IST = ZoneInfo("Asia/Kolkata")
MAILPIT = "http://localhost:8025/api/v1"
ONE_LINE = "Branch forms wait a day in the outward register"
WORKDAY_NOON = dt.datetime(2026, 11, 18, 12, 0, tzinfo=IST)  # a Wednesday, not a holiday


def test_template_variables_sections_and_no_reinterpretation() -> None:
    data = {"a": {"b": "x"}, "items": ["one", "two"], "flag": True, "evil": "{{a.b}}"}
    assert render_text(
        "{{a.b}} {{items.1}} {{#flag}}yes{{/flag}}{{#missing}}no{{/missing}} {{evil}}", data
    ) == ("x two yes {{a.b}}")


def test_quiet_hours_weekends_and_holidays() -> None:
    assert next_send_time(WORKDAY_NOON, "routine") == WORKDAY_NOON
    late = dt.datetime(2026, 11, 20, 21, 0, tzinfo=IST)  # Friday 21:00
    assert next_send_time(late, "routine") == dt.datetime(2026, 11, 23, 8, 0, tzinfo=IST)
    early = dt.datetime(2026, 11, 18, 6, 30, tzinfo=IST)
    assert next_send_time(early, "routine") == dt.datetime(2026, 11, 18, 8, 0, tzinfo=IST)
    assert next_send_time(late, "immediate") == late
    holiday = dt.datetime(2026, 12, 25, 11, 0, tzinfo=IST)  # rules/calendar.md
    assert next_send_time(holiday, "routine") == dt.datetime(2026, 12, 28, 8, 0, tzinfo=IST)


def _mailpit(path: str, method: str = "GET") -> Any:
    req = urllib.request.Request(f"{MAILPIT}/{path}", method=method)
    with urllib.request.urlopen(req, timeout=10) as r:
        body = r.read()
        try:
            return json.loads(body) if body else None
        except ValueError:
            return body.decode()


@pytest.fixture
def people(db: Any) -> Any:
    killswitch.clear_cache()
    db.execute("DELETE FROM jobs")  # events queued by earlier tests are not this test's to deliver
    tag = secrets.token_hex(3)
    users = {}
    for role in ("owner", "joiner", "reviewer", "member", "lob"):
        u = db.execute(
            "INSERT INTO users (emp_id_hash, name, email, source) VALUES (%s, %s, %s, 'hr') RETURNING id",
            (f"test:{role}:{tag}", f"{role.title()} Person", f"{role}.{tag}@kfintech.example"),
        ).fetchone()
        code = f"CTR-{secrets.token_hex(3)}"
        db.execute("INSERT INTO contributor_map (contributor_code, user_id) VALUES (%s, %s)", (code, u["id"]))
        users[role] = {"id": str(u["id"]), "code": code, "email": f"{role}.{tag}@kfintech.example"}
    db.execute("INSERT INTO role_grants (user_id, role) VALUES (%s, 'reviewer')", (users["reviewer"]["id"],))
    db.execute(
        "INSERT INTO role_grants (user_id, role, scope_id) VALUES (%s, 'lob_committee', 'LOB-mf')",
        (users["lob"]["id"],),
    )
    idea_uuid = str(uuid.uuid4())
    canvas = {
        "one_line": ONE_LINE,
        "neutral_summary": "Forms wait before they are sent on.",
        "strength": {"next_best": ["Add numbers", "Add evidence"]},
    }
    db.execute(
        "INSERT INTO ideas (id, idea_id, submission_id, stage, capture_mode, contributor_code, canvas, strength, "
        "submitted_at) VALUES (%s, 'IDEA-2026-000901', 'SUB-2026-000901', 'scanned', 'quick', %s, %s, 2, now())",
        (idea_uuid, users["owner"]["code"], json.dumps(canvas)),
    )
    db.execute(
        "INSERT INTO idea_links (idea_id, contributor_code, link_type) VALUES ('IDEA-2026-000901', %s, 'originator')",
        (users["owner"]["code"],),
    )
    item = db.execute(
        "INSERT INTO review_items (item_type, ref_id, veto_reason, vetoed_by, vetoed_at) "
        "VALUES ('idea', 'IDEA-2026-000901', 'The committee sees a wider pattern', %s, now()) RETURNING id",
        (users["member"]["id"],),
    ).fetchone()["id"]
    q = db.execute(
        "INSERT INTO idea_questions (idea_uuid, review_item_id, asked_by, question_encrypted, due_at) "
        "VALUES (%s, %s, %s, '\\x00', now() + interval '7 days') RETURNING id",
        (idea_uuid, item, users["reviewer"]["id"]),
    ).fetchone()["id"]
    db.execute(
        "UPDATE idea_questions SET question_encrypted = %s WHERE id = %s",
        (encrypt_json({"text": "Which branches see this most?"}, f"question:{q}"), q),
    )
    corr = db.execute(
        "INSERT INTO corrections (review_item_id, field, proposed, final, note) "
        "VALUES (%s, 'value.category', '\"new_revenue\"', '\"cost_saving\"', 'Reads as a saving') RETURNING id",
        (item,),
    ).fetchone()["id"]
    db.execute(
        "INSERT INTO idea_links (idea_id, from_idea_id, contributor_code, link_type, context_text) "
        "VALUES ('IDEA-2026-000901', 'IDEA-2026-000902', %s, 'joiner', 'Same at Jaipur')",
        (users["joiner"]["code"],),
    )
    link = db.execute(
        "INSERT INTO idea_links (solution_id, from_idea_id, contributor_code, link_type, context_text) "
        "VALUES ('SOL-0004', 'IDEA-2026-000901', %s, 'adoption', 'We would use it in MF ops') RETURNING id",
        (users["owner"]["code"],),
    ).fetchone()["id"]
    refs = {
        "idea.submitted": {"idea_id": "IDEA-2026-000901"},
        "canvas.nudge": {"idea_id": "IDEA-2026-000901"},
        "idea.question": {"idea_id": "IDEA-2026-000901", "question_id": q, "reviewer_user_id": users["reviewer"]["id"]},
        "idea.reviewed": {"idea_id": "IDEA-2026-000901", "outcome": "standalone", "next_step": "qualify",
                          "note_correction_id": corr, "reviewer_user_id": users["reviewer"]["id"]},
        "idea.redirected": {"idea_id": "IDEA-2026-000901", "redirect_kind": "it_ticket"},
        "idea.reconsidered": {"idea_id": "IDEA-2026-000901", "review_item_id": item, "outcome": "changed",
                              "member_user_id": users["member"]["id"], "next_step": "clustered"},
        "idea.joined": {"target_id": "IDEA-2026-000901", "joiner_code": users["joiner"]["code"], "idea_id": "IDEA-2026-000902"},
        "adoption.requested": {"idea_id": "IDEA-2026-000901", "solution_id": "SOL-0004", "owner_team": "LOB-mf", "link_id": link},
    }  # fmt: skip
    return db, users, refs


def test_eight_day_one_events_reach_the_inbox_and_mailpit(people: Any) -> None:
    db, users, refs = people
    _mailpit("messages", "DELETE")
    for event, r in refs.items():
        emit(db, event, r)
    while run_one(db, "test-worker"):
        pass
    owner_inbox = inbox(db, users["owner"]["id"])
    subjects = [m["subject"] for m in owner_inbox]
    assert len(owner_inbox) == 7  # submitted, nudge, question, reviewed, redirected, reconsidered, joined
    assert all("{{" not in m["subject"] + m["body"] for m in owner_inbox)
    assert any(ONE_LINE in m["body"] for m in owner_inbox)  # the owner sees their own one line
    assert any("Which branches see this most?" in m["body"] for m in owner_inbox)
    assert any(s.startswith("Your idea is in: IDEA-2026-000901") for s in subjects)
    joiner_view = inbox(
        db, users["owner"]["id"]
    )  # the joined message goes to the existing contributor (owner)
    assert joiner_view
    lob = inbox(db, users["lob"]["id"])
    assert len(lob) == 1 and "We would use it in MF ops" in lob[0]["body"] and ONE_LINE not in lob[0]["body"]

    # Email: immediate ones at once; routine ones respect working hours; the digest carries the rest.
    db.execute("UPDATE notifications SET send_after = %s WHERE channel = 'email'", (WORKDAY_NOON,))
    sent = send_due(db, now=WORKDAY_NOON + dt.timedelta(minutes=1))
    assert sent >= 5
    db.execute("UPDATE notifications SET state = 'held' WHERE channel = 'digest'")
    send_digests(db, now=WORKDAY_NOON)
    time.sleep(0.5)
    msgs = _mailpit("messages")["messages"]
    to_owner = [m for m in msgs if any(t["Address"] == users["owner"]["email"] for t in m["To"])]
    assert len(to_owner) >= 5
    full = _mailpit(f"message/{to_owner[0]['ID']}")
    assert full["HTML"] == "" and "<img" not in full["Text"]  # plain text: nothing to track opens with
    # Text lives only in templates and source records, never in notifications or the comms log.
    assert tables_containing(db, "Which branches see this most?") == []
    assert "notifications.payload" not in tables_containing(db, ONE_LINE)


def test_one_non_urgent_email_a_day_and_the_email_switch(people: Any) -> None:
    db, users, refs = people
    route(db, "canvas.nudge", refs["canvas.nudge"], now=WORKDAY_NOON)
    route(db, "canvas.nudge", refs["canvas.nudge"], now=WORKDAY_NOON)
    rows = db.execute(
        "SELECT channel FROM notifications WHERE user_id = %s AND event = 'canvas.nudge' ORDER BY id",
        (users["owner"]["id"],),
    ).fetchall()
    assert [r["channel"] for r in rows] == ["in_app", "email", "in_app", "digest"]
    killswitch.set_switch(db, "comms.email", "off", reason="Testing the email switch", actor="REV-0001")
    killswitch.clear_cache()
    assert send_due(db, now=WORKDAY_NOON + dt.timedelta(hours=1)) == 0
    assert (
        db.execute(
            "SELECT count(*) AS n FROM notifications WHERE channel = 'email' AND state = 'queued'"
        ).fetchone()["n"]
        >= 1
    )
    killswitch.set_switch(db, "comms.email", "on", reason="Testing the email switch", actor="REV-0001")
    killswitch.clear_cache()
