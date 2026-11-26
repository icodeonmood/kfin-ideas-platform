"""BLD-A255 without a database: DEC-133's after-launch rule with DEC-138's defaults (L-NOTIFY/1, /3, /4, /5).

`notify.post` sends outside the app at once only a decision, a reversal, a merge notice, an answer reminder or
anything posted as Needs you; every other Inbox item queues no email and no Teams message and is stored `routine`,
the mark the day's Inbox digest reads. A repeat post that marks Needs you on an item that waited sends it at once, that
one time. The digest is routed by `comms.send.compose` to `notify.digest.compose_inbox`, which builds one email from
the items still unread, each section as that item's own email reads, so the sender is named exactly as the Inbox
names them to that reader (DEC-111, DEC-113). Synthetic people only; the same flows against the real tables run in CI
in tests/test_bld_a255_inbox_digest_db.py."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import pytest

import notify
from notify import digest
from tests import test_inbox_desk_name as desk

# The desk test's synthetic people, idea and template loader (the fixture is autouse there; it is bound here too)
_seed_templates = desk._seed_templates
NOW, IDEA = desk.NOW, desk.IDEA
SHARER, CREW = desk.SHARER, desk.OTHER  # Kavya Menon, who shared the idea; Ravi Nair, on her crew (synthetic)
REVIEWER, MEMBER = desk.REVIEWER, desk.MEMBER  # Meera Iyer, at the review desk; Rohan Mehta, on the committee
ENTRY = {"entry_id": "4c2e8a6d-0f1b-4d39-b7e5-9a3c1d5f7b28"}
AT_ONCE_KINDS = {"decision", "decision_reversed", "desk_merge", "answer_reminder"}
DIGEST_KINDS = sorted(notify.INBOX_KINDS - AT_ONCE_KINDS)


class _Writes:
    """`notify.post`'s reads and writes without a database: everyone's preferences (email and Teams on, reminders as
    given), no desk or committee grants, then each INSERT and UPDATE, kept so a test can see what would be stored.
    With `repeat`, the in-app INSERT meets an open item with the same key, stored with urgency `stored`."""

    def __init__(self, *, reminders: bool = True, repeat: bool = False, stored: str | None = None) -> None:
        self.reminders, self.repeat, self.stored = reminders, repeat, stored
        self.inserts: list[tuple[str, tuple[Any, ...]]] = []
        self.updates: list[tuple[str, tuple[Any, ...]]] = []

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> desk._Rows:
        if "FROM users u LEFT JOIN comms_prefs" in sql:
            return desk._Rows(
                [{"id": u, "email": True, "teams": True, "reminders": self.reminders} for u in params[0]]
            )
        if "FROM role_grants" in sql:
            return desk._Rows([])
        if sql.startswith("UPDATE notifications"):
            self.updates.append((sql, params))
            return desk._Rows([])
        if sql.startswith("INSERT INTO notifications"):
            self.inserts.append((sql, params))
            if self.repeat and "'in_app'" in sql:
                return desk._Rows([{"id": 7, "inserted": False, "urgency": self.stored}])
            return desk._Rows([{"id": len(self.inserts), "inserted": True, "urgency": None}])
        return desk._Rows([])

    def in_app_urgency(self) -> str:
        """The urgency the in-app row was written with (the last value of the in-app INSERT)."""
        (sql, params), *_ = self.inserts
        assert "'in_app'" in sql and sql.split("VALUES", 1)[0].rstrip().endswith("urgency)")
        return str(params[-1])

    def outside(self) -> list[str]:
        """The channel of every outside row written: (user_id, channel, …)."""
        return [p[1] for sql, p in self.inserts if "'in_app'" not in sql]


@pytest.fixture
def teams_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """`comms.teams` on (DEC-105 ships it off), so a test can show a waiting item gets no Teams message either."""
    monkeypatch.setattr(notify.killswitch, "is_on", lambda *_: True)


def test_bld_a255_l_notify_4_5_dec138_the_at_once_kinds() -> None:
    assert notify.AT_ONCE == frozenset(AT_ONCE_KINDS) == notify.ALWAYS_OUTSIDE | notify.REMINDER_KINDS
    for kind in sorted(notify.INBOX_KINDS):
        assert notify.goes_at_once(kind, needs_you=True), kind  # anything marked Needs you
        assert notify.goes_at_once(kind, needs_you=False) is (kind in AT_ONCE_KINDS), kind


@pytest.mark.parametrize("kind", sorted(AT_ONCE_KINDS))
def test_bld_a255_l_notify_1_4_5_an_at_once_kind_is_queued_on_every_channel_at_once(
    kind: str, teams_on: None
) -> None:
    conn = _Writes()
    posted = notify.post(conn, kind, [SHARER], idea_id=IDEA)  # type: ignore[arg-type]
    assert posted.ids == [1]
    assert conn.in_app_urgency() == "immediate"
    assert conn.outside() == ["email", "teams"]
    assert all("'immediate', 'queued', now()" in sql for sql, _ in conn.inserts[1:])


def test_bld_a255_l_notify_2_5_an_answer_reminder_with_reminders_off_goes_nowhere_and_never_waits(
    teams_on: None,
) -> None:
    conn = _Writes(reminders=False)
    notify.post(conn, "answer_reminder", [SHARER], idea_id=IDEA, needs_you=True)  # type: ignore[arg-type]
    assert conn.outside() == [] and conn.in_app_urgency() == "immediate"  # not a digest item either


@pytest.mark.parametrize("kind", DIGEST_KINDS)
def test_bld_a255_l_notify_1_dec138_any_other_kind_queues_no_outside_row_and_waits(
    kind: str, teams_on: None
) -> None:
    conn = _Writes()
    refs = {} if kind in notify.NO_REFS_KINDS else ENTRY
    posted = notify.post(conn, kind, [SHARER], idea_id=IDEA, sender=CREW, refs=refs)  # type: ignore[arg-type]
    assert posted.ids == [1]
    assert conn.outside() == []  # no email and no Teams, with both on and Teams switched on
    assert conn.in_app_urgency() == "routine"  # the mark the digest reads


@pytest.mark.parametrize("kind", DIGEST_KINDS)
def test_bld_a255_l_notify_1_dec138_marked_needs_you_any_kind_goes_at_once(kind: str, teams_on: None) -> None:
    conn = _Writes()
    refs = {} if kind in notify.NO_REFS_KINDS else ENTRY
    notify.post(conn, kind, [SHARER], idea_id=IDEA, sender=CREW, refs=refs, needs_you=True)  # type: ignore[arg-type]
    assert conn.outside() == ["email", "teams"] and conn.in_app_urgency() == "immediate"


def test_bld_a255_a_repeat_that_marks_needs_you_on_a_waiting_item_sends_it_at_once(teams_on: None) -> None:
    conn = _Writes(repeat=True, stored="routine")
    again = notify.post(conn, "comment", [SHARER], idea_id=IDEA, sender=CREW, refs=ENTRY,  # type: ignore[arg-type]
                        needs_you=True, dedupe_key="t:edge")  # fmt: skip
    assert again.updated == [7] and again.ids == []
    assert ("UPDATE notifications SET urgency = 'immediate' WHERE id = %s", (7,)) in conn.updates
    assert conn.outside() == ["email", "teams"]


@pytest.mark.parametrize(
    ("stored", "needs_you"),
    [
        ("immediate", True),  # it went out when it was posted (or before the rule, r6): never twice
        (None, True),  # an item the club seed wrote: never had an outside row and is never sent now
        ("routine", False),  # still waiting: the repeat changes nothing outside the app
    ],
)
def test_bld_a255_any_other_repeat_queues_nothing_outside(
    stored: str | None, needs_you: bool, teams_on: None
) -> None:
    conn = _Writes(repeat=True, stored=stored)
    notify.post(conn, "comment", [SHARER], idea_id=IDEA, sender=CREW, refs=ENTRY,  # type: ignore[arg-type]
                needs_you=needs_you, dedupe_key="t:edge")  # fmt: skip
    assert conn.outside() == []
    assert not any("urgency = 'immediate'" in sql for sql, _ in conn.updates)


def test_bld_a255_l_notify_job_queues_the_inbox_digest_before_the_monday_flush(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The decide-by digest, then the Inbox digest, then the old routes' held mail (on Mondays; `force` here)."""
    from jobs import handlers

    calls: list[str] = []

    def called(name: str) -> Any:
        def record(*_: Any, **__: Any) -> int:
            calls.append(name)
            return 0

        return record

    monkeypatch.setattr(digest, "queue", called("decide_by"))
    monkeypatch.setattr(digest, "queue_inbox", called("inbox"))
    monkeypatch.setattr("comms.send.send_digests", called("flush"))
    handlers.comms_digest(object(), {"force": True})  # type: ignore[arg-type]
    assert calls == ["decide_by", "inbox", "flush"]


def test_bld_a255_out_of_working_hours_nothing_is_read_or_queued(monkeypatch: pytest.MonkeyPatch) -> None:
    """A weekend, a holiday or out of hours (the calendar says the next open time is later): no query at all, so the
    items roll into the next working day's window. The real calendar is checked in CI against the database."""

    class _Refuse:
        def execute(self, *_: Any) -> None:
            raise AssertionError("no query out of hours")

    monkeypatch.setattr(digest, "next_send_time", lambda now, urgency: now + dt.timedelta(hours=1))
    assert digest.queue_inbox(_Refuse(), now=NOW) == 0  # type: ignore[arg-type]


def test_bld_a255_compose_routes_the_inbox_digest_and_nothing_left_is_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from comms import send

    seen: list[tuple[str, dict[str, Any]]] = []

    def waiting(conn: Any, user_id: str, since: object, until: object) -> list[dict[str, Any]]:
        seen.append((user_id, {"since": since, "until": until}))
        return []

    monkeypatch.setattr(digest, "waiting_items", waiting)
    refs = {"since": None, "until": "2026-11-18T05:00:00+00:00"}
    row = {"kind": None, "event": digest.INBOX_EVENT}
    assert send.compose(desk._Conn(), SHARER, digest.INBOX_EVENT, digest.INBOX_TEMPLATE, refs, row) is None  # type: ignore[arg-type]
    assert seen == [(SHARER, refs)]


def _waiting(
    kind: str, sender: str | None, item_id: int, extra: dict[str, Any] | None = None
) -> dict[str, Any]:
    row = desk._row(kind, sender, "in_app", extra)
    return {**row, "id": item_id, "needs_you": False, "due_at": None}


def test_bld_a255_l_notify_3_dec111_dec113_the_digest_names_senders_as_the_inbox_does(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One section per item still unread, oldest first, each headed by its own email's subject: the review desk and
    the Ones Committee as one to the sharer, a crew member by name; no reviewer or committee member in any form, no
    one's words (the refs hold IDs only), and the subject counts the sections."""
    items = [
        _waiting("comment", REVIEWER, 61, {**ENTRY, "as_desk": True}),
        _waiting("comment", MEMBER, 62, {**ENTRY, "as_committee": True}),
        _waiting("comment", CREW, 63, ENTRY),
        _waiting("worth_revised", REVIEWER, 64),
    ]
    monkeypatch.setattr(digest, "waiting_items", lambda *_: items)
    conn = desk._Conn()
    mail = digest.compose_inbox(conn, SHARER, {"since": None, "until": "2026-11-18T06:30:00+00:00"}, NOW)  # type: ignore[arg-type]
    assert mail is not None
    assert mail.subject == "Your 1% Club update: 4 new"
    headings = [
        "The review desk commented on your idea",
        "The Ones Committee commented on your idea",
        "Ravi Nair commented on your idea",
        "The review desk revised what your idea is worth",
    ]
    at = [mail.text.index(h + "\n") for h in headings]
    assert at == sorted(at)  # in the order the items were posted
    seen = "\n".join((mail.subject, mail.text, mail.html))
    for trace in (*desk.REVIEWER_TRACES, MEMBER, "Rohan", "Mehta", '"RM"'):
        assert trace not in seen, trace
    assert REVIEWER not in conn.people_read and MEMBER not in conn.people_read
    assert (
        "Rejection SMS codes confuse investors" in mail.text
    )  # the idea's title, the one line every message carries


def test_bld_a255_no_template_file_is_seeded() -> None:
    """The digest is built from each item's own template: no new file under the seed, which an upgrade would never
    copy to the server's company repo."""
    seed = Path(__file__).resolve().parents[3] / "seed" / "company-repo" / "comms" / "templates"
    assert (seed / "inbox" / "comment.md").exists()  # the seed's templates are where this looks
    assert not (seed / f"{digest.INBOX_TEMPLATE}.md").exists()
