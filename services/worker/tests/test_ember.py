"""The Ember (DEC-062, DEC-070, DEC-079; BLD-128): an admin drafts, the chair writes the note, an admin sends; the
issue holds only what everyone may see; the switches stop it. Synthetic people only."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from core import killswitch
from ember import render, service
from tests import test_ones
from tests.test_ones import induct, person, refused

ones_db = test_ones.ones_db
cast = test_ones.cast
NOW = dt.datetime(2026, 12, 14, 10, 0, tzinfo=dt.UTC)
NOTE = "The ideas that stood out this month named who feels the problem, and how often. Start there."

ISSUE: dict[str, Any] = {
    "month": "2026-12-01",
    "month_label": "December 2026",
    "impact": [
        {
            "number": 1,
            "name": "Rohit Menon",
            "line": "Flag likely-wrong bank details before a payout",
            "measures": {"effort": {"value": 420, "unit": "corrections a year"}},
            "founding": True,
        },
    ],
    "new_ones": [
        {"number": 17, "name": None, "brief": "If this works: no nominee form twice.", "founding": False}
    ],
    "shipped": [],
    "results": [],
    "by_lob": [{"lob": "Mutual fund operations", "shared": 12, "picked": 3}],
    "managers": ["Rahul Deshpande"],
    "note": NOTE,
}


def test_the_email_reads_in_order_and_says_when_a_section_is_empty() -> None:
    email = render.compose(ISSUE, "https://ideas.example", "https://ideas.example/ember/1")
    assert email.subject == "The Ember, December 2026"
    order = [
        email.html.index(h)
        for h in ("Impact created by Ones", "New Ones", "Shipped, with results", "Ideas in and picked",
                  "What the committee looks for", "Thank you, managers")
    ]  # fmt: skip
    assert order == sorted(order)
    assert "One No. 17" in email.html and "No. 1, Rohit Menon" in email.html  # a name only with consent
    assert "Nothing shipped this month." in email.html and "Effort: 420 corrections a year" in email.text
    assert (
        email.html.count("1% spark. 99% sweat.") == 1 and 'href="https://ideas.example/ember/1"' in email.html
    )


def test_the_email_escapes_everything() -> None:
    issue = {**ISSUE, "note": "<script>x</script> [a](javascript:1)", "managers": ["<b>Rahul</b>"]}
    html = render.compose(issue, "https://ideas.example", "https://ideas.example/ember/1").html
    assert "<script>" not in html and "&lt;script&gt;" in html and "&lt;b&gt;Rahul&lt;/b&gt;" in html
    assert 'href="javascript' not in html


def test_month_labels_and_bounds() -> None:
    assert service.month_label(dt.date(2026, 11, 1)) == "November 2026"
    start, end = service._bounds(dt.date(2026, 12, 1))
    assert (start.month, end.year, end.month) == (12, 2027, 1)
    refused("month_not_valid", service._month, "Dec-2026", NOW)
    assert service._month("", NOW) == dt.date(2026, 12, 1)


# --- With the database ------------------------------------------------------------------------------------------------


@pytest.mark.stack
def test_draft_note_send_and_the_archive(ones_db: Any, cast: Any) -> None:
    db = ones_db
    named = person(db, name="Ananya Rao", consent=True)
    quiet = person(db, name="Synthetic Quiet One")
    induct(db, cast, named, now=NOW)
    induct(db, cast, quiet, now=NOW)

    refused("forbidden", service.draft, db, cast["member"], {"month": "2026-12"})
    issue = service.draft(db, cast["admin"], {"month": "2026-12"}, now=NOW)
    assert service.draft(db, cast["admin"], {"month": "2026-12"}, now=NOW) == {
        "id": issue["id"],
        "created": False,
    }

    refused("not_found", service.view, db, cast["employee"], issue["id"])  # a draft is not for everyone
    draft_view = service.view(db, cast["chair"], issue["id"])
    names = [o["name"] for o in draft_view["new_ones"]]
    assert "Ananya Rao" in names and "Synthetic Quiet One" not in names  # consent decides

    refused("note_required", service.send, db, cast["admin"], issue["id"], now=NOW)
    refused("not_found", service.set_note, db, cast["member"], issue["id"], {"note": NOTE})  # chair or admin
    assert service.current_draft(db, cast["member"]) == {"id": None}
    assert service.current_draft(db, cast["chair"]) == {"id": issue["id"]}
    service.set_note(db, cast["chair"], issue["id"], {"note": NOTE})
    refused("forbidden", service.send, db, cast["chair"], issue["id"], now=NOW)  # only an admin sends

    db.execute("DELETE FROM jobs")
    assert service.send(db, cast["admin"], issue["id"], now=NOW)["state"] == "sent"
    refused("already_sent", service.send, db, cast["admin"], issue["id"], now=NOW)
    refused("already_sent", service.set_note, db, cast["chair"], issue["id"], {"note": NOTE})
    job = db.execute(
        "SELECT payload FROM jobs WHERE type = 'comms.route' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert job["payload"]["event"] == "ember.issue" and job["payload"]["refs"] == {"issue_id": issue["id"]}

    sent = service.view(db, cast["employee"], issue["id"])  # everyone reads a sent issue
    assert sent["state"] == "sent" and sent["note"] == NOTE
    assert next(i["id"] for i in service.archive(db)["issues"]) == issue["id"]
    row = db.execute("SELECT chair_note_encrypted FROM ember_issues WHERE id = %s", (issue["id"],)).fetchone()
    assert row["chair_note_encrypted"] is None  # kept once, in the sent issue
    actions = [r["action"] for r in db.execute(
        "SELECT action FROM audit_log WHERE entity = %s ORDER BY id", (f"ember:{issue['id']}",)).fetchall()]  # fmt: skip
    assert actions == ["ember.drafted", "ember.note_saved", "ember.sent"]


@pytest.mark.stack
def test_the_switches_stop_sending(ones_db: Any, cast: Any) -> None:
    db = ones_db
    issue = service.draft(db, cast["admin"], {"month": "2027-01"}, now=NOW)
    service.set_note(db, cast["admin"], issue["id"], {"note": NOTE})
    for name, code in (("ember.send", "ember_paused"), ("ones.public", "ones_paused")):
        killswitch.set_switch(db, name, "off", reason="test: switch walkthrough", actor="test")
        killswitch.clear_cache()
        refused(code, service.send, db, cast["admin"], issue["id"], now=NOW)
        killswitch.set_switch(db, name, "on", reason="test: switch walkthrough", actor="test")
        killswitch.clear_cache()
    assert service.send(db, cast["admin"], issue["id"], now=NOW)["state"] == "sent"


@pytest.mark.stack
def test_managers_are_thanked_only_for_people_who_share_with_them(ones_db: Any, cast: Any) -> None:
    from tests import helpers

    db = ones_db
    boss = person(db, name="Synthetic Manager Kiran")
    shy_boss = person(db, name="Synthetic Manager Leela")
    open_report = person(db, manager=boss)
    shy_report = person(db, manager=shy_boss)
    db.execute("INSERT INTO comms_prefs (user_id, manager_notes) VALUES (%s, false) "
               "ON CONFLICT (user_id) DO UPDATE SET manager_notes = false", (shy_report,))  # fmt: skip
    for uid in (open_report, shy_report):
        code = db.execute(
            "SELECT contributor_code FROM contributor_map WHERE user_id = %s", (uid,)
        ).fetchone()
        idea = helpers.insert_idea(db, contributor=code["contributor_code"], stage="reviewed")
        db.execute("UPDATE ideas SET submitted_at = %s WHERE idea_id = %s", (NOW, idea))
    managers = service.build(db, dt.date(2026, 12, 1))["managers"]
    assert "Synthetic Manager Kiran" in managers and "Synthetic Manager Leela" not in managers
