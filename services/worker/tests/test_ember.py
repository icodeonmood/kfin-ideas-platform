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
    "picked_in_month": True,
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
    assert "Picked this month: 3." in email.text
    older = render.compose(
        {**ISSUE, "picked_in_month": None}, "https://ideas.example", "https://x.example/e/1"
    )
    assert "Picked so far: 3." in older.text  # issues sent before stage history keep their meaning
    assert (
        email.html.count("1% spark. 99% sweat.") == 1 and 'href="https://ideas.example/ember/1"' in email.html
    )


def test_the_email_escapes_everything() -> None:
    issue = {**ISSUE, "note": "<script>x</script> [a](javascript:1)", "managers": ["<b>Rahul</b>"]}
    html = render.compose(issue, "https://ideas.example", "https://ideas.example/ember/1").html
    assert "<script>" not in html and "&lt;script&gt;" in html and "&lt;b&gt;Rahul&lt;/b&gt;" in html
    assert 'href="javascript' not in html


def test_money_and_time_read_as_on_the_web() -> None:
    """Indian grouping and the web's words (apps/web/src/lib/measures.ts): no doubled "rupees", time given back."""
    assert [render.grouped(v) for v in (999, 1000, 123456, 1234567, 12345678.5)] == [
        "999", "1,000", "1,23,456", "12,34,567", "1,23,45,678.5",
    ]  # fmt: skip
    assert render.measure_words("money", {"value": 250000, "unit": "rupees a year"}) == "₹2,50,000 a year"
    assert (
        render.measure_words("time", {"value": 1200, "unit": "hours a year"})
        == "1,200 hours a year given back"
    )
    issue = {**ISSUE, "results": [{"label": "Bank check", "mark": "30 days",
                                   "measures": {"money": {"value": 180000, "unit": "rupees a year"}}}]}  # fmt: skip
    text = render.compose(issue, "https://ideas.example", "https://ideas.example/ember/1").text
    assert "Money: ₹1,80,000 a year" in text and "rupees" not in text


def test_month_labels_and_bounds() -> None:
    assert service.month_label(dt.date(2026, 11, 1)) == "November 2026"
    start, end = service._bounds(dt.date(2026, 12, 1))
    assert (start.month, end.year, end.month) == (12, 2027, 1)
    refused("month_not_valid", service._month, "Dec-2026", NOW)
    assert service._month("", NOW) == dt.date(2026, 12, 1)


# --- With the database ------------------------------------------------------------------------------------------------


@pytest.mark.stack
def test_draft_note_send_and_the_archive(ones_db: Any, cast: Any) -> None:
    """The chair approves the note (server-side `ready`), and a different admin sends with the confirm token."""
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

    refused("not_ready", service.send, db, cast["admin"], issue["id"], {}, now=NOW)
    refused("note_required", service.approve_note, db, cast["chair"], issue["id"], now=NOW)
    refused("not_found", service.set_note, db, cast["member"], issue["id"], {"note": NOTE})  # chair or admin
    assert service.current_draft(db, cast["member"]) == {"id": None}
    assert service.current_draft(db, cast["chair"]) == {"id": issue["id"]}
    service.set_note(db, cast["chair"], issue["id"], {"note": NOTE})
    refused(
        "not_ready", service.send, db, cast["admin"], issue["id"], {}, now=NOW
    )  # the chair has not signed
    refused("chair_only", service.approve_note, db, cast["admin"], issue["id"], now=NOW)
    service.approve_note(db, cast["chair"], issue["id"], now=NOW)
    refused("forbidden", service.send, db, cast["chair"], issue["id"], {}, now=NOW)  # only an admin sends
    admin_view = service.view(db, cast["admin"], issue["id"])
    assert admin_view["state"] == "ready" and admin_view["can_send"] and admin_view["confirm_token"]
    assert service.view(db, cast["chair"], issue["id"])["confirm_token"] is None  # only for the sender
    refused("confirm_stale", service.send, db, cast["admin"], issue["id"], {"confirm_token": "x"}, now=NOW)

    db.execute("DELETE FROM jobs")
    token = {"confirm_token": admin_view["confirm_token"]}
    assert service.send(db, cast["admin"], issue["id"], token, now=NOW)["state"] == "sent"
    refused("already_sent", service.send, db, cast["admin"], issue["id"], token, now=NOW)
    refused("already_sent", service.set_note, db, cast["chair"], issue["id"], {"note": NOTE})
    job = db.execute(
        "SELECT payload FROM jobs WHERE type = 'comms.route' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert job["payload"]["event"] == "ember.issue" and job["payload"]["refs"] == {"issue_id": issue["id"]}

    sent = service.view(db, cast["employee"], issue["id"])  # everyone reads a sent issue
    assert sent["state"] == "sent" and sent["note"] == NOTE
    assert "Ananya Rao" in [o["name"] for o in sent["new_ones"]]
    assert next(i["id"] for i in service.archive(db)["issues"]) == issue["id"]
    row = db.execute(
        "SELECT chair_note_encrypted, ready_token, content FROM ember_issues WHERE id = %s", (issue["id"],)
    ).fetchone()
    assert row["chair_note_encrypted"] is None and row["ready_token"] is None  # kept once, in the sent issue
    assert "Ananya Rao" not in str(row["content"])  # Ones are stored as references, never names

    # She withdraws her consent: the archive stops naming her at once (DPDPA).
    db.execute("UPDATE comms_prefs SET public_name_consent = false WHERE user_id = %s", (named,))
    later = service.view(db, cast["employee"], issue["id"])
    assert "Ananya Rao" not in [o["name"] for o in later["new_ones"]] and later["new_ones"]
    actions = [r["action"] for r in db.execute(
        "SELECT action FROM audit_log WHERE entity = %s ORDER BY id", (f"ember:{issue['id']}",)).fetchall()]  # fmt: skip
    assert actions == ["ember.drafted", "ember.note_saved", "ember.note_approved", "ember.sent"]


@pytest.mark.stack
def test_the_note_writer_or_approver_never_sends_and_a_changed_note_needs_the_chair_again(
    ones_db: Any, cast: Any
) -> None:
    db = ones_db
    other_admin = person(db, "admin")
    issue = service.draft(db, cast["admin"], {"month": "2027-02"}, now=NOW)
    service.set_note(db, cast["admin"], issue["id"], {"note": NOTE})  # an admin may draft the note
    service.approve_note(db, cast["chair"], issue["id"], now=NOW)
    token = {"confirm_token": service.view(db, other_admin, issue["id"])["confirm_token"]}
    refused("own_note", service.send, db, cast["admin"], issue["id"], token, now=NOW)  # wrote it
    assert service.view(db, cast["admin"], issue["id"])["own_note"]
    # A change after approval takes the issue back to draft; the old token is gone.
    service.set_note(db, cast["admin"], issue["id"], {"note": NOTE + " Then say what changes."})
    assert service.view(db, other_admin, issue["id"])["state"] == "draft"
    refused("not_ready", service.send, db, other_admin, issue["id"], token, now=NOW)
    service.approve_note(db, cast["chair"], issue["id"], now=NOW)
    refused("confirm_stale", service.send, db, other_admin, issue["id"], token, now=NOW)
    fresh = {"confirm_token": service.view(db, other_admin, issue["id"])["confirm_token"]}
    assert service.send(db, other_admin, issue["id"], fresh, now=NOW)["state"] == "sent"


@pytest.mark.stack
def test_the_switches_stop_sending(ones_db: Any, cast: Any) -> None:
    db = ones_db
    issue = service.draft(db, cast["admin"], {"month": "2027-01"}, now=NOW)
    service.set_note(db, cast["chair"], issue["id"], {"note": NOTE})
    service.approve_note(db, cast["chair"], issue["id"], now=NOW)
    token = {"confirm_token": service.view(db, cast["admin"], issue["id"])["confirm_token"]}
    for name, code in (("ember.send", "ember_paused"), ("ones.public", "ones_paused")):
        killswitch.set_switch(db, name, "off", reason="test: switch walkthrough", actor="test")
        killswitch.clear_cache()
        refused(code, service.send, db, cast["admin"], issue["id"], token, now=NOW)
        killswitch.set_switch(db, name, "on", reason="test: switch walkthrough", actor="test")
        killswitch.clear_cache()
    assert service.send(db, cast["admin"], issue["id"], token, now=NOW)["state"] == "sent"


@pytest.mark.stack
def test_committee_only_ideas_stay_out_and_mixed_groups_are_counted_not_named(
    ones_db: Any, cast: Any
) -> None:
    from tests import helpers

    db = ones_db
    org = helpers.insert_idea(db, stage="shipped")
    hidden = helpers.insert_idea(db, stage="shipped")
    db.execute("UPDATE ideas SET visibility = 'committee' WHERE idea_id = %s", (hidden,))
    assert service.public_label(db, "idea", org) is not None
    assert service.public_label(db, "idea", hidden) is None
    cid = "CL-0951"
    db.execute("INSERT INTO clusters (id, stage, distinct_contributors) VALUES (%s, 'shipped', 2)", (cid,))
    db.execute("UPDATE ideas SET cluster_id = %s WHERE idea_id = ANY(%s)", (cid, [org, hidden]))
    assert service.public_label(db, "cluster", cid) == "A group of 2 ideas"
    db.execute("UPDATE ideas SET visibility = 'org' WHERE idea_id = %s", (hidden,))
    assert service.public_label(db, "cluster", cid) not in (None, "A group of 2 ideas")


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


@pytest.mark.stack
def test_picked_this_month_comes_from_stage_history(ones_db: Any, cast: Any) -> None:
    """BLD-137: an idea counts as picked in the month it first reached a picked stage, not every month after."""
    from tests import helpers

    db = ones_db

    def picked(month: dt.date) -> int:
        return sum(r["picked"] for r in service.build(db, month)["by_lob"])

    idea = helpers.insert_idea(db, stage="scanned")
    nov0, dec0 = picked(dt.date(2026, 11, 1)), picked(dt.date(2026, 12, 1))
    db.execute("UPDATE ideas SET stage = 'picked' WHERE idea_id = %s", (idea,))
    db.execute(
        "UPDATE idea_stage_history SET at = '2026-11-20T10:00:00Z' WHERE to_stage = 'picked' "
        "AND idea_uuid = (SELECT id FROM ideas WHERE idea_id = %s)",
        (idea,),
    )
    db.execute(
        "UPDATE ideas SET stage = 'in_garage' WHERE idea_id = %s", (idea,)
    )  # moving on is not a new pick
    lobs = db.execute("SELECT lobs FROM ideas WHERE idea_id = %s", (idea,)).fetchone()["lobs"]
    assert picked(dt.date(2026, 11, 1)) == nov0 + len(lobs)
    assert picked(dt.date(2026, 12, 1)) == dec0
    # A marker row for an idea already picked (migration 20261118000700) and a backfilled move inside the group
    # never count as a new pick (BLD-145).
    old_pick = helpers.insert_idea(db, stage="in_garage")
    db.execute(
        "INSERT INTO idea_stage_history (idea_uuid, from_stage, to_stage, at, source) SELECT id, 'in_garage', "
        "'in_garage', '2026-12-05T10:00:00Z', 'backfill' FROM ideas WHERE idea_id = %s",
        (old_pick,),
    )
    db.execute(
        "INSERT INTO idea_stage_history (idea_uuid, from_stage, to_stage, at, source) SELECT id, NULL, 'shipped', "
        "'2026-12-06T10:00:00Z', 'backfill' FROM ideas WHERE idea_id = %s",
        (old_pick,),
    )
    db.execute(  # its insert row (live, from nothing) belongs to another month
        "UPDATE idea_stage_history SET at = '2026-01-05T10:00:00Z' WHERE source = 'live' "
        "AND idea_uuid = (SELECT id FROM ideas WHERE idea_id = %s)",
        (old_pick,),
    )
    assert picked(dt.date(2026, 12, 1)) == dec0
    built = service.build(db, dt.date(2026, 11, 1))
    assert built["picked_in_month"] and not built["coming_soon"]


@pytest.mark.stack
def test_reading_creates_no_draft_and_draft_authors_may_leave(ones_db: Any, cast: Any) -> None:
    """BLD-140: reading never opens a draft; a draft's author can be deleted (kept in audit_log); a sent issue
    keeps its authors."""
    db = ones_db

    def count() -> int:
        return int(db.execute("SELECT count(*) AS n FROM ember_issues").fetchone()["n"])

    before = count()
    assert service.current_draft(db, cast["admin"]) == {"id": None}
    service.archive(db)
    assert count() == before  # nothing opened by looking

    # Months no other test has used in this database: a month that already has an issue would hand back that
    # issue (and its own author) instead of opening a new one.
    taken = {r["month"] for r in db.execute("SELECT month FROM ember_issues").fetchall()}
    free = [f"{y}-{m:02d}" for y in range(2040, 2060) for m in range(1, 13) if dt.date(y, m, 1) not in taken]

    leaver = person(db, "admin")
    issue = service.draft(db, leaver, {"month": free[0]}, now=NOW)
    assert issue["created"]
    db.execute("DELETE FROM users WHERE id = %s", (leaver,))
    row = db.execute("SELECT created_by FROM ember_issues WHERE id = %s", (issue["id"],)).fetchone()
    assert row["created_by"] is None
    audit = db.execute(  # the drafting row itself, picked by action, entity and month
        "SELECT actor FROM audit_log WHERE action = 'ember.drafted' AND entity = %s AND after ->> 'month' = %s "
        "ORDER BY id DESC LIMIT 1",
        (f"ember:{issue['id']}", f"{free[0]}-01"),
    ).fetchone()
    assert audit["actor"] == f"user:{leaver}"  # who opened it stays on record after they leave

    author = person(db, "admin")
    sent = service.draft(db, author, {"month": free[1]}, now=NOW)
    assert sent["created"]
    service.set_note(db, cast["chair"], sent["id"], {"note": NOTE})
    service.approve_note(db, cast["chair"], sent["id"], now=NOW)
    token = {"confirm_token": service.view(db, cast["admin"], sent["id"])["confirm_token"]}
    service.send(db, cast["admin"], sent["id"], token, now=NOW)
    with pytest.raises(Exception, match="keeps its authors"):
        db.execute("DELETE FROM users WHERE id = %s", (author,))
