"""Communication module v1 (B6, AT-B6-08): the eight day-one events land in the in-app inbox and in Mailpit,
rendered from `comms/templates/`; non-urgent email waits through quiet hours, weekends and holidays; at most
one non-urgent email a day per person (the rest go to the digest); plain text with no tracking; `comms.email`
off keeps email queued. Message text is never stored: notifications hold IDs only."""

from __future__ import annotations

import datetime as dt
import json
import re
import secrets
import time
import urllib.request
import uuid
from collections.abc import Iterator
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from comms import emit
from comms.inbox import inbox
from comms.route import next_send_time, route
from comms.send import send_digests, send_due
from comms.templates import render_text
from core import killswitch
from core.config import get_settings
from core.crypto import encrypt_json
from jobs import handlers
from jobs.runner import run_one
from tests import helpers
from tests.helpers import tables_containing

IST = ZoneInfo("Asia/Kolkata")
MAILPIT = f"http://localhost:{get_settings().mailpit_ui_host_port}/api/v1"
ONE_LINE = "Branch forms wait a day in the outward register"
WORKDAY_NOON = dt.datetime(2026, 11, 18, 12, 0, tzinfo=IST)  # a Wednesday, not a holiday


def test_template_variables_sections_and_no_reinterpretation() -> None:
    data = {"a": {"b": "x"}, "items": ["one", "two"], "flag": True, "evil": "{{a.b}}"}
    assert render_text(
        "{{a.b}} {{items.1}} {{#flag}}yes{{/flag}}{{#missing}}no{{/missing}} {{evil}}", data
    ) == ("x two yes {{a.b}}")
    # Inside a section too: an inserted value is never expanded a second time (B6 review).
    assert render_text("{{#flag}}[{{evil}}]{{/flag}}", data) == "[{{a.b}}]"


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
    # Both parts (DEC-061, BLD-125): plain text and branded HTML. The only image is the hosted mark: no pixel.
    assert full["Text"].strip() and full["HTML"].strip()
    imgs = re.findall(r'<img[^>]+src="([^"]+)"', full["HTML"])
    assert imgs == [f"{get_settings().app_base_url.rstrip('/')}/brand/email-mark-white@2x.png"]
    assert "<img" not in full["Text"] and "**" not in full["Text"] and "1% spark. 99% sweat." in full["HTML"]
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


# --- B6 review regressions -------------------------------------------------------------------------------------


def _queue(
    db: Any, user_id: str, channel: str, urgency: str, send_after: dt.datetime | None, state: str
) -> int:
    return int(
        db.execute(
            "INSERT INTO notifications (user_id, channel, template, payload, event, urgency, state, send_after) "
            "VALUES (%s, %s, 'quick-capture-nudge', %s, 'canvas.nudge', %s, %s, %s) RETURNING id",
            (user_id, channel, json.dumps({"idea_id": "IDEA-2026-000901"}), urgency, state, send_after),
        ).fetchone()["id"]
    )


def _state(db: Any, nid: int) -> dict[str, Any]:
    return dict(
        db.execute(
            "SELECT channel, state, error_code, send_after FROM notifications WHERE id = %s", (nid,)
        ).fetchone()
    )


def test_people_who_have_left_get_no_email(people: Any, monkeypatch: Any) -> None:
    db, users, _refs = people
    sent: list[str] = []
    monkeypatch.setattr("comms.send._smtp", lambda to, email: sent.append(to))
    mail = _queue(db, users["owner"]["id"], "email", "immediate", WORKDAY_NOON, "queued")
    held = _queue(db, users["owner"]["id"], "digest", "routine", None, "held")
    db.execute("UPDATE users SET active = false WHERE id = %s", (users["owner"]["id"],))
    send_due(db, now=WORKDAY_NOON)
    send_digests(db, now=WORKDAY_NOON)
    assert sent == []
    assert _state(db, mail)["state"] == "failed" and _state(db, mail)["error_code"] == "recipient_inactive"
    assert _state(db, held)["state"] == "failed"


def test_routine_email_is_checked_again_when_it_is_sent(people: Any, monkeypatch: Any) -> None:
    """A backlog released at night (say, `comms.email` back on at 22:00) still waits for working hours, and a
    second routine email on the same day goes to the digest."""
    db, users, _refs = people
    sent: list[str] = []
    monkeypatch.setattr("comms.send._smtp", lambda to, email: sent.append(to))
    night = dt.datetime(2026, 11, 18, 22, 0, tzinfo=IST)
    late = _queue(db, users["owner"]["id"], "email", "routine", WORKDAY_NOON, "queued")
    urgent = _queue(db, users["owner"]["id"], "email", "immediate", WORKDAY_NOON, "queued")
    assert send_due(db, now=night) == 1 and _state(db, urgent)["state"] == "sent"  # urgent mail goes at once
    assert _state(db, late)["state"] == "queued"
    assert _state(db, late)["send_after"] == dt.datetime(2026, 11, 19, 8, 0, tzinfo=IST)

    morning = dt.datetime(2026, 11, 19, 9, 0, tzinfo=IST)
    second = _queue(db, users["owner"]["id"], "email", "routine", morning, "queued")
    assert send_due(db, now=morning) == 1  # the first routine email of the day
    assert {_state(db, late)["state"], _state(db, second)["state"]} == {"sent", "held"}
    capped = late if _state(db, late)["state"] == "held" else second
    assert _state(db, capped)["channel"] == "digest"


def _queue_event(db: Any, user_id: str, event: str, channel: str, state: str, send_after: Any) -> int:
    return int(
        db.execute(
            "INSERT INTO notifications (user_id, channel, template, payload, event, urgency, state, send_after) "
            "VALUES (%s, %s, 'ember-issue', '{\"issue_id\": 1}', %s, 'routine', %s, %s) RETURNING id",
            (user_id, channel, event, state, send_after),
        ).fetchone()["id"]
    )


def test_the_ember_and_announcements_never_ride_in_a_digest(people: Any, monkeypatch: Any) -> None:
    """Ember review: over the daily cap they wait for the next working day on their own; one held before this rule
    goes back to the email queue, where the switches are checked; the digest carries only the rest."""
    db, users, _refs = people
    sent: list[str] = []
    monkeypatch.setattr("comms.send._smtp", lambda to, email: sent.append(to))
    owner = users["owner"]["id"]
    morning = dt.datetime(2026, 11, 19, 9, 0, tzinfo=IST)
    _queue(db, owner, "email", "routine", morning, "queued")
    assert send_due(db, now=morning) == 1  # the day's one routine email
    killswitch.set_switch(db, "ember.send", "off", reason="test: ember paused", actor="test")
    killswitch.clear_cache()
    try:
        capped = _queue_event(db, owner, "ones.announced", "email", "queued", morning)
        send_due(db, now=morning)
        assert _state(db, capped)["channel"] == "email" and _state(db, capped)["state"] == "queued"
        assert _state(db, capped)["send_after"] == dt.datetime(2026, 11, 20, 8, 0, tzinfo=IST)

        old = _queue_event(db, owner, "ember.issue", "digest", "held", None)
        nudge = _queue(db, owner, "digest", "routine", None, "held")
        assert send_digests(db, now=WORKDAY_NOON) == 1
        assert _state(db, nudge)["state"] == "sent"
        assert (_state(db, old)["channel"], _state(db, old)["state"]) == ("email", "queued")
        send_due(db, now=WORKDAY_NOON)
        assert _state(db, old)["state"] == "queued"  # paused: it waits, it is not sent
    finally:
        killswitch.set_switch(db, "ember.send", "on", reason="test: ember back", actor="test")
        killswitch.clear_cache()


def test_one_bad_digest_does_not_hold_back_the_others(people: Any, monkeypatch: Any) -> None:
    db, users, _refs = people
    sent: list[str] = []

    def smtp(to: str, email: Any) -> None:
        if to == users["owner"]["email"]:
            raise OSError("mailbox unavailable")
        sent.append(to)

    monkeypatch.setattr("comms.send._smtp", smtp)
    bad = _queue(db, users["owner"]["id"], "digest", "routine", None, "held")
    good = _queue(db, users["joiner"]["id"], "digest", "routine", None, "held")
    assert send_digests(db, now=WORKDAY_NOON) == 1
    assert sent == [users["joiner"]["email"]]
    assert _state(db, good)["state"] == "sent" and _state(db, bad)["state"] == "held"  # tried again next time


def test_a_message_that_cannot_be_shown_does_not_hide_the_rest(people: Any) -> None:
    db, users, _refs = people
    _queue(db, users["owner"]["id"], "in_app", "routine", None, "sent")
    db.execute(
        "INSERT INTO notifications (user_id, channel, template, payload, event, urgency, state) "
        "VALUES (%s, 'in_app', 'no-such-template', '{}', 'canvas.nudge', 'routine', 'sent')",
        (users["owner"]["id"],),
    )
    messages = inbox(db, users["owner"]["id"])
    assert len(messages) == 2
    assert any(m["subject"] == "A message we can't show just now" for m in messages)
    assert any(ONE_LINE in m["body"] for m in messages)


# --- BLD-157: what the messages promise is what the product does ------------------------------------------------


@pytest.fixture
def seeded(
    people: Any, company_repo: Any, test_database: str, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Any]:
    """The people above, with messages rendered from this checkout's templates (a fresh copy of the seed), not
    from whatever the local stack's company repo holds."""
    from comms import render, templates
    from comms import route as route_module

    settings = helpers.settings_for(company_repo, test_database)
    for module in (route_module, render, templates):
        monkeypatch.setattr(module, "get_settings", lambda: settings)
    templates._load.cache_clear()
    yield people
    templates._load.cache_clear()


def _msg(db: Any, user_id: str, event: str, template: str, refs: dict[str, Any]) -> tuple[str, str]:
    from comms.send import message_for

    subject, body, _ = message_for(db, user_id, event, template, refs)
    assert "{{" not in subject + body
    return subject, body


def test_joined_counts_everyone_now_on_it_in_plain_plurals(seeded: Any) -> None:
    db, users, refs = seeded
    subject, body = _msg(db, users["owner"]["id"], "idea.joined", "joined", refs["idea.joined"])
    assert subject == "A colleague raised the same thing as you"
    assert "a colleague has raised the same thing as you." in body and f'Your idea: **"{ONE_LINE}"**' in body
    assert "more colleague" not in subject + body
    db.execute(
        "INSERT INTO idea_links (idea_id, from_idea_id, contributor_code, link_type) "
        "VALUES ('IDEA-2026-000901', 'IDEA-2026-000903', %s, 'plus_one')",
        (users["member"]["code"],),
    )
    subject, body = _msg(db, users["owner"]["id"], "idea.joined", "joined", refs["idea.joined"])
    assert subject == "2 colleagues have now raised the same thing as you"
    assert "2 colleagues have now raised the same thing as you." in body
    # An earlier joiner counts the person who first raised it and the newcomer, never themselves.
    subject, _ = _msg(db, users["joiner"]["id"], "idea.joined", "joined", refs["idea.joined"])
    assert subject == "2 colleagues have now raised the same thing as you"


def test_reviewed_and_group_messages_name_the_group_not_its_number(seeded: Any) -> None:
    db, users, refs = seeded
    taken = {r["id"] for r in db.execute("SELECT id FROM clusters").fetchall()}
    cl = next(f"CL-{n}" for n in range(7100, 7999) if f"CL-{n}" not in taken)
    db.execute(
        "INSERT INTO clusters (id, distinct_contributors, member_count, title) VALUES (%s, 2, 2, %s)",
        (cl, "Outward register delays at branches"),
    )
    db.execute("UPDATE ideas SET cluster_id = %s WHERE idea_id = 'IDEA-2026-000901'", (cl,))
    grouped = refs["idea.reviewed"] | {"outcome": "grouped", "cluster_id": cl, "cluster_other_count": 1}
    _, body = _msg(db, users["owner"]["id"], "idea.reviewed", "reviewed", grouped)
    assert "It's now part of **Outward register delays at branches**" in body and cl not in body
    linked = refs["idea.reviewed"] | {"outcome": "grouped", "cluster_id": None}
    _, body = _msg(db, users["owner"]["id"], "idea.reviewed", "reviewed", linked)
    assert "linked with a similar idea" in body and "part of" not in body
    subject, body = _msg(
        db,
        users["owner"]["id"],
        "cluster.approved",
        "cluster-approved",
        {"cluster_id": cl, "member_count": 2},
    )
    assert subject == "Your idea is now in a group: Outward register delays at branches"
    assert "It holds one other idea." in body and cl not in subject + body


def test_redirected_and_reconsidered_offer_only_what_the_idea_page_has(seeded: Any) -> None:
    db, users, refs = seeded
    _, body = _msg(db, users["owner"]["id"], "idea.redirected", "redirected", refs["idea.redirected"])
    assert "Disagree with this?" in body and "reply in the app" not in body
    assert "[See your idea](" in body and "/ideas/IDEA-2026-000901" in body
    assert "Go to" not in body  # no team in rules/redirects.md has a link at launch
    _, body = _msg(db, users["owner"]["id"], "idea.reconsidered", "reconsidered", refs["idea.reconsidered"])
    assert "Disagree with this?" in body and "15 working days" not in body and "another look" not in body
    assert "/ideas/IDEA-2026-000901" in body


def test_adoption_request_links_only_people_who_can_open_the_desk(seeded: Any) -> None:
    db, users, refs = seeded
    _, body = _msg(
        db, users["lob"]["id"], "adoption.requested", "adoption-requested", refs["adoption.requested"]
    )
    assert "/review" not in body and "Open the request" not in body
    assert "the 1% Club team can put you in touch" in body
    assert "credited" not in body and "SOL-0004" not in body and "We would use it in MF ops" in body
    _, body = _msg(
        db, users["reviewer"]["id"], "adoption.requested", "adoption-requested", refs["adoption.requested"]
    )
    assert "[Open the request](" in body and "/review" in body


def test_suggestions_show_only_the_bullets_that_exist(seeded: Any) -> None:
    db, users, refs = seeded
    _, body = _msg(db, users["owner"]["id"], "idea.submitted", "submitted", refs["idea.submitted"])
    assert "- Add numbers\n- Add evidence" in body
    db.execute(
        "UPDATE ideas SET canvas = jsonb_set(canvas, '{strength,next_best}', '[\"Add numbers\"]') "
        "WHERE idea_id = 'IDEA-2026-000901'"
    )
    _, body = _msg(db, users["owner"]["id"], "canvas.nudge", "quick-capture-nudge", refs["canvas.nudge"])
    assert "- Add numbers\n\n" in body and "\n- \n" not in body and not body.rstrip().endswith("-")
    db.execute(
        "UPDATE ideas SET canvas = jsonb_set(canvas, '{strength,next_best}', '[]') WHERE idea_id = 'IDEA-2026-000901'"
    )
    _, body = _msg(db, users["owner"]["id"], "idea.submitted", "submitted", refs["idea.submitted"])
    assert "What would help most" not in body and "\n- " not in body


def test_no_nudge_without_a_suggestion_to_make(seeded: Any) -> None:
    db, _users, _refs = seeded
    db.execute("UPDATE ideas SET submitted_at = now() - interval '2 days' WHERE idea_id = 'IDEA-2026-000901'")
    db.execute("DELETE FROM jobs")
    handlers.comms_nudges(db, {})
    nudged = [
        r["payload"]["refs"]["idea_id"]
        for r in db.execute("SELECT payload FROM jobs WHERE type = 'comms.route'").fetchall()
        if r["payload"]["event"] == "canvas.nudge"
    ]
    assert "IDEA-2026-000901" in nudged
    db.execute(
        "UPDATE ideas SET canvas = jsonb_set(canvas, '{strength,next_best}', '[]') WHERE idea_id = 'IDEA-2026-000901'"
    )
    db.execute("DELETE FROM jobs")
    handlers.comms_nudges(db, {})
    assert not [
        r
        for r in db.execute("SELECT payload FROM jobs WHERE type = 'comms.route'").fetchall()
        if r["payload"]["refs"].get("idea_id") == "IDEA-2026-000901"
    ]
