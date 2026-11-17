"""L-NOTIFY and L-INBOX in the database (BLD-A180, BLD-A200 to A203): `notify.post` writes one in-app item per
recipient and queues email by preference; decisions, reversals and merges always go out (L-NOTIFY/4); Teams waits
for its switch (DEC-105); no message carries anyone's words or a reason (L-NOTIFY/3); `resolve` takes an item off
"Needs you"; the Inbox's tabs and counts agree; the decide-by digest goes to the review desk."""

from __future__ import annotations

import datetime as dt
import secrets
import uuid
from typing import Any
from zoneinfo import ZoneInfo

import pytest

import notify
from comms.send import send_due
from core import killswitch
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
    db.execute("UPDATE kill_switches SET state = 'off' WHERE name = 'comms.teams'")  # as shipped (DEC-105)
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
        (("mine", "kavya", "with_review_desk", 2), ("ravis", "ravi", "with_review_desk", None), ("draft", "kavya", "draft", None))
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
        "SELECT channel, kind, state, needs_you, dedupe_key FROM notifications WHERE user_id = %s ORDER BY id", (user,)
    ).fetchall()


def test_L_NOTIFY_post_writes_in_app_at_once_and_queues_email_by_preference(cast: Any) -> None:
    db, p, ideas = cast["db"], cast["p"], cast["ideas"]
    posted = notify.post(db, "comment", [p["kavya"]["id"], p["kavya"]["id"], p["ravi"]["id"]],
                         idea_id=ideas["mine"], sender=p["ravi"]["id"], refs={"entry_id": 42})  # fmt: skip
    assert len(posted.ids) == 1  # the sender is never a recipient; a name listed twice gets one item
    assert [(r["channel"], r["kind"]) for r in _rows(db, p["kavya"]["id"])] == [("in_app", "comment"), ("email", "comment")]
    assert _rows(db, p["ravi"]["id"]) == []
    db.execute("INSERT INTO comms_prefs (user_id, email, teams) VALUES (%s, false, false)", (p["rohan"]["id"],))
    notify.post(db, "mention", [p["rohan"]["id"], p["left"]["id"]], idea_id=ideas["mine"], sender=p["ravi"]["id"])
    assert [r["channel"] for r in _rows(db, p["rohan"]["id"])] == ["in_app"]  # email off: in-app only
    assert _rows(db, p["left"]["id"]) == []  # people who have left get nothing


def test_L_NOTIFY_4_decisions_reversals_and_merges_always_go_out_and_teams_waits_for_its_switch(cast: Any) -> None:
    db, p, ideas = cast["db"], cast["p"], cast["ideas"]
    db.execute("INSERT INTO comms_prefs (user_id, email, teams) VALUES (%s, false, true)", (p["kavya"]["id"],))
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
    assert notify.outside_channels("answer_reminder", email=True, teams=True, reminders=False, teams_on=True) == []


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
    assert "declined your team-up request, with a reason" in mail.text and "/ideas/IDEA-2026-000900" in mail.text
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
    # A key resolves the keys under it: both answer reminders of a set go with "answer_reminder:<set>".
    s = str(uuid.uuid4())
    for hours in (24, 2):
        notify.post(db, "answer_reminder", [p["kavya"]["id"]], idea_id=ideas["mine"], needs_you=True,
                    due_at=WORKDAY_NOON, refs={"set_id": s}, dedupe_key=f"answer_reminder:{s}:{hours}")  # fmt: skip
    assert notify.resolve(db, f"answer_reminder:{s}") == 2


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
            "INSERT INTO questions (set_id, seq, part, text_encrypted) VALUES (%s, %s, 'summary', '\\x00')", (s, seq)
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
    assert got["items"][0]["actions"] == [{"label": "Carry on", "style": "primary", "to": f"/share/{ideas['draft']}"}]
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


def test_L_INBOX_a_message_with_no_kind_shows_as_a_note_from_1pc_club(cast: Any) -> None:
    """J-ONE step 3: "You're No. 17." arrives through the Ones flow, which has no Inbox kind (BLD-A202)."""
    db, p = cast["db"], cast["p"]
    one = db.execute(
        "INSERT INTO ones (induction_no, user_id, number, tier, way_in, swap_until) "
        "VALUES (9017, %s, 17, 1, 'accepted_idea', now() + interval '30 days') RETURNING id",
        (p["kavya"]["id"],),
    ).fetchone()["id"]
    db.execute(
        "INSERT INTO notifications (user_id, channel, template, payload, event, urgency, state, sent_at) "
        "VALUES (%s, 'in_app', 'one-inducted', %s, 'ones.inducted', 'immediate', 'sent', now())",
        (p["kavya"]["id"], f'{{"one_id": {one}, "current_owner_ids": ["{p["kavya"]["id"]}"]}}'),
    )
    got = inbox.items(db, p["kavya"]["id"])
    item = got["items"][0]
    assert item["kind"] == "notice" and item["from"] == "system" and item["line"].startswith("You're No. 17")
    assert item["actions"] and item["actions"][0]["to"].startswith("/")
    assert got["unread"] == 1


def test_L_INBOX_actions_go_to_the_lane_that_owns_the_op(cast: Any) -> None:
    db, p, ideas = cast["db"], cast["p"], cast["ideas"]
    posted = notify.post(db, "teamup_request", [p["kavya"]["id"]], idea_id=ideas["mine"], sender=p["ravi"]["id"],
                         needs_you=True, refs={"request_id": str(uuid.uuid4()), "request": "team_only"},
                         actions=[Action("Decline", "text", op="decline")])  # fmt: skip
    item = posted.ids[0]
    with pytest.raises(inbox.InboxRefused) as refused:
        inbox.action(db, p["kavya"]["id"], item, "decline")
    assert refused.value.code == "not_available"  # until lane F registers it
    seen: list[str] = []

    @ops.register("teamup_request", "decline")
    def _decline(conn: Any, user_id: str, row: dict[str, Any]) -> dict[str, Any]:
        seen.append(user_id)
        return {"ok": True}

    try:
        assert inbox.action(db, p["kavya"]["id"], item, "decline")["result"] == {"ok": True}
        with pytest.raises(inbox.InboxRefused):
            inbox.action(db, p["kavya"]["id"], item, "merge")  # not offered on this item
    finally:
        ops._OPS.clear()
    assert seen == [p["kavya"]["id"]]


def test_L_REVIEW_clock_3_the_decide_by_digest_goes_to_the_review_desk_once_a_day(cast: Any, monkeypatch: Any) -> None:
    db, p = cast["db"], cast["p"]
    assert digest.queue(db, now=dt.datetime(2026, 11, 21, 12, 0, tzinfo=IST)) == 0  # a Saturday
    assert digest.queue(db, now=WORKDAY_NOON) == 1  # Meera, the only reviewer (no lead role yet)
    assert digest.queue(db, now=WORKDAY_NOON) == 0  # once a day
    sent: list[Any] = []
    monkeypatch.setattr("comms.send._smtp", lambda to, email: sent.append((to, email)))
    db.execute("UPDATE notifications SET send_after = now() - interval '1 minute' WHERE event = %s", (digest.EVENT,))
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
        "SELECT state, attempts FROM notifications WHERE user_id = %s AND channel = 'email'", (p["kavya"]["id"],)
    ).fetchone()
    assert row["state"] == "queued" and row["attempts"] == 1  # retried later; the in-app item is already there
    assert tables_containing(db, TITLE) == ["ideas.title"]  # the title lives on the idea only
