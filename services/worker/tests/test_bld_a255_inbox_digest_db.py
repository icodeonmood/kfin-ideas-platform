"""BLD-A255 against the real tables (stack tests, CI only; BLD-A251): DEC-133's after-launch rule with DEC-138's
defaults (L-NOTIFY/1, /2, /3, /4, /5).

A decision, a reversal, a merge notice, an answer reminder and anything posted as Needs you are queued at once, as
before. Every other Inbox item queues no email and no Teams message: the 10:30 run of `comms.digest` gives each
active person with email on one digest row on a working day, covering the items that waited since their last digest
(a weekend's or a holiday's roll over), and the email is built when it is sent from the items still unread. Items
posted before the rule (r6 emailed every one at once) and the club seed's are never in it. Synthetic people only
(L-NOTIFY's `cast`, shared with tests/test_notify.py)."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any
from zoneinfo import ZoneInfo

import notify
from comms.send import send_due
from core import killswitch
from notify import digest, inbox
from tests import test_notify as l_notify

cast = l_notify.cast
IST = ZoneInfo("Asia/Kolkata")
TITLE, REASON = l_notify.TITLE, l_notify.REASON
WED = dt.datetime(2026, 12, 2, 10, 30, tzinfo=IST)  # a working Wednesday at the digest's time
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


def _switch(db: Any, name: str, state: str) -> None:
    db.execute("UPDATE kill_switches SET state = %s WHERE name = %s", (state, name))
    killswitch.clear_cache()


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
        "SELECT urgency, state, send_after <= now() AS due FROM notifications WHERE user_id = %s "
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


def test_bld_a255_l_notify_1_dec138_any_other_kind_queues_no_outside_row_db(cast: Any) -> None:
    """With email and Teams on and Teams switched on, every kind that does not go at once gets its in-app item only,
    marked as waiting for the digest."""
    db, p, ideas = cast["db"], cast["p"], cast["ideas"]
    kavya = p["kavya"]["id"]
    _switch(db, "comms.teams", "on")
    try:
        for kind in sorted(notify.INBOX_KINDS - notify.AT_ONCE):
            refs = {} if kind in notify.NO_REFS_KINDS else ENTRY
            idea = ideas["draft"] if kind == "draft_kept" else ideas["mine"]
            item = _post(db, kind, kavya, idea, sender=p["ravi"]["id"], refs=refs)
            assert _urgency(db, item) == "routine", kind
        assert _outside(db, kavya) == []
    finally:
        _switch(db, "comms.teams", "off")


def test_bld_a255_the_1030_run_queues_one_digest_per_person_with_unread_waiting_items_db(cast: Any) -> None:
    """One row each for the people with something unread that waited; none for email off, none for nothing unread,
    none for nothing at all; the row holds the window's two times only; a second run the same day adds nothing."""
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
        assert set(r["payload"]) == {"since", "until"} and r["payload"]["since"] is None  # the first digest
        assert dt.datetime.fromisoformat(r["payload"]["until"]) == WED
        assert r["from_user_id"] is None and r["idea_uuid"] is None
    assert digest.queue_inbox(db, now=WED + dt.timedelta(hours=2)) == 0  # once a day
    assert len(_digests(db)) == 2


def test_bld_a255_a_weekend_and_a_holiday_roll_into_the_next_working_day_db(cast: Any) -> None:
    db, p, ideas = cast["db"], cast["p"], cast["ideas"]
    kavya, ravi = p["kavya"]["id"], p["ravi"]["id"]
    friday = _post(
        db, "stage_moved", kavya, ideas["mine"], FRI - dt.timedelta(hours=2), refs={"to": "picked"}
    )
    assert digest.queue_inbox(db, now=FRI) == 1
    _post(db, "comment", kavya, ideas["mine"], SAT + dt.timedelta(hours=2), sender=ravi, refs=ENTRY)
    assert digest.queue_inbox(db, now=SAT + dt.timedelta(hours=3)) == 0  # Saturday
    assert digest.queue_inbox(db, now=SUN) == 0  # Sunday
    assert digest.queue_inbox(db, now=MON) == 1
    first, monday = _digests(db, kavya)
    assert dt.datetime.fromisoformat(monday["payload"]["since"]) == FRI  # from the last digest's end
    assert dt.datetime.fromisoformat(monday["payload"]["until"]) == MON
    mail = digest.compose_inbox(db, kavya, monday["payload"], MON)
    assert mail is not None and mail.subject == "Your 1% Club update: 1 new"
    assert "Ravi Nair commented on your idea" in mail.text and "moved to Picked" not in mail.text
    friday_mail = digest.compose_inbox(db, kavya, first["payload"], MON)  # Friday's item is still Friday's
    assert friday_mail is not None and "moved to Picked" in friday_mail.text
    assert "Ravi Nair" not in friday_mail.text
    inbox.mark_read(db, kavya, friday)
    # Christmas Day is a holiday in the seed's calendar: Thursday's item goes on the Monday after
    _post(db, "crew_joined", kavya, ideas["mine"], XMAS - dt.timedelta(hours=20), sender=ravi)
    assert digest.queue_inbox(db, now=XMAS) == 0
    assert digest.queue_inbox(db, now=MON_AFTER) == 1
    last = _digests(db, kavya)[-1]
    assert dt.datetime.fromisoformat(last["payload"]["since"]) == MON
    mail = digest.compose_inbox(db, kavya, last["payload"], MON_AFTER)
    assert mail is not None and mail.subject == "Your 1% Club update: 1 new"
    assert "Ravi Nair joined your crew" in mail.text


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
    sent: list[Any] = []
    monkeypatch.setattr("comms.send._smtp", lambda to, email: sent.append((to, email)))
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
    sent: list[Any] = []
    monkeypatch.setattr("comms.send._smtp", lambda to, email: sent.append((to, email)))
    _switch(db, "comms.email", "off")
    try:
        assert send_due(db, now=WED + dt.timedelta(minutes=1)) == 0 and sent == []
        assert _digests(db, kavya)[0]["state"] == "queued"
    finally:
        _switch(db, "comms.email", "on")
    assert send_due(db, now=WED + dt.timedelta(minutes=2)) == 1 and len(sent) == 1
    assert _digests(db, kavya)[0]["state"] == "sent"


def test_bld_a255_needs_you_on_a_waiting_item_sends_it_at_once_once_db(cast: Any) -> None:
    db, p, ideas = cast["db"], cast["p"], cast["ideas"]
    kavya, ravi = p["kavya"]["id"], p["ravi"]["id"]
    key = f"t:edge:{uuid.uuid4().hex}"
    item = _post(db, "comment", kavya, ideas["mine"], sender=ravi, refs=ENTRY, dedupe_key=key)
    assert _outside(db, kavya) == [] and _urgency(db, item) == "routine"
    again = notify.post(db, "comment", [kavya], idea_id=ideas["mine"], sender=ravi, refs=ENTRY,
                        needs_you=True, dedupe_key=key)  # fmt: skip
    assert again.updated == [item] and again.ids == []
    assert _outside(db, kavya) == [("email", "comment")]
    assert _urgency(db, item) == "immediate"
    mail_row = db.execute(
        "SELECT urgency, state, dedupe_key FROM notifications WHERE user_id = %s AND channel = 'email'",
        (kavya,),
    ).fetchone()
    assert (mail_row["urgency"], mail_row["state"], mail_row["dedupe_key"]) == ("immediate", "queued", key)
    notify.post(db, "comment", [kavya], idea_id=ideas["mine"], sender=ravi, refs=ENTRY, needs_you=True,
                dedupe_key=key)  # fmt: skip
    assert _outside(db, kavya) == [("email", "comment")]  # once
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
    into the app; oldest first."""
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
    finally:
        db.execute("DELETE FROM role_grants WHERE user_id = %s", (rohan,))
