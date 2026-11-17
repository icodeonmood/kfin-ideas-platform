"""L-NOTIFY and L-INBOX in the database (BLD-A180, BLD-A200 to A203): `notify.post` writes one in-app item per
recipient and queues email by preference; decisions, reversals and merges always go out (L-NOTIFY/4); Teams waits
for its switch (DEC-105); no message carries anyone's words or a reason (L-NOTIFY/3); `resolve` takes an item off
"Needs you"; the Inbox's tabs and counts agree; the decide-by digest is off at launch (BLD-B241) and, once switched
on, goes to the review desk."""

from __future__ import annotations

import datetime as dt
import secrets
import uuid
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from psycopg.types.json import Jsonb

import notify
from comms.send import send_due
from core import killswitch
from core.config import Settings, get_settings
from notify import Action, digest, inbox, ops
from notify import render as nrender
from tests.helpers import tables_containing

IST = ZoneInfo("Asia/Kolkata")
TITLE = "Investors call to ask why a redemption was rejected"
REASON = "We already have a fix for the SMS wording in the next release"
WORKDAY_NOON = dt.datetime(2026, 11, 18, 12, 0, tzinfo=IST)  # a Wednesday


@pytest.fixture
def cast(db: Any) -> dict[str, Any]:
    db.execute("DELETE FROM jobs")
    db.execute(  # as shipped (DEC-105), even if a test before this one removed the switch
        "INSERT INTO kill_switches (name, state) VALUES ('comms.teams', 'off') "
        "ON CONFLICT (name) DO UPDATE SET state = 'off'"
    )
    killswitch.clear_cache()
    tag = secrets.token_hex(3)
    people: dict[str, Any] = {}
    for key, name in (("kavya", "Kavya Menon"), ("meera", "Meera Iyer"), ("ravi", "Ravi Nair"),
                      ("rohan", "Rohan Mehta"), ("left", "Gone Person")):  # fmt: skip
        u = db.execute(
            "INSERT INTO users (emp_id_hash, name, first_name, email, source, active) VALUES (%s, %s, %s, %s, 'hr', %s) "
            "RETURNING id",
            (f"test:{key}:{tag}", name, name.split()[0], f"{key}.{tag}@kfintech.example", key != "left"),
        ).fetchone()
        code = f"CTR-{secrets.token_hex(3)}"
        db.execute("INSERT INTO contributor_map (contributor_code, user_id) VALUES (%s, %s)", (code, u["id"]))
        people[key] = {"id": str(u["id"]), "code": code, "email": f"{key}.{tag}@kfintech.example"}
    db.execute("INSERT INTO role_grants (user_id, role) VALUES (%s, 'reviewer')", (people["meera"]["id"],))
    ideas: dict[str, str] = {}
    for n, (key, owner, status, late) in enumerate(
        (
            ("mine", "kavya", "with_review_desk", 2),
            ("ravis", "ravi", "with_review_desk", None),
            ("draft", "kavya", "draft", None),
        )
    ):
        idea_uuid = str(uuid.uuid4())
        db.execute(
            "INSERT INTO ideas (id, idea_id, submission_id, stage, capture_mode, contributor_code, canvas, strength, "
            "submitted_at, status, title, decide_by, reviewer_id) VALUES (%s, %s, %s, 'scanned', 'quick', %s, '{}', 2, "
            "now(), %s, %s, %s, %s)",
            (idea_uuid, f"IDEA-2026-0009{n:02d}", f"SUB-2026-0009{n:02d}", people[owner]["code"], status,
             TITLE if key == "mine" else f"Synthetic idea {n}",
             (WORKDAY_NOON - dt.timedelta(days=late)) if late else None,
             people["meera"]["id"] if key == "mine" else None),
        )  # fmt: skip
        ideas[key] = idea_uuid
    return {"db": db, "p": people, "ideas": ideas}


def _rows(db: Any, user: str) -> list[dict[str, Any]]:
    return db.execute(
        "SELECT channel, kind, state, needs_you, dedupe_key FROM notifications WHERE user_id = %s ORDER BY id",
        (user,),
    ).fetchall()


def test_L_NOTIFY_post_writes_in_app_at_once_and_queues_email_by_preference(cast: Any) -> None:
    db, p, ideas = cast["db"], cast["p"], cast["ideas"]
    posted = notify.post(db, "comment", [p["kavya"]["id"], p["kavya"]["id"], p["ravi"]["id"]],
                         idea_id=ideas["mine"], sender=p["ravi"]["id"], refs={"entry_id": 42})  # fmt: skip
    assert len(posted.ids) == 1  # the sender is never a recipient; a name listed twice gets one item
    assert [(r["channel"], r["kind"]) for r in _rows(db, p["kavya"]["id"])] == [
        ("in_app", "comment"),
        ("email", "comment"),
    ]
    assert _rows(db, p["ravi"]["id"]) == []
    db.execute(
        "INSERT INTO comms_prefs (user_id, email, teams) VALUES (%s, false, false)", (p["rohan"]["id"],)
    )
    notify.post(
        db, "mention", [p["rohan"]["id"], p["left"]["id"]], idea_id=ideas["mine"], sender=p["ravi"]["id"]
    )
    assert [r["channel"] for r in _rows(db, p["rohan"]["id"])] == ["in_app"]  # email off: in-app only
    assert _rows(db, p["left"]["id"]) == []  # people who have left get nothing


def test_L_NOTIFY_4_decisions_reversals_and_merges_always_go_out_and_teams_waits_for_its_switch(
    cast: Any,
) -> None:
    db, p, ideas = cast["db"], cast["p"], cast["ideas"]
    db.execute(
        "INSERT INTO comms_prefs (user_id, email, teams) VALUES (%s, false, true)", (p["kavya"]["id"],)
    )
    for kind in ("decision", "decision_reversed", "desk_merge"):
        notify.post(db, kind, [p["kavya"]["id"]], idea_id=ideas["mine"], sender=p["meera"]["id"],
                    refs={"choice": "not_picked"})  # fmt: skip
    notify.post(db, "stage_moved", [p["kavya"]["id"]], idea_id=ideas["mine"], refs={"to": "being_built"})
    channels = [(r["kind"], r["channel"]) for r in _rows(db, p["kavya"]["id"]) if r["channel"] != "in_app"]
    # Teams is switched off (DEC-105), email is off: the three that must go out fall back to email, the stage move
    # stays in the app.
    assert channels == [("decision", "email"), ("decision_reversed", "email"), ("desk_merge", "email")]
    db.execute("UPDATE kill_switches SET state = 'on' WHERE name = 'comms.teams'")
    killswitch.clear_cache()
    notify.post(db, "decision", [p["kavya"]["id"]], idea_id=ideas["mine"], sender=p["meera"]["id"])
    assert _rows(db, p["kavya"]["id"])[-1]["channel"] == "teams"  # Teams carries it once IT switches it on
    assert (
        notify.outside_channels("answer_reminder", email=True, teams=True, reminders=False, teams_on=True)
        == []
    )


def test_L_NOTIFY_3_no_words_reasons_or_free_text_go_in(cast: Any) -> None:
    db, p, ideas = cast["db"], cast["p"], cast["ideas"]
    for bad in ({"reason": "too-short"}, {"note": "x"}, {"idea": "words with spaces in them"}):
        with pytest.raises(notify.NotifyError):
            notify.post(db, "teamup_answer", [p["kavya"]["id"]], idea_id=ideas["mine"], refs=bad)
    notify.post(db, "teamup_answer", [p["kavya"]["id"]], idea_id=ideas["mine"], sender=p["ravi"]["id"],
                refs={"request_id": str(uuid.uuid4()), "answer": "decline", "has_reason": True})  # fmt: skip
    row = db.execute(
        "SELECT * FROM notifications WHERE user_id = %s AND channel = 'email'", (p["kavya"]["id"],)
    ).fetchone()
    mail = nrender.email(db, dict(row), WORKDAY_NOON)
    assert (
        "declined your team-up request, with a reason" in mail.text and "/ideas/IDEA-2026-000900" in mail.text
    )
    assert REASON not in mail.text + mail.html  # the reason is read in the app (BLD-E004)


def test_L_NOTIFY_dedupe_keeps_one_item_and_resolve_takes_it_off_needs_you(cast: Any) -> None:
    db, p, ideas = cast["db"], cast["p"], cast["ideas"]
    request = str(uuid.uuid4())
    for _ in range(2):  # a retry posts the same key again
        notify.post(db, "teamup_request", [p["kavya"]["id"]], idea_id=ideas["mine"], sender=p["ravi"]["id"],
                    needs_you=True, refs={"request_id": request, "request": "merge", "brought": 1},
                    actions=[Action("Decline", "text", op="decline"), Action("Team up only", op="team_only"),
                             Action("Merge it", "primary", op="merge")],
                    dedupe_key=f"teamup_request:{request}")  # fmt: skip
    assert [r["channel"] for r in _rows(db, p["kavya"]["id"])] == ["in_app", "email"]
    assert inbox.counts(db, p["kavya"]["id"])["needs_you"] == 1
    assert notify.resolve(db, f"teamup_request:{request}", recipients=[p["ravi"]["id"]]) == 0  # not theirs
    assert notify.resolve(db, f"teamup_request:{request}") == 1
    assert notify.resolve(db, f"teamup_request:{request}") == 0  # twice is harmless
    assert inbox.counts(db, p["kavya"]["id"])["needs_you"] == 0
    # A key resolves the keys under it: lane B's "qs:<set>" takes the questions item and both answer reminders
    # ("qs:<set>:24", "qs:<set>:2") off "Needs you" when the answers are sent (BLD-A180, L-INBOX.rules/3).
    s = str(uuid.uuid4())
    notify.post(db, "questions", [p["kavya"]["id"]], idea_id=ideas["mine"], needs_you=True, due_at=WORKDAY_NOON,
                refs={"set_id": s}, dedupe_key=f"qs:{s}")  # fmt: skip
    for hours in (24, 2):
        notify.post(db, "answer_reminder", [p["kavya"]["id"]], idea_id=ideas["mine"], needs_you=True,
                    due_at=WORKDAY_NOON, refs={"set_id": s}, dedupe_key=f"qs:{s}:{hours}")  # fmt: skip
    notify.post(
        db,
        "questions",
        [p["kavya"]["id"]],
        idea_id=ideas["mine"],
        needs_you=True,
        due_at=WORKDAY_NOON,
        refs={"set_id": s},
        dedupe_key=f"qs:{s}0",
    )  # another key that only starts the same way
    # Lane B keys each reminder by its threshold with the offset (BLD-A200): the key under "qs:<set>" is taken too.
    notify.post(db, "answer_reminder", [p["kavya"]["id"]], idea_id=ideas["mine"], needs_you=True,
                due_at=WORKDAY_NOON, refs={"set_id": s}, dedupe_key=f"qs:{s}:20261119T1020+0530")  # fmt: skip
    assert notify.resolve(db, f"qs:{s}") == 4
    assert inbox.counts(db, p["kavya"]["id"])["needs_you"] == 1


def test_L_NOTIFY_a_repeat_key_updates_the_open_item_in_place(cast: Any) -> None:
    """BLD-A188, V-ACC.track/3 (one countdown everywhere): lane B's "Give 2 more days" posts `questions` again under
    `qs:<set>` with the new due date and `more_time`. The same row moves its date and refs; no second row and no
    second email; read stays read. Once resolved, a repeat post changes nothing."""
    db, p, ideas = cast["db"], cast["p"], cast["ideas"]
    kavya = p["kavya"]["id"]
    s = str(uuid.uuid4())
    first_due, later_due = WORKDAY_NOON + dt.timedelta(days=3), WORKDAY_NOON + dt.timedelta(days=5)
    posted = notify.post(db, "questions", [kavya], idea_id=ideas["mine"], sender=p["meera"]["id"], needs_you=True,
                         due_at=first_due, refs={"set_id": s}, dedupe_key=f"qs:{s}")  # fmt: skip
    item = posted.ids[0]
    inbox.mark_read(db, kavya, item)
    again = notify.post(db, "questions", [kavya], idea_id=ideas["mine"], sender=p["meera"]["id"], needs_you=True,
                        due_at=later_due, refs={"set_id": s, "more_time": True},
                        actions=[Action("Answer the questions", "primary", to="answer")],
                        dedupe_key=f"qs:{s}")  # fmt: skip
    assert again.ids == [] and again.updated == [item]
    rows = db.execute(
        "SELECT id, channel, due_at, payload, actions, needs_you, read_at FROM notifications WHERE user_id = %s "
        "ORDER BY id",
        (kavya,),
    ).fetchall()
    assert [r["channel"] for r in rows] == ["in_app", "email"]  # one item, one email in total
    mine = rows[0]
    assert (
        mine["id"] == item
        and mine["due_at"] == later_due
        and mine["payload"] == {"set_id": s, "more_time": True}
    )
    assert mine["actions"] == [{"label": "Answer the questions", "style": "primary", "to": "answer"}]
    assert mine["needs_you"] and mine["read_at"] is not None  # read stays read
    assert rows[1]["due_at"] == later_due  # the email still waiting to go says the new date
    assert inbox.items(db, kavya, now=WORKDAY_NOON)["items"][0]["due"]["label"] == "5 days left"
    # Resolved: a repeat post leaves the item as it is and posts nothing.
    assert notify.resolve(db, f"qs:{s}") == 1
    late = notify.post(db, "questions", [kavya], idea_id=ideas["mine"], needs_you=True,
                       due_at=later_due + dt.timedelta(days=1), refs={"set_id": s}, dedupe_key=f"qs:{s}")  # fmt: skip
    assert late == notify.Posted()
    after = db.execute("SELECT due_at, needs_you FROM notifications WHERE id = %s", (item,)).fetchone()
    assert after["due_at"] == later_due and not after["needs_you"]
    assert (
        db.execute("SELECT count(*) AS n FROM notifications WHERE user_id = %s", (kavya,)).fetchone()["n"]
        == 2
    )


def test_L_INBOX_tabs_counts_read_archive_and_the_kinds_lines(cast: Any) -> None:
    db, p, ideas = cast["db"], cast["p"], cast["ideas"]
    kavya = p["kavya"]["id"]
    s = db.execute(
        "INSERT INTO question_sets (idea_uuid, by_user_id, state, sent_at, due_at) VALUES (%s, %s, 'sent', now(), %s) "
        "RETURNING id",
        (ideas["mine"], p["meera"]["id"], WORKDAY_NOON + dt.timedelta(days=3)),
    ).fetchone()["id"]
    for seq in (1, 2, 3):
        db.execute(
            "INSERT INTO questions (set_id, seq, part, text_encrypted) VALUES (%s, %s, 'summary', '\\x00')",
            (s, seq),
        )
    notify.post(db, "questions", [kavya], idea_id=ideas["mine"], sender=p["meera"]["id"], needs_you=True,
                due_at=WORKDAY_NOON + dt.timedelta(days=3), refs={"set_id": str(s)},
                actions=[Action("Answer the questions", "primary", to="/ideas/IDEA-2026-000900/answer")],
                dedupe_key=f"questions:{s}")  # fmt: skip
    notify.post(db, "decision_reversed", [kavya], idea_id=ideas["mine"], sender=p["rohan"]["id"],
                refs={"window_id": str(uuid.uuid4()), "to": "pick"})  # fmt: skip
    notify.post(db, "draft_kept", [kavya], idea_id=ideas["draft"], refs={"via": "phone"})
    got = inbox.items(db, kavya, "all", now=WORKDAY_NOON)
    lines = [(it["body"]["sender"], it["line"]) for it in got["items"]]
    assert lines == [
        ("1% Club", "kept your draft from your phone"),
        ("Rohan Mehta from the Ones Committee", "reversed a decision on your idea"),
        ("Meera from the review desk", "asked you 3 questions"),
    ]
    q = got["items"][2]
    assert q["needs_you"] and q["due"]["label"] == "3 days left" and q["idea"]["title"] == TITLE
    assert q["body"]["heading"] == "Questions from the review desk"
    assert q["body"]["note"] == "Answer by Saturday 21 November, 12 pm."
    # The forward action is last and primary; "Open the conversation" is a line button before it (S-H5.rules/3).
    assert [(a["label"], a["style"]) for a in q["actions"]] == [
        ("Open the conversation", "line"), ("Answer the questions", "primary")]  # fmt: skip
    assert got["items"][0]["actions"] == [
        {"label": "Carry on", "style": "primary", "to": f"/share/{ideas['draft']}"}
    ]
    assert got["counts"] == {"all": 3, "needs_you": 1, "unread": 3, "archived": 0} and got["unread"] == 3

    with pytest.raises(inbox.InboxRefused) as refused:
        inbox.archive(db, kavya, int(q["id"]))
    assert refused.value.code == "needs_you"  # an open ask cannot be archived (L-INBOX.rules/5)
    after = inbox.mark_read(db, kavya, int(got["items"][1]["id"]))
    assert after["unread"] == 2
    after = inbox.archive(db, kavya, int(got["items"][0]["id"]))
    assert after == {"all": 2, "needs_you": 1, "unread": 1, "archived": 1}
    assert inbox.mark_unread(db, kavya, int(got["items"][1]["id"]))["unread"] == 2
    assert inbox.mark_all_read(db, kavya)["unread"] == 0
    home = inbox.needs_you(db, kavya)
    assert home["total"] == 1 and home["top"][0]["kind"] == "questions"
    with pytest.raises(inbox.InboxRefused):
        inbox.mark_read(db, p["ravi"]["id"], int(q["id"]))  # someone else's item


def test_L_INBOX_J_ONE_3_a_new_one_gets_no_inbox_item_and_old_route_messages_stay_out(cast: Any) -> None:
    """BLD-A186, BLD-A202: "You're No. 17" arrives through the Ones flow by email; the Inbox, its counts and Home's
    "Needs you" hold only the E-ENUMS.inbox kinds, so the sidebar, the tab bar and the Inbox agree."""
    db, p, ideas = cast["db"], cast["p"], cast["ideas"]
    kavya = p["kavya"]["id"]
    one = db.execute(
        "INSERT INTO ones (induction_no, user_id, number, tier, way_in, swap_until) "
        "VALUES (9017, %s, 17, 1, 'accepted_idea', now() + interval '30 days') RETURNING id",
        (kavya,),
    ).fetchone()["id"]
    try:
        db.execute(
            "INSERT INTO notifications (user_id, channel, template, payload, event, urgency, state, sent_at) "
            "VALUES (%s, 'in_app', 'one-inducted', %s, 'ones.inducted', 'immediate', 'sent', now())",
            (kavya, f'{{"one_id": {one}, "current_owner_ids": ["{kavya}"]}}'),
        )
        legacy = db.execute("SELECT id FROM notifications WHERE user_id = %s", (kavya,)).fetchone()["id"]
        got = inbox.items(db, kavya)
        assert got["items"] == [] and got["counts"] == {"all": 0, "needs_you": 0, "unread": 0, "archived": 0}
        with pytest.raises(inbox.InboxRefused):
            inbox.mark_read(db, kavya, int(legacy))  # not an Inbox item
        notify.post(db, "stage_moved", [kavya], idea_id=ideas["mine"], refs={"to": "shipped"})
        assert [it["line"] for it in inbox.items(db, kavya)["items"]] == ["moved your idea to Shipped"]
        assert inbox.mark_all_read(db, kavya)["unread"] == 0
        assert (
            db.execute("SELECT read_at FROM notifications WHERE id = %s", (legacy,)).fetchone()["read_at"]
            is None
        )
    finally:
        db.execute("DELETE FROM notifications WHERE user_id = %s", (kavya,))
        db.execute("DELETE FROM ones WHERE id = %s", (one,))


def test_L_HIDE_7_detail_hidden_by_desk_comes_from_the_review_desk_with_one_action(cast: Any) -> None:
    """BLD-A205: lane C posts it when a reviewer hides a detail. The reviewer's name is never shown or sent; it is
    not "Needs you"; it carries no refs; its one action opens the idea."""
    db, p, ideas = cast["db"], cast["p"], cast["ideas"]
    kavya = p["kavya"]["id"]
    with pytest.raises(notify.NotifyError):
        notify.post(db, "detail_hidden_by_desk", [kavya], idea_id=ideas["mine"], refs={"part": "summary"})
    check = db.execute(
        "SELECT pg_get_constraintdef(oid) AS d FROM pg_constraint WHERE conname = 'notifications_kind_check'"
    ).fetchone()["d"]
    widen = (
        "detail_hidden_by_desk" not in check
    )  # lane C's c/hide adds the kind to the CHECK; until then, here
    if widen:
        db.execute("ALTER TABLE notifications DROP CONSTRAINT notifications_kind_check")
        db.execute(
            "ALTER TABLE notifications ADD CONSTRAINT notifications_kind_check "
            + check.replace(
                "'answer_reminder'::text", "'answer_reminder'::text, 'detail_hidden_by_desk'::text"
            )
        )
    try:
        posted = notify.post(
            db, "detail_hidden_by_desk", [kavya], idea_id=ideas["mine"], sender=p["meera"]["id"]
        )
        assert len(posted.ids) == 1
        item = inbox.items(db, kavya, now=WORKDAY_NOON)["items"][0]
        assert item["kind"] == "detail_hidden_by_desk" and item["from"] == "system" and not item["needs_you"]
        assert (item["body"]["sender"], item["line"]) == (
            "The review desk",
            "hid a customer’s detail in your idea",
        )
        assert (
            item["body"]["heading"] == "A detail was hidden"
            and item["body"]["note"] == "Only you can still see it."
        )
        assert item["actions"] == [
            {"label": "Open your idea", "style": "primary", "to": "/ideas/IDEA-2026-000900"}
        ]
        assert "Meera" not in repr(item)
        row = db.execute(
            "SELECT * FROM notifications WHERE user_id = %s AND channel = 'email'", (kavya,)
        ).fetchone()
        assert row["payload"] == {}
        # Not even stored: the item and its email carry no sender, so no later read can name the reviewer.
        senders = db.execute(
            "SELECT channel, from_user_id FROM notifications WHERE user_id = %s ORDER BY id", (kavya,)
        ).fetchall()
        assert [(r["channel"], r["from_user_id"]) for r in senders] == [("in_app", None), ("email", None)]
        mail = nrender.email(db, dict(row), WORKDAY_NOON)
        assert "The review desk hid a customer’s detail in your idea" in mail.text
        assert "Only you can still see it." in mail.text and "Meera" not in mail.text + mail.html
    finally:
        db.execute("DELETE FROM notifications WHERE user_id = %s", (kavya,))
        if widen:
            db.execute("ALTER TABLE notifications DROP CONSTRAINT notifications_kind_check")
            db.execute("ALTER TABLE notifications ADD CONSTRAINT notifications_kind_check " + check)


def test_L_NOTIFY_3_J_TEAMUP_4_the_request_email_opens_the_leads_item_in_the_app(cast: Any) -> None:
    """The email row has no buttons of its own, so "Answer the request" uses the kind's "inbox" link: it opens the
    person's in-app item (found by its key, else by the idea), never the email row's id; with no item, the Inbox."""
    db, p, ideas = cast["db"], cast["p"], cast["ideas"]
    kavya = p["kavya"]["id"]
    request = str(uuid.uuid4())
    # Lane F's call (BLD-A188): bare ops under teamup_request, refs {request_id, request, brought}.
    posted = notify.post(db, "teamup_request", [kavya], idea_id=ideas["mine"], sender=p["ravi"]["id"],
                         needs_you=True, refs={"request_id": request, "request": "merge", "brought": 1},
                         actions=[Action("Decline", "text", op="decline"), Action("Team up only", op="team_only"),
                                  Action("Merge it", "primary", op="merge")],
                         dedupe_key=f"teamup_request:{request}")  # fmt: skip
    item = posted.ids[0]
    mail_row = dict(
        db.execute(
            "SELECT * FROM notifications WHERE user_id = %s AND channel = 'email'", (kavya,)
        ).fetchone()
    )
    assert mail_row["id"] != item and not mail_row["actions"]  # an email row carries no buttons
    mail = nrender.email(db, mail_row, WORKDAY_NOON)
    assert f"/inbox/{item}" in mail.text and f"/inbox/{mail_row['id']}" not in mail.text + mail.html
    assert "Answer the request" in mail.text
    # An item posted with no key is found by its idea: the latest of its kind posted before the email.
    other = notify.post(db, "teamup_request", [kavya], idea_id=ideas["mine"], sender=p["rohan"]["id"],
                        needs_you=True, refs={"request_id": str(uuid.uuid4()), "request": "team_only"},
                        actions=[Action("Decline", "text", op="decline"),
                                 Action("Approve", "primary", op="team_only")])  # fmt: skip
    second = dict(
        db.execute(
            "SELECT * FROM notifications WHERE user_id = %s AND channel = 'email' ORDER BY id DESC LIMIT 1",
            (kavya,),
        ).fetchone()
    )
    assert second["dedupe_key"] is None
    assert f"/inbox/{other.ids[0]}" in nrender.email(db, second, WORKDAY_NOON).text
    # No in-app item left to open: the plain Inbox.
    db.execute("DELETE FROM notifications WHERE user_id = %s AND channel = 'in_app'", (kavya,))
    text = nrender.email(db, mail_row, WORKDAY_NOON).text
    assert "/inbox/" not in text and "/inbox" in text


@pytest.mark.parametrize(
    ("refs", "line", "label"),
    [
        ({"via": "phone"}, "kept your draft from your phone", "Carry on"),
        ({"via": "email"}, "kept your draft from email", "Check and send"),
        ({"via": "teams"}, "kept your draft from Teams", "Check and send"),
        ({}, "kept your draft", "Carry on"),
        ({"via": "fax"}, "kept your draft", "Carry on"),
    ],
    ids=["phone", "email", "teams", "missing", "unknown"],
)
def test_L_INBOX_J_RESUME_5_6_draft_kept_reads_and_acts_by_via(
    cast: Any, refs: dict[str, Any], line: str, label: str
) -> None:
    """BLD-A188: lane C posts `via` (phone|email|teams) and no buttons; the line and the one button follow it, and
    every button opens the draft on S-04B. A missing or unknown `via` is never read as the phone."""
    db, p, ideas = cast["db"], cast["p"], cast["ideas"]
    kavya = p["kavya"]["id"]
    notify.post(db, "draft_kept", [kavya], idea_id=ideas["draft"], refs=refs)
    got = inbox.items(db, kavya, now=WORKDAY_NOON)["items"][0]
    assert (got["body"]["sender"], got["line"]) == ("1% Club", line)
    assert got["actions"] == [{"label": label, "style": "primary", "to": f"/share/{ideas['draft']}"}]
    row = db.execute(
        "SELECT * FROM notifications WHERE user_id = %s AND channel = 'email'", (kavya,)
    ).fetchone()
    mail = nrender.email(db, dict(row), WORKDAY_NOON)
    assert f"1% Club {line}: " in mail.text
    assert f"{label}" in mail.text and f"/share/{ideas['draft']}" in mail.text
    assert ("Carry on" if label == "Check and send" else "Check and send") not in mail.text + mail.html
    assert "your phone" not in mail.text or refs.get("via") == "phone"


def test_L_INBOX_kinds_items_that_name_no_set_choice_or_request_read_them_from_the_idea(cast: Any) -> None:
    """Items written without refs (the 1% Club seed, BLD-A206) read the set, the decision and the request kind from
    the idea and the item's own buttons, so their lines match the pack's."""
    db, p, ideas = cast["db"], cast["p"], cast["ideas"]
    kavya, ravi = p["kavya"]["id"], p["ravi"]["id"]
    s = db.execute(
        "INSERT INTO question_sets (idea_uuid, by_user_id, state, sent_at, due_at) VALUES (%s, %s, 'sent', now(), %s) "
        "RETURNING id",
        (ideas["mine"], p["meera"]["id"], WORKDAY_NOON + dt.timedelta(days=2)),
    ).fetchone()["id"]
    for seq in (1, 2):
        db.execute(
            "INSERT INTO questions (set_id, seq, part, text_encrypted) VALUES (%s, %s, 'summary', '\\x00')",
            (s, seq),
        )
    db.execute(
        "INSERT INTO idea_decisions (idea_uuid, choice, reason_encrypted, by_user_id) VALUES (%s, 'pick', '\\x00', %s)",
        (ideas["mine"], p["meera"]["id"]),
    )
    rows: tuple[tuple[str, str, str | None, bool, dt.datetime | None, list[dict[str, str]]], ...] = (
        (kavya, "questions", p["meera"]["id"], True, WORKDAY_NOON + dt.timedelta(days=2), []),
        (kavya, "answer_reminder", None, True, WORKDAY_NOON + dt.timedelta(hours=5), []),
        (kavya, "decision", p["meera"]["id"], False, None, []),
        (ravi, "teamup_request", kavya, True, None,
         [{"label": "Decline", "op": "decline", "style": "text"}, {"label": "Merge it", "op": "merge", "style": "primary"}]),
    )  # fmt: skip
    for to, kind, sender, needs, due, actions in rows:
        db.execute(
            "INSERT INTO notifications (user_id, channel, template, event, payload, state, sent_at, kind, from_user_id, "
            "idea_uuid, needs_you, due_at, actions) VALUES (%s, 'in_app', %s, %s, '{}', 'sent', now(), %s, %s, %s, %s, "
            "%s, %s)",
            (to, f"inbox/{kind}", f"inbox.{kind}", kind, sender, ideas["mine"], needs, due,
             Jsonb(actions)),
        )  # fmt: skip
    mine = {it["kind"]: it for it in inbox.items(db, kavya, now=WORKDAY_NOON)["items"]}
    assert mine["questions"]["line"] == "asked you 2 questions" and mine["questions"]["body"][
        "set_id"
    ] == str(s)
    assert mine["answer_reminder"]["line"] == "5 hours left to answer Meera’s questions"
    assert mine["answer_reminder"]["body"]["sender"] == "1% Club"
    assert mine["decision"]["line"] == "picked your idea"
    request = inbox.items(db, ravi, now=WORKDAY_NOON)["items"][0]
    assert request["line"] == "asks to team up and merge their idea into yours"
    assert request["body"]["heading"] == "Merge request"


def test_L_INBOX_actions_go_to_the_lane_that_owns_the_op(cast: Any) -> None:
    db, p, ideas = cast["db"], cast["p"], cast["ideas"]
    posted = notify.post(db, "teamup_request", [p["kavya"]["id"]], idea_id=ideas["mine"], sender=p["ravi"]["id"],
                         needs_you=True, refs={"request_id": str(uuid.uuid4()), "request": "team_only"},
                         actions=[Action("Decline", "text", op="decline")])  # fmt: skip
    item = posted.ids[0]
    # Lane F's team-up handlers register when the teamup package is imported (BLD-F028); this test checks the
    # Inbox's own routing with a stand-in, so it sets them aside and puts them back afterwards.
    saved = dict(ops._OPS)
    ops._OPS.clear()
    seen: list[str] = []
    try:
        with pytest.raises(inbox.InboxRefused) as refused:
            inbox.action(db, p["kavya"]["id"], item, "decline")
        assert refused.value.code == "not_available"  # no lane has registered this op

        @ops.register("teamup_request", "decline")
        def _decline(conn: Any, user_id: str, row: dict[str, Any]) -> dict[str, Any]:
            seen.append(user_id)
            return {"ok": True}

        assert inbox.action(db, p["kavya"]["id"], item, "decline")["result"] == {"ok": True}
        with pytest.raises(inbox.InboxRefused):
            inbox.action(db, p["kavya"]["id"], item, "merge")  # not offered on this item
    finally:
        ops._OPS.clear()
        ops._OPS.update(saved)
    assert seen == [p["kavya"]["id"]]


@pytest.fixture
def decide_by_digest(monkeypatch: Any) -> Any:
    """Sets DECIDE_BY_DIGEST for one test (BLD-A203) and leaves the cached settings as they were found."""

    def set_to(on: bool) -> None:
        monkeypatch.setenv("DECIDE_BY_DIGEST", "true" if on else "false")
        get_settings.cache_clear()

    yield set_to
    monkeypatch.delenv("DECIDE_BY_DIGEST", raising=False)
    get_settings.cache_clear()


def _digest_rows(db: Any) -> int:
    row = db.execute("SELECT count(*) AS n FROM notifications WHERE event = %s", (digest.EVENT,)).fetchone()
    return int(row["n"])


def test_L_REVIEW_clock_3_the_decide_by_digest_is_off_at_launch(cast: Any, decide_by_digest: Any) -> None:
    """BLD-B241: no overdue digest at launch, even with an idea past its decide-by date on a working day."""
    db = cast["db"]
    db.execute("DELETE FROM notifications WHERE event = %s", (digest.EVENT,))
    assert Settings.model_fields["decide_by_digest"].default is False  # the shipped default, with no env set
    decide_by_digest(False)  # and an env left over on this machine can't switch it on for this test
    assert digest.overdue(db, WORKDAY_NOON)  # Kavya's idea is two days late
    assert digest.queue(db, now=WORKDAY_NOON) == 0
    assert _digest_rows(db) == 0


def test_L_REVIEW_clock_3_the_job_still_flushes_held_mail_on_mondays_with_the_digest_off(
    cast: Any, decide_by_digest: Any, monkeypatch: Any
) -> None:
    from jobs import handlers

    db = cast["db"]
    db.execute("DELETE FROM notifications WHERE event = %s", (digest.EVENT,))
    decide_by_digest(False)
    flushed: list[Any] = []
    monkeypatch.setattr("comms.send.send_digests", lambda conn: flushed.append(conn))
    handlers.comms_digest(db, {"force": True})  # the Monday branch, whatever day the test runs
    assert flushed == [db]  # mail the old routes held still goes out
    assert _digest_rows(db) == 0  # and no decide-by email is queued


def test_L_REVIEW_clock_3_a_digest_queued_before_it_was_switched_off_is_not_sent(
    cast: Any, decide_by_digest: Any, monkeypatch: Any
) -> None:
    db = cast["db"]
    decide_by_digest(True)
    assert digest.queue(db, now=WORKDAY_NOON) == 1
    decide_by_digest(False)
    sent: list[Any] = []
    monkeypatch.setattr("comms.send._smtp", lambda to, email: sent.append((to, email)))
    db.execute(
        "UPDATE notifications SET send_after = now() - interval '1 minute' WHERE event = %s", (digest.EVENT,)
    )
    assert send_due(db) == 0 and sent == []
    row = db.execute(
        "SELECT state, error_code FROM notifications WHERE event = %s", (digest.EVENT,)
    ).fetchone()
    assert (row["state"], row["error_code"]) == ("failed", "nothing_to_send")  # marked, never mailed


def test_L_REVIEW_clock_3_switched_on_the_decide_by_digest_goes_to_the_review_desk_once_a_day(
    cast: Any, decide_by_digest: Any, monkeypatch: Any
) -> None:
    db, p = cast["db"], cast["p"]
    decide_by_digest(True)
    assert digest.queue(db, now=dt.datetime(2026, 11, 21, 12, 0, tzinfo=IST)) == 0  # a Saturday
    assert digest.queue(db, now=WORKDAY_NOON) == 1  # Meera, the only reviewer (no lead role yet)
    assert digest.queue(db, now=WORKDAY_NOON) == 0  # once a day
    sent: list[Any] = []
    monkeypatch.setattr("comms.send._smtp", lambda to, email: sent.append((to, email)))
    db.execute(
        "UPDATE notifications SET send_after = now() - interval '1 minute' WHERE event = %s", (digest.EVENT,)
    )
    assert send_due(db) == 1
    to, mail = sent[0]
    assert to == p["meera"]["email"]
    assert "1 idea is past" in mail.text and TITLE in mail.text and "IDEA-2026-000900" in mail.text
    assert "opened by Meera" in mail.text and "/desk" in mail.text


def test_L_NOTIFY_6_a_failing_mail_server_never_reaches_the_caller(cast: Any, monkeypatch: Any) -> None:
    db, p, ideas = cast["db"], cast["p"], cast["ideas"]
    notify.post(db, "decision", [p["kavya"]["id"]], idea_id=ideas["mine"], sender=p["meera"]["id"],
                refs={"choice": "pick"})  # fmt: skip

    def refuse(to: str, email: Any) -> None:
        raise OSError("mailbox unavailable")

    monkeypatch.setattr("comms.send._smtp", refuse)
    assert send_due(db, now=dt.datetime.now(dt.UTC) + dt.timedelta(minutes=1)) == 0
    row = db.execute(
        "SELECT state, attempts FROM notifications WHERE user_id = %s AND channel = 'email'",
        (p["kavya"]["id"],),
    ).fetchone()
    assert (
        row["state"] == "queued" and row["attempts"] == 1
    )  # retried later; the in-app item is already there
    assert tables_containing(db, TITLE) == ["ideas.title"]  # the title lives on the idea only
