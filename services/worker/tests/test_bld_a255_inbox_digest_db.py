"""BLD-A255 against the real tables (stack tests, CI only; BLD-A251): DEC-133's after-launch rule with DEC-138's
defaults (L-NOTIFY/1, /2, /3, /4, /5, /6).

A decision, a reversal, a merge notice, an answer reminder and anything posted as Needs you are emailed at once, as
before. Every other Inbox item queues no email (DEC-138 is an email rule: its Teams message still goes at once while
the switch and the person's setting allow). The 10:30 run of `comms.digest`, in working hours on a working day, gives
each active person with email on one digest row, covering the items that waited since their last digest (a weekend's
or a holiday's roll over), never more than 7 days back and up to 5 minutes before the run; a digest still queued from
an earlier day is carried on instead. The email is built when it is sent from the items still unread, in working
hours only and after every other email. Items posted before the rule (r6 emailed every one at once) and the club
seed's are never in it. Synthetic people only (L-NOTIFY's `cast`, shared with tests/test_notify.py)."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any
from zoneinfo import ZoneInfo

import pytest

import notify
from comms.send import send_due
from core import killswitch
from notify import digest, inbox
from tests import test_notify as l_notify
from tests.test_1pc_dec111_notify_names_db import _refs as desk_refs

cast = l_notify.cast
IST = ZoneInfo("Asia/Kolkata")
TITLE, REASON = l_notify.TITLE, l_notify.REASON
GRACE, LOOKBACK = digest.GRACE, digest.LOOKBACK
WED = dt.datetime(2026, 12, 2, 10, 30, tzinfo=IST)  # a working Wednesday at the digest's time
THU = WED + dt.timedelta(days=1)
THU_NIGHT = dt.datetime(2026, 12, 3, 22, 30, tzinfo=IST)
FRI_OPEN = dt.datetime(2026, 12, 4, 8, 0, tzinfo=IST)  # the next opening after Thursday night
FRI = dt.datetime(2026, 11, 27, 10, 30, tzinfo=IST)
SAT, SUN = FRI + dt.timedelta(days=1), FRI + dt.timedelta(days=2)
MON = FRI + dt.timedelta(days=3)
XMAS = dt.datetime(2026, 12, 25, 10, 30, tzinfo=IST)  # a Friday, a holiday in the seed's calendar
MON_AFTER = dt.datetime(2026, 12, 28, 10, 30, tzinfo=IST)
ENTRY = {"entry_id": "4c2e8a6d-0f1b-4d39-b7e5-9a3c1d5f7b28"}
AT_ONCE_REFS: dict[str, dict[str, Any]] = {
    "decision": {"decision_id": str(uuid.uuid4()), "choice": "pick"},
    "decision_reversed": {"window_id": str(uuid.uuid4()), "to": "pick"},
    "desk_merge": {"merge_id": str(uuid.uuid4())},
}
DIGEST_SUBJECT = "Your 1% Club update:"


def _post(db: Any, kind: str, to: str, idea: str, at: dt.datetime | None = None, **kw: Any) -> int:
    """Post one item to one person and, with `at`, date it then (the clock the window reads). Its in-app id."""
    posted = notify.post(db, kind, [to], idea_id=idea, **kw)  # type: ignore[arg-type]
    item = (posted.ids or posted.updated)[0]
    if at is not None:
        db.execute("UPDATE notifications SET created_at = %s WHERE id = %s", (at, item))
    return item


def _outside(db: Any, user: str) -> list[tuple[str, str]]:
    """(channel, kind) of the person's outside rows other than digests, in the order they were queued."""
    rows = db.execute(
        "SELECT channel, kind FROM notifications WHERE user_id = %s AND channel <> 'in_app' "
        "AND event <> %s ORDER BY id",
        (user, digest.INBOX_EVENT),
    ).fetchall()
    return [(r["channel"], r["kind"]) for r in rows]


def _urgency(db: Any, item: int) -> str | None:
    return db.execute("SELECT urgency FROM notifications WHERE id = %s", (item,)).fetchone()["urgency"]


def _digests(db: Any, user: str | None = None) -> list[dict[str, Any]]:
    return db.execute(
        "SELECT * FROM notifications WHERE event = %s AND (%s::uuid IS NULL OR user_id = %s::uuid) ORDER BY id",
        (digest.INBOX_EVENT, user, user),
    ).fetchall()


def _window(row: dict[str, Any]) -> tuple[dt.datetime, dt.datetime]:
    return (
        dt.datetime.fromisoformat(row["payload"]["since"]),
        dt.datetime.fromisoformat(row["payload"]["until"]),
    )


def _pin(db: Any, user: str, at: dt.datetime) -> None:
    """Date the person's queued emails other than digests at `at`, so no test reads the real clock: an email queued
    at the real now() would not yet be due at a fixed time once that time is in the past (a date bomb)."""
    db.execute(
        "UPDATE notifications SET send_after = %s WHERE user_id = %s AND channel = 'email' AND state = 'queued' "
        "AND event <> %s",
        (at, user, digest.INBOX_EVENT),
    )


def _switch(db: Any, name: str, state: str) -> None:
    db.execute("UPDATE kill_switches SET state = %s WHERE name = %s", (state, name))
    killswitch.clear_cache()


def _mail_to(monkeypatch: Any) -> list[tuple[str, Any]]:
    sent: list[tuple[str, Any]] = []
    monkeypatch.setattr("comms.send._smtp", lambda to, email: sent.append((to, email)))
    return sent


def test_bld_a255_l_notify_2_4_5_the_at_once_cases_still_go_at_once_db(cast: Any) -> None:
    """Decisions, reversals and merges (with email off they fall back to email, L-NOTIFY/4), an answer reminder with
    reminders on, and anything marked Needs you: one email each, queued at once, as before. With reminders off an
    answer reminder goes nowhere outside the app, and it never waits for the digest."""
    db, p, ideas = cast["db"], cast["p"], cast["ideas"]
    kavya, meera, rohan = p["kavya"]["id"], p["meera"]["id"], p["rohan"]["id"]
    items = [
        _post(db, kind, kavya, ideas["mine"], sender=meera, refs=refs) for kind, refs in AT_ONCE_REFS.items()
    ]
    items.append(_post(db, "answer_reminder", kavya, ideas["mine"], needs_you=True, refs={"set_id": "s1"},
                       due_at=WED, dedupe_key="qs:s1:2"))  # fmt: skip
    items.append(
        _post(db, "comment", kavya, ideas["mine"], sender=p["ravi"]["id"], refs=ENTRY, needs_you=True)
    )
    assert _outside(db, kavya) == [
        ("email", "decision"),
        ("email", "decision_reversed"),
        ("email", "desk_merge"),
        ("email", "answer_reminder"),
        ("email", "comment"),
    ]
    queued = db.execute(
        "SELECT urgency, state, send_after = created_at AS due FROM notifications WHERE user_id = %s "
        "AND channel = 'email'",
        (kavya,),
    ).fetchall()
    assert all((r["urgency"], r["state"], r["due"]) == ("immediate", "queued", True) for r in queued)
    assert [_urgency(db, i) for i in items] == ["immediate"] * 5
    db.execute(
        "INSERT INTO comms_prefs (user_id, email, teams, reminders) VALUES (%s, false, false, false)",
        (rohan,),
    )
    reminder = _post(db, "answer_reminder", rohan, ideas["mine"], needs_you=True, refs={"set_id": "s2"},
                     due_at=WED, dedupe_key="qs:s2:2", at=WED - dt.timedelta(hours=1))  # fmt: skip
    merge = _post(db, "desk_merge", rohan, ideas["mine"], refs={"merge_id": str(uuid.uuid4())})
    assert _outside(db, rohan) == [("email", "desk_merge")]  # the fallback; the reminder follows its setting
    assert _urgency(db, reminder) == _urgency(db, merge) == "immediate"
    db.execute("UPDATE notifications SET needs_you = false WHERE id = %s", (reminder,))
    db.execute("UPDATE comms_prefs SET email = true WHERE user_id = %s", (rohan,))
    digest.queue_inbox(db, now=WED)
    assert _digests(db, rohan) == []  # an answer reminder is never a digest item, Needs you or not


def test_bld_a255_l_notify_1_dec138_any_other_kind_gets_teams_at_once_and_no_email_db(cast: Any) -> None:
    """DEC-138 is an email rule. With email and Teams on and Teams switched on, every kind that is not emailed at once
    gets its Teams message at once, as before (the Profile's "Teams messages" line and S-08's "on Teams" note stay
    true), and no email row; its in-app item is marked as waiting for the digest."""
    db, p, ideas = cast["db"], cast["p"], cast["ideas"]
    kavya = p["kavya"]["id"]
    kinds = sorted(notify.INBOX_KINDS - notify.AT_ONCE)
    _switch(db, "comms.teams", "on")
    try:
        for kind in kinds:
            refs = {} if kind in notify.NO_REFS_KINDS else ENTRY
            idea = ideas["draft"] if kind == "draft_kept" else ideas["mine"]
            item = _post(db, kind, kavya, idea, sender=p["ravi"]["id"], refs=refs)
            assert _urgency(db, item) == "routine", kind
        assert _outside(db, kavya) == [("teams", kind) for kind in kinds]
        teams = db.execute(
            "SELECT urgency, state, send_after = created_at AS due FROM notifications WHERE user_id = %s "
            "AND channel = 'teams'",
            (kavya,),
        ).fetchall()
        assert all((r["urgency"], r["state"], r["due"]) == ("immediate", "queued", True) for r in teams)
    finally:
        _switch(db, "comms.teams", "off")
    _post(db, "comment", kavya, ideas["mine"], sender=p["ravi"]["id"], refs=ENTRY)
    assert len(_outside(db, kavya)) == len(kinds)  # switched off (DEC-105): nothing more outside the app


def test_bld_a255_the_1030_run_queues_one_digest_per_person_with_unread_waiting_items_db(cast: Any) -> None:
    """One row each for the people with something unread that waited; none for email off, none for nothing unread,
    none for nothing at all; the row holds the window's two times only (a first digest looks back 7 days and stops
    5 minutes before the run); a second run the same day adds nothing."""
    db, p, ideas = cast["db"], cast["p"], cast["ideas"]
    kavya, meera, rohan, ravi = (p[k]["id"] for k in ("kavya", "meera", "rohan", "ravi"))
    before = WED - dt.timedelta(hours=1)
    _post(db, "comment", kavya, ideas["mine"], before, sender=ravi, refs=ENTRY)
    _post(db, "stage_moved", kavya, ideas["mine"], before, refs={"to": "being_built"})
    _post(db, "crew_joined", meera, ideas["mine"], before, sender=ravi)
    db.execute("INSERT INTO comms_prefs (user_id, email) VALUES (%s, false)", (rohan,))
    _post(db, "mention", rohan, ideas["mine"], before, sender=ravi)  # email off: no digest
    read = _post(db, "mention", ravi, ideas["ravis"], before, sender=meera)  # read before 10:30: no digest
    inbox.mark_read(db, ravi, read)
    assert digest.queue_inbox(db, now=WED) == 2
    rows = _digests(db)
    assert {str(r["user_id"]) for r in rows} == {kavya, meera}
    for r in rows:
        assert (r["channel"], r["template"], r["urgency"], r["state"], r["kind"]) == (
            "email",
            "inbox/digest",
            "immediate",
            "queued",
            None,
        )
        assert (r["send_after"], r["dedupe_key"]) == (WED, "inbox_digest:2026-12-02")
        assert set(r["payload"]) == {"since", "until"}
        assert _window(r) == (WED - LOOKBACK, WED - GRACE)
        assert r["from_user_id"] is None and r["idea_uuid"] is None
    assert digest.queue_inbox(db, now=WED + dt.timedelta(hours=2)) == 0  # once a day
    assert len(_digests(db)) == 2


def test_bld_a255_a_weekend_and_a_holiday_roll_into_the_next_working_day_db(
    cast: Any, monkeypatch: Any
) -> None:
    db, p, ideas = cast["db"], cast["p"], cast["ideas"]
    kavya, ravi = p["kavya"]["id"], p["ravi"]["id"]
    sent = _mail_to(monkeypatch)
    friday = _post(
        db, "stage_moved", kavya, ideas["mine"], FRI - dt.timedelta(hours=2), refs={"to": "picked"}
    )
    assert digest.queue_inbox(db, now=FRI) == 1
    first = _digests(db, kavya)[0]
    friday_mail = digest.compose_inbox(db, kavya, first["payload"], FRI)
    assert friday_mail is not None and "moved to Picked" in friday_mail.text
    assert send_due(db, now=FRI + dt.timedelta(minutes=1)) == 1  # Friday's digest goes on Friday
    _post(db, "comment", kavya, ideas["mine"], SAT + dt.timedelta(hours=2), sender=ravi, refs=ENTRY)
    assert digest.queue_inbox(db, now=SAT + dt.timedelta(hours=3)) == 0  # Saturday
    assert digest.queue_inbox(db, now=SUN) == 0  # Sunday
    assert digest.queue_inbox(db, now=MON) == 1
    first, monday = _digests(db, kavya)
    assert _window(monday) == (FRI - GRACE, MON - GRACE)  # from the last digest's end
    mail = digest.compose_inbox(db, kavya, monday["payload"], MON)
    assert mail is not None and mail.subject == "Your 1% Club update: 1 new"
    assert "Ravi Nair commented on your idea" in mail.text and "moved to Picked" not in mail.text
    assert send_due(db, now=MON + dt.timedelta(minutes=1)) == 1 and len(sent) == 2
    inbox.mark_read(db, kavya, friday)
    # Christmas Day is a holiday in the seed's calendar: Thursday's item goes on the Monday after. Four weeks after
    # Monday's digest, the window starts 7 days back (LOOKBACK), not at Monday's end.
    _post(db, "crew_joined", kavya, ideas["mine"], XMAS - dt.timedelta(hours=20), sender=ravi)
    assert digest.queue_inbox(db, now=XMAS) == 0
    assert digest.queue_inbox(db, now=MON_AFTER) == 1
    last = _digests(db, kavya)[-1]
    assert _window(last) == (MON_AFTER - LOOKBACK, MON_AFTER - GRACE)
    mail = digest.compose_inbox(db, kavya, last["payload"], MON_AFTER)
    assert mail is not None and mail.subject == "Your 1% Club update: 1 new"
    assert "Ravi Nair joined your crew" in mail.text


def test_bld_a255_a_window_ends_5_minutes_before_the_run_so_a_late_commit_goes_next_time_db(
    cast: Any, monkeypatch: Any
) -> None:
    """An item whose transaction began just before the 10:30 run but committed after it carries a time before the
    run: it falls into the next window, never into none."""
    db, p, ideas = cast["db"], cast["p"], cast["ideas"]
    kavya, ravi = p["kavya"]["id"], p["ravi"]["id"]
    sent = _mail_to(monkeypatch)
    _post(db, "comment", kavya, ideas["mine"], WED - dt.timedelta(hours=1), sender=ravi, refs=ENTRY)
    _post(db, "crew_joined", kavya, ideas["mine"], WED - dt.timedelta(minutes=2), sender=ravi)
    assert digest.queue_inbox(db, now=WED) == 1
    assert send_due(db, now=WED + dt.timedelta(minutes=1)) == 1
    wednesday = sent[-1][1]
    assert wednesday.subject == "Your 1% Club update: 1 new" and "joined your crew" not in wednesday.text
    assert digest.queue_inbox(db, now=THU) == 1
    assert _window(_digests(db, kavya)[-1]) == (WED - GRACE, THU - GRACE)
    assert send_due(db, now=THU + dt.timedelta(minutes=1)) == 1
    thursday = sent[-1][1]
    assert thursday.subject == "Your 1% Club update: 1 new" and "Ravi Nair joined your crew" in thursday.text


def test_bld_a255_a_window_never_starts_more_than_7_days_back_db(cast: Any, monkeypatch: Any) -> None:
    db, p, ideas = cast["db"], cast["p"], cast["ideas"]
    kavya, ravi = p["kavya"]["id"], p["ravi"]["id"]
    sent = _mail_to(monkeypatch)
    launch = dt.datetime(2026, 11, 20, 10, 30, tzinfo=IST)  # a Friday, twelve days before WED
    _post(db, "stage_moved", kavya, ideas["mine"], launch - dt.timedelta(hours=2), refs={"to": "picked"})
    assert digest.queue_inbox(db, now=launch) == 1
    assert send_due(db, now=launch + dt.timedelta(minutes=1)) == 1
    _post(
        db, "mention", kavya, ideas["mine"], WED - dt.timedelta(days=7, hours=22), sender=ravi
    )  # 8 days back
    _post(db, "comment", kavya, ideas["mine"], WED - dt.timedelta(days=6), sender=ravi, refs=ENTRY)
    assert digest.queue_inbox(db, now=WED) == 1
    assert _window(_digests(db, kavya)[-1]) == (WED - LOOKBACK, WED - GRACE)
    assert send_due(db, now=WED + dt.timedelta(minutes=1)) == 1
    mail = sent[-1][1]
    assert mail.subject == "Your 1% Club update: 1 new"
    assert "Ravi Nair commented on your idea" in mail.text and "mentioned you" not in mail.text


def test_bld_a255_a_backlog_is_one_digest_sent_in_working_hours_and_after_the_at_once_email_db(
    cast: Any, monkeypatch: Any
) -> None:
    """`comms.email` off on Wednesday and back on on Thursday at 22:30. Wednesday's digest is still queued at
    Thursday's run, so its window is carried on to Thursday (one row, today's key). At 22:30 the decision queued
    while email was off goes at once (lane G's G007 and G010 flow); the digest waits for Friday 08:00 and then goes as
    one email with both days' items."""
    db, p, ideas = cast["db"], cast["p"], cast["ideas"]
    kavya, meera, ravi = p["kavya"]["id"], p["meera"]["id"], p["ravi"]["id"]
    sent = _mail_to(monkeypatch)
    _switch(db, "comms.email", "off")
    try:
        _post(db, "comment", kavya, ideas["mine"], WED - dt.timedelta(hours=1), sender=ravi, refs=ENTRY)
        assert digest.queue_inbox(db, now=WED) == 1
        _post(db, "decision", kavya, ideas["mine"], sender=meera, refs=AT_ONCE_REFS["decision"])
        _pin(db, kavya, WED)  # queued on Wednesday while email was off, whatever today's date is
        assert send_due(db, now=WED + dt.timedelta(minutes=1)) == 0
        _post(db, "crew_joined", kavya, ideas["mine"], THU - dt.timedelta(hours=1), sender=ravi)
        assert digest.queue_inbox(db, now=THU) == 1  # carried on, not a second row
        (row,) = _digests(db, kavya)
        assert (row["state"], row["dedupe_key"]) == ("queued", "inbox_digest:2026-12-03")
        assert _window(row) == (THU - LOOKBACK, THU - GRACE)
        assert send_due(db, now=THU + dt.timedelta(minutes=1)) == 0 and sent == []
    finally:
        _switch(db, "comms.email", "on")
    assert send_due(db, now=THU_NIGHT) == 1  # the decision, queued while email was off, goes now
    (to, decision), *_ = sent
    assert to == p["kavya"]["email"] and len(sent) == 1
    assert decision.subject == "A decision on your idea" and not decision.subject.startswith(DIGEST_SUBJECT)
    (row,) = _digests(db, kavya)
    assert (
        row["state"] == "queued" and row["send_after"] == FRI_OPEN
    )  # out of hours: waits for the next opening
    assert send_due(db, now=FRI_OPEN + dt.timedelta(minutes=1)) == 1
    assert len(sent) == 2
    backlog = sent[-1][1]
    assert backlog.subject == "Your 1% Club update: 2 new"
    assert "Ravi Nair commented on your idea" in backlog.text and "Ravi Nair joined your crew" in backlog.text
    assert _digests(db, kavya)[0]["state"] == "sent"


@pytest.mark.parametrize(
    "kind", ["decision", "decision_reversed", "desk_merge", "answer_reminder", "needs_you"]
)
def test_bld_a255_an_at_once_email_queued_after_many_digests_goes_first_db(
    cast: Any, monkeypatch: Any, kind: str
) -> None:
    """send_due takes every other email before the Inbox digests (an ORDER BY change only), so a backlog of digests,
    older by send_after, never holds back a decision, a reminder or a Needs you email."""
    db, p, ideas = cast["db"], cast["p"], cast["ideas"]
    kavya, meera, rohan, ravi = (p[k]["id"] for k in ("kavya", "meera", "rohan", "ravi"))
    for person in (kavya, meera, rohan):
        _post(db, "comment", person, ideas["ravis"], WED - dt.timedelta(hours=1), sender=ravi, refs=ENTRY)
    assert digest.queue_inbox(db, now=WED) == 3
    db.execute(
        "UPDATE notifications SET send_after = %s WHERE event = %s",
        (WED - dt.timedelta(hours=2), digest.INBOX_EVENT),
    )  # three digests, older by send_after than the email below
    if kind == "needs_you":
        _post(db, "comment", kavya, ideas["mine"], sender=ravi, refs=ENTRY, needs_you=True)
    elif kind == "decision_reversed":
        _post(db, kind, kavya, ideas["mine"], sender=rohan, refs=AT_ONCE_REFS[kind])
    else:
        _post(db, kind, kavya, ideas["mine"], sender=meera, refs=desk_refs(db, kind, p, ideas),
              needs_you=kind == "answer_reminder",
              due_at=WED if kind == "answer_reminder" else None)  # fmt: skip
    _pin(db, kavya, WED - dt.timedelta(hours=1))
    sent = _mail_to(monkeypatch)
    assert send_due(db, now=WED + dt.timedelta(minutes=1), limit=1) == 1
    (to, mail), *_ = sent
    assert to == p["kavya"]["email"] and not mail.subject.startswith(DIGEST_SUBJECT), mail.subject
    assert {r["state"] for r in _digests(db)} == {"queued"}


def test_bld_a255_l_notify_6_read_after_queueing_is_left_out_and_all_read_sends_nothing_db(
    cast: Any, monkeypatch: Any
) -> None:
    db, p, ideas = cast["db"], cast["p"], cast["ideas"]
    kavya, meera, ravi = p["kavya"]["id"], p["meera"]["id"], p["ravi"]["id"]
    before = WED - dt.timedelta(hours=1)
    _post(db, "comment", kavya, ideas["mine"], before, sender=ravi, refs=ENTRY)
    moved = _post(db, "stage_moved", kavya, ideas["mine"], before, refs={"to": "being_built"})
    mention = _post(db, "mention", meera, ideas["mine"], before, sender=ravi)
    assert digest.queue_inbox(db, now=WED) == 2
    inbox.mark_read(db, kavya, moved)
    inbox.mark_read(db, meera, mention)
    sent = _mail_to(monkeypatch)
    assert send_due(db, now=WED + dt.timedelta(minutes=1)) == 1
    (to, mail), *_ = sent
    assert to == p["kavya"]["email"] and len(sent) == 1
    assert mail.subject == "Your 1% Club update: 1 new"
    assert "Ravi Nair commented on your idea" in mail.text and "moved your idea" not in mail.text
    assert TITLE in mail.text
    states = {str(r["user_id"]): (r["state"], r["error_code"]) for r in _digests(db)}
    assert states == {kavya: ("sent", None), meera: ("failed", "nothing_to_send")}


def test_bld_a255_comms_email_off_leaves_the_digest_queued_db(cast: Any, monkeypatch: Any) -> None:
    db, p, ideas = cast["db"], cast["p"], cast["ideas"]
    kavya = p["kavya"]["id"]
    _post(
        db, "comment", kavya, ideas["mine"], WED - dt.timedelta(hours=1), sender=p["ravi"]["id"], refs=ENTRY
    )
    assert digest.queue_inbox(db, now=WED) == 1
    sent = _mail_to(monkeypatch)
    _switch(db, "comms.email", "off")
    try:
        assert send_due(db, now=WED + dt.timedelta(minutes=1)) == 0 and sent == []
        assert _digests(db, kavya)[0]["state"] == "queued"
    finally:
        _switch(db, "comms.email", "on")
    assert send_due(db, now=WED + dt.timedelta(minutes=2)) == 1 and len(sent) == 1
    assert _digests(db, kavya)[0]["state"] == "sent"


def test_bld_a255_needs_you_on_a_waiting_item_emails_it_at_once_once_and_teams_stays_one_db(
    cast: Any,
) -> None:
    db, p, ideas = cast["db"], cast["p"], cast["ideas"]
    kavya, ravi = p["kavya"]["id"], p["ravi"]["id"]
    key = f"t:edge:{uuid.uuid4().hex}"
    _switch(db, "comms.teams", "on")
    try:
        item = _post(db, "comment", kavya, ideas["mine"], sender=ravi, refs=ENTRY, dedupe_key=key)
        assert _outside(db, kavya) == [("teams", "comment")] and _urgency(db, item) == "routine"
        again = notify.post(db, "comment", [kavya], idea_id=ideas["mine"], sender=ravi, refs=ENTRY,
                            needs_you=True, dedupe_key=key)  # fmt: skip
        assert again.updated == [item] and again.ids == []
        assert _outside(db, kavya) == [("teams", "comment"), ("email", "comment")]  # Teams not doubled
        assert _urgency(db, item) == "immediate"
        mail_row = db.execute(
            "SELECT urgency, state, dedupe_key FROM notifications WHERE user_id = %s AND channel = 'email'",
            (kavya,),
        ).fetchone()
        assert (mail_row["urgency"], mail_row["state"], mail_row["dedupe_key"]) == (
            "immediate",
            "queued",
            key,
        )
        notify.post(db, "comment", [kavya], idea_id=ideas["mine"], sender=ravi, refs=ENTRY, needs_you=True,
                    dedupe_key=key)  # fmt: skip
        assert _outside(db, kavya) == [("teams", "comment"), ("email", "comment")]  # once
    finally:
        _switch(db, "comms.teams", "off")
    db.execute("UPDATE notifications SET created_at = %s WHERE id = %s", (WED - dt.timedelta(hours=1), item))
    assert notify.resolve(db, key) == 1  # off Needs you again, and resolved: it went at once, never twice
    assert digest.queue_inbox(db, now=WED) == 0


def test_bld_a255_items_from_before_the_rule_and_the_club_seed_never_go_twice_db(
    cast: Any, monkeypatch: Any
) -> None:
    """r6 emailed every item at once (stored `immediate` with an email row); the club seed writes items with no
    urgency and no outside row. Neither is ever in a digest; an item posted under the rule is."""
    db, p, ideas = cast["db"], cast["p"], cast["ideas"]
    kavya, ravi = p["kavya"]["id"], p["ravi"]["id"]
    before = WED - dt.timedelta(hours=1)
    with monkeypatch.context() as r6:
        r6.setattr(notify, "goes_at_once", lambda kind, needs_you: True)  # as r6 posted every kind
        _post(db, "stage_moved", kavya, ideas["mine"], before, refs={"to": "shipped"})
    assert _outside(db, kavya) == [("email", "stage_moved")]
    db.execute(
        "INSERT INTO notifications (user_id, channel, template, event, payload, state, created_at, sent_at, kind, "
        "from_user_id, idea_uuid) VALUES (%s, 'in_app', 'inbox/mention', 'inbox.mention', '{}', 'sent', %s, %s, "
        "'mention', %s, %s)",
        (kavya, before, before, ravi, ideas["mine"]),
    )  # as the club seed writes one
    _post(db, "comment", kavya, ideas["mine"], before, sender=ravi, refs=ENTRY)
    assert digest.queue_inbox(db, now=WED) == 1
    mail = digest.compose_inbox(db, kavya, _digests(db, kavya)[0]["payload"], WED)
    assert mail is not None and mail.subject == "Your 1% Club update: 1 new"
    assert "Ravi Nair commented on your idea" in mail.text
    assert "Shipped" not in mail.text and "mentioned you" not in mail.text


def test_bld_a255_l_notify_3_dec111_dec113_the_digest_says_what_the_inbox_says_and_nothing_more_db(
    cast: Any,
) -> None:
    """The sharer's digest names the review desk and the Ones Committee as one and a crew member by name, as her
    Inbox does; no reviewer or committee member in any form, no reason, no one's words; the idea's title and links
    into the app; oldest first; the greeting and the sign-off once."""
    db, p, ideas = cast["db"], cast["p"], cast["ideas"]
    kavya, meera, rohan, ravi = (p[k]["id"] for k in ("kavya", "meera", "rohan", "ravi"))
    db.execute("INSERT INTO role_grants (user_id, role) VALUES (%s, 'core_committee')", (rohan,))
    try:
        at = [WED - dt.timedelta(hours=h) for h in (5, 4, 3, 2, 1)]
        _post(db, "comment", kavya, ideas["mine"], at[0], sender=meera, refs={**ENTRY, "as_desk": True})
        _post(db, "comment", kavya, ideas["mine"], at[1], sender=rohan, refs={**ENTRY, "as_committee": True})
        _post(db, "comment", kavya, ideas["mine"], at[2], sender=ravi, refs=ENTRY)
        _post(db, "teamup_answer", kavya, ideas["ravis"], at[3], sender=ravi,  # Ravi leads his idea
              refs={"request_id": str(uuid.uuid4()), "request": "teamup", "answer": "decline", "has_reason": True})  # fmt: skip
        _post(
            db,
            "worth_revised",
            kavya,
            ideas["mine"],
            at[4],
            sender=meera,
            refs={"worth_id": str(uuid.uuid4())},
        )
        assert digest.queue_inbox(db, now=WED) == 1
        mail = digest.compose_inbox(db, kavya, _digests(db, kavya)[0]["payload"], WED)
        assert mail is not None and mail.subject == "Your 1% Club update: 5 new"
        headings = [
            "The review desk commented on your idea",
            "The Ones Committee commented on your idea",
            "Ravi Nair commented on your idea",
            "Ravi Nair answered your team-up request",
            "The review desk revised what your idea is worth",
        ]
        where = [mail.text.index(h + "\n") for h in headings]
        assert where == sorted(where)  # oldest first
        senders = {it["body"]["sender"] for it in inbox.items(db, kavya, now=WED)["items"]}
        assert senders == {"The review desk", "The Ones Committee", "Ravi Nair"}  # the Inbox names the same
        assert "Ravi Nair declined your team-up request, with a reason" in mail.text
        seen = mail.subject + mail.text + mail.html
        for trace in ("Meera", "Iyer", meera, "Rohan", "Mehta", rohan, REASON):
            assert trace not in seen, trace
        assert TITLE in mail.text and "/ideas/IDEA-2026-000900" in mail.text
        for part in (mail.text, mail.html):
            assert part.count("Hi Kavya,") == 1 and part.count("The 1% Club team") == 1
        assert mail.text.index("Hi Kavya,") < where[0] and mail.text.rindex("The 1% Club team") > where[-1]
    finally:
        db.execute("DELETE FROM role_grants WHERE user_id = %s", (rohan,))


def test_bld_a255_a_database_error_in_one_item_rolls_back_that_item_and_the_digest_is_still_sent_db(
    cast: Any, monkeypatch: Any
) -> None:
    """Each item is rendered under its own savepoint inside send_due's claim: a SQL error in one item's render leaves
    that item out, the claim transaction stays usable, the others go, and the row is marked sent (nothing escapes to
    the ticker, which would stop the worker and pick the same row again)."""
    db, p, ideas = cast["db"], cast["p"], cast["ideas"]
    kavya, ravi = p["kavya"]["id"], p["ravi"]["id"]
    before = WED - dt.timedelta(hours=1)
    _post(db, "comment", kavya, ideas["mine"], before, sender=ravi, refs=ENTRY)
    bad = _post(db, "mention", kavya, ideas["mine"], before + dt.timedelta(minutes=1), sender=ravi)
    _post(db, "crew_joined", kavya, ideas["mine"], before + dt.timedelta(minutes=2), sender=ravi)
    assert digest.queue_inbox(db, now=WED) == 1
    real = digest.inbox_render.variables

    def broken(conn: Any, row: dict[str, Any], viewer: str, now: dt.datetime, **kw: Any) -> Any:
        if row["id"] == bad:
            conn.execute("SELECT 1 / 0")  # a database error inside this item's render
        return real(conn, row, viewer, now, **kw)

    monkeypatch.setattr(digest.inbox_render, "variables", broken)
    sent = _mail_to(monkeypatch)
    assert send_due(db, now=WED + dt.timedelta(minutes=1)) == 1
    (to, mail), *_ = sent
    assert to == p["kavya"]["email"] and mail.subject == "Your 1% Club update: 2 new"
    assert "Ravi Nair commented on your idea" in mail.text and "Ravi Nair joined your crew" in mail.text
    assert "mentioned you" not in mail.text
    assert _digests(db, kavya)[0]["state"] == "sent"


def test_bld_a255_a_digest_that_failed_for_good_does_not_end_the_next_window_db(
    cast: Any, monkeypatch: Any
) -> None:
    """The previous window ends at the last digest that did not fail. Wednesday's digest fails for good; Thursday's
    starts where Monday's sent one ended, so it carries Wednesday's still-unread item with Thursday's."""
    db, p, ideas = cast["db"], cast["p"], cast["ideas"]
    kavya, ravi = p["kavya"]["id"], p["ravi"]["id"]
    monday = dt.datetime(2026, 11, 30, 10, 30, tzinfo=IST)
    sent = _mail_to(monkeypatch)
    _post(db, "stage_moved", kavya, ideas["mine"], monday - dt.timedelta(hours=1), refs={"to": "picked"})
    assert digest.queue_inbox(db, now=monday) == 1
    assert send_due(db, now=monday + dt.timedelta(minutes=1)) == 1  # Monday's digest is sent
    _post(db, "comment", kavya, ideas["mine"], WED - dt.timedelta(hours=1), sender=ravi, refs=ENTRY)
    assert digest.queue_inbox(db, now=WED) == 1
    wednesday = _digests(db, kavya)[-1]
    db.execute(  # as `_failed` leaves it after its last try
        "UPDATE notifications SET state = 'failed', attempts = 3, error_code = 'oserror' WHERE id = %s",
        (wednesday["id"],),
    )
    _post(db, "crew_joined", kavya, ideas["mine"], THU - dt.timedelta(hours=1), sender=ravi)
    assert digest.queue_inbox(db, now=THU) == 1
    thursday = _digests(db, kavya)[-1]
    assert thursday["id"] != wednesday["id"]
    assert _window(thursday) == (monday - GRACE, THU - GRACE)
    assert send_due(db, now=THU + dt.timedelta(minutes=1)) == 1
    mail = sent[-1][1]
    assert mail.subject == "Your 1% Club update: 2 new"
    assert "Ravi Nair commented on your idea" in mail.text and "Ravi Nair joined your crew" in mail.text
    assert "moved to Picked" not in mail.text  # Monday's, sent on Monday
