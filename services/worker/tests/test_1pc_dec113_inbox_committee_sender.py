"""DEC-113 (BLD-A231) without a database: a sharer never sees a committee member's name either. The Ones Committee's
reversal (L-INBOX.kinds "Decision reversed"; J-COMMITTEE, the reversal reaching the sharer; J-TRACK, the sharer
reading their Inbox) reads "The Ones Committee", with no avatar or initials, to the sharer and the crew: no users.id,
name, first name or initials of the member in the item's JSON, its template variables or its email, and the member's
row is never read for them. The review desk and the committee still read "{name} from the Ones Committee", by their
live role grants. An item stored with the member as its sender (earlier, or by the club seed) reads the same way.
`notify.post` stores the member only on the rows of recipients who hold a desk or committee role, and lane F's
comment and mention with `as_committee: true` (S-08) store no sender and read as the committee. Synthetic people
only; the same flows against the real tables run in CI in tests/test_1pc_dec111_notify_names_db.py."""

from __future__ import annotations

import json
from typing import Any

import pytest

import notify
from notify import render
from onepc.words import ONES_COMMITTEE, ONES_COMMITTEE_START
from tests import test_inbox_desk_name as desk

# The desk test's synthetic people, idea and template loader (the fixture is autouse there; it is bound here too)
_seed_templates = desk._seed_templates
NOW, IDEA = desk.NOW, desk.IDEA
SHARER, CREW = desk.SHARER, desk.OTHER  # Kavya Menon, who shared the idea; Ravi Nair, on her crew (synthetic)
REVIEWER, MEMBER = desk.REVIEWER, desk.MEMBER  # Meera Iyer, at the review desk; Rohan Mehta, on the committee
# Every way the committee member could show: their users.id, name, first name, surname and initials
MEMBER_TRACES = (MEMBER, "Rohan", "Mehta", '"RM"')
AS_ONE = {"id": "", "name": "The Ones Committee", "first_name": "The Ones Committee", "initials": ""}
REVERSAL = {"window_id": "7d1c3b5a-9e2f-4c68-8b40-5a9e7c3d1f26", "to": "pick"}
ENTRY = {"entry_id": "4c2e8a6d-0f1b-4d39-b7e5-9a3c1d5f7b28"}


def _read(
    kind: str, reader: str, sender: str | None, refs: dict[str, Any] | None = None
) -> tuple[desk._Conn, dict[str, Any], dict[str, Any], str]:
    """One reader's item, its template variables and its email, all from one connection."""
    conn = desk._Conn()

    def row(channel: str) -> dict[str, Any]:
        r = desk._row(kind, sender, channel, refs)
        return {**r, "user_id": reader, "payload": refs if refs is not None else r["payload"]}

    item = render.item(conn, row("in_app"), reader, NOW)  # type: ignore[arg-type]
    _, data = render.variables(conn, row("in_app"), reader, NOW)  # type: ignore[arg-type]
    mail = render.email(conn, row("email"), NOW)  # type: ignore[arg-type]
    return conn, item, data, "\n".join((mail.subject, mail.text, mail.html))


def _seen(item: dict[str, Any], data: dict[str, Any], mail: str) -> str:
    return "\n".join(
        (json.dumps(item, ensure_ascii=False), json.dumps(data, ensure_ascii=False, default=str), mail)
    )


def test_dec113_the_shared_words() -> None:
    assert (ONES_COMMITTEE, ONES_COMMITTEE_START) == ("the Ones Committee", "The Ones Committee")


@pytest.mark.parametrize("reader", (SHARER, CREW), ids=("sharer", "crew"))
def test_l_inbox_kinds_dec113_committee_sender_for_sharer(reader: str) -> None:
    """J-COMMITTEE, J-TRACK: the sharer and a crew member read "The Ones Committee reversed a decision on your idea",
    with no avatar or initials, though the item is stored with the member as its sender (an item from before DEC-113,
    or the club seed's): the role check is at the moment of reading, and the member is never read."""
    conn, item, data, mail = _read("decision_reversed", reader, MEMBER, REVERSAL)
    assert item["from"] == AS_ONE and item["body"]["sender"] == ONES_COMMITTEE_START
    assert item["line"] == "reversed a decision on your idea"
    assert data["from"]["display"] == ONES_COMMITTEE_START and data["from"]["system"] is False
    for trace in MEMBER_TRACES:
        assert trace not in _seen(item, data, mail), trace
    assert MEMBER not in conn.people_read  # not read at all, so no future template can name them
    assert (
        "The Ones Committee reversed a decision on your idea: Rejection SMS codes confuse investors" in mail
    )
    assert item["actions"][-1] == {
        "label": "Read the note",
        "style": "primary",
        "to": "/ideas/IDEA-2026-000900",
    }


@pytest.mark.parametrize("reader", (SHARER, CREW), ids=("sharer", "crew"))
def test_l_inbox_kinds_dec113_a_reversal_stored_with_no_sender_reads_the_ones_committee(reader: str) -> None:
    """What `notify.post` now stores for the sharer and the crew: no sender. It reads the committee, never "1% Club"."""
    conn, item, _, mail = _read("decision_reversed", reader, None, REVERSAL)
    assert (item["from"], item["body"]["sender"]) == (AS_ONE, ONES_COMMITTEE_START)
    assert "The Ones Committee reversed a decision on your idea" in mail and MEMBER not in conn.people_read


def test_l_inbox_kinds_dec113_the_reviewer_still_reads_the_members_name() -> None:
    """The review desk and the Ones Committee still see each other's names (DEC-111, DEC-113): the reviewer whose
    decision was reversed reads "Rohan Mehta from the Ones Committee reversed your decision on this idea"."""
    _, item, _, mail = _read("decision_reversed", REVIEWER, MEMBER, REVERSAL)
    assert item["body"]["sender"] == "Rohan Mehta from the Ones Committee"
    assert item["from"] == {
        "id": MEMBER,
        "name": "Rohan Mehta",
        "first_name": "Rohan",
        "initials": "RM",
        "role_label": "from the Ones Committee",
    }
    assert item["line"] == "reversed your decision on this idea"
    assert "Rohan Mehta from the Ones Committee reversed your decision on this idea" in mail


def test_l_inbox_kinds_dec113_a_role_that_has_ended_reads_the_ones_committee() -> None:
    """The role is read live: a reviewer whose grant has ended (no live grant) reads the committee as one."""
    conn = desk._Conn(staff=frozenset())
    row = {**desk._row("decision_reversed", MEMBER), "user_id": REVIEWER}
    item = render.item(conn, row, REVIEWER, NOW)  # type: ignore[arg-type]
    assert (item["from"], item["body"]["sender"]) == (AS_ONE, ONES_COMMITTEE_START)
    assert MEMBER not in conn.people_read


@pytest.mark.parametrize("kind", ("comment", "mention"))
def test_l_inbox_kinds_dec113_as_committee_comment_reads_the_ones_committee(kind: str) -> None:
    """Lane F's seam (S-08): a member's comment or mention carries `as_committee: true` for recipients outside the
    desk and the committee. It reads "The Ones Committee", with no avatar or initials, and the member is never read."""
    conn, item, data, mail = _read(kind, SHARER, MEMBER, {**ENTRY, "as_committee": True})
    assert (item["from"], item["body"]["sender"]) == (AS_ONE, ONES_COMMITTEE_START), kind
    for trace in MEMBER_TRACES:
        assert trace not in _seen(item, data, mail), (kind, trace)
    assert MEMBER not in conn.people_read, kind
    assert f"{ONES_COMMITTEE_START} {item['line']}" in mail, kind
    assert "as_committee" not in json.dumps(item), kind  # a choice of sender only, not given to the reader


@pytest.mark.parametrize("flag", (False, "true", 1, None))
def test_l_inbox_kinds_dec113_only_as_committee_true_speaks_as_the_committee(flag: Any) -> None:
    """Only the boolean true counts: anything else leaves the comment as the writer's (the kind's own rule)."""
    _, item, _, _ = _read("comment", SHARER, CREW, {**ENTRY, "as_committee": flag})
    assert item["body"]["sender"] == "Ravi Nair", flag


class _Writes:
    """`notify.post`'s reads and writes without a database: everyone's preferences (email on), the live desk and
    committee grants, then each INSERT, kept so a test can see what would be stored."""

    def __init__(self, staff: frozenset[str] = frozenset({REVIEWER})) -> None:
        self.staff = staff
        self.inserts: list[tuple[str, tuple[Any, ...]]] = []
        self.role_reads = 0

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> desk._Rows:
        if "FROM users u LEFT JOIN comms_prefs" in sql:
            return desk._Rows(
                [{"id": u, "email": True, "teams": False, "reminders": True} for u in params[0]]
            )
        if "FROM role_grants" in sql:
            self.role_reads += 1
            assert set(params[1]) == {"reviewer", "committee", "core_committee", "core_chair"}
            return desk._Rows([{"user_id": u} for u in params[0] if u in self.staff])
        if sql.startswith("INSERT INTO notifications"):
            self.inserts.append((sql, params))
            return desk._Rows([{"id": len(self.inserts), "inserted": True}])
        return desk._Rows([])

    def stored(self) -> list[tuple[str, str, str | None]]:
        """(recipient, channel, from_user_id) of every row written."""
        out = []
        for _, p in self.inserts:
            # in-app: (user_id, template, payload, event, kind, from_user_id, …); outside: (user_id, channel, …)
            in_app = p[1].startswith("inbox/")
            out.append((p[0], "in_app", p[5]) if in_app else (p[0], p[1], p[6]))
        return out


def test_l_notify_dec113_post_stores_the_member_only_for_the_desk_and_committee(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """J-COMMITTEE: lane B tells the sharer, the crew and the reviewer (committee.py, merging.py). The member is stored
    on the reviewer's row and its email only; the sharer's and the crew's rows and emails carry no sender."""
    monkeypatch.setattr(notify.killswitch, "is_on", lambda *_: False)
    conn = _Writes()
    posted = notify.post(conn, "decision_reversed", [SHARER, CREW, REVIEWER], idea_id=IDEA, sender=MEMBER,  # type: ignore[arg-type]
                         refs=REVERSAL)  # fmt: skip
    assert len(posted.ids) == 3 and conn.role_reads == 1
    assert conn.stored() == [
        (SHARER, "in_app", None),
        (SHARER, "email", None),
        (CREW, "in_app", None),
        (CREW, "email", None),
        (REVIEWER, "in_app", MEMBER),
        (REVIEWER, "email", MEMBER),
    ]


def test_l_notify_dec113_post_stores_no_member_when_no_recipient_holds_a_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(notify.killswitch, "is_on", lambda *_: False)
    conn = _Writes(staff=frozenset())
    notify.post(conn, "decision_reversed", [SHARER], idea_id=IDEA, sender=MEMBER, refs=REVERSAL)  # type: ignore[arg-type]
    assert conn.stored() == [(SHARER, "in_app", None), (SHARER, "email", None)]


@pytest.mark.parametrize("kind", ("comment", "mention"))
def test_l_notify_dec113_as_committee_stores_no_sender(kind: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """With `as_committee: true` the member is stored on no row, and no role is read: the flag is the whole of it.
    The writer is still never one of the recipients."""
    monkeypatch.setattr(notify.killswitch, "is_on", lambda *_: False)
    conn = _Writes()
    posted = notify.post(conn, kind, [SHARER, MEMBER], idea_id=IDEA, sender=MEMBER,  # type: ignore[arg-type]
                         refs={**ENTRY, "as_committee": True})  # fmt: skip
    assert len(posted.ids) == 1 and conn.role_reads == 0
    # a comment or mention waits for the Inbox digest (DEC-138, BLD-A255): no outside row is written when it is posted
    assert conn.stored() == [(SHARER, "in_app", None)]


def test_l_notify_dec113_other_kinds_keep_their_sender_and_read_no_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(notify.killswitch, "is_on", lambda *_: False)
    conn = _Writes()
    notify.post(conn, "comment", [SHARER], idea_id=IDEA, sender=CREW, refs=ENTRY)  # type: ignore[arg-type]
    # the Inbox digest carries the comment (BLD-A255): no email row of its own
    assert conn.stored() == [(SHARER, "in_app", CREW)] and conn.role_reads == 0


def test_l_notify_dec113_the_seam_constants() -> None:
    assert notify.AS_COMMITTEE_REF == "as_committee"
    assert notify.AS_THE_COMMITTEE == frozenset({"decision_reversed"}) == render.COMMITTEE_KINDS
    assert not notify.AS_THE_COMMITTEE & notify.AS_THE_DESK
    assert notify.as_the_committee("comment", {"as_committee": True})
    assert not notify.as_the_committee("decision_reversed", None)  # the reversal depends on the reader
    assert notify.sees_names(desk._Conn(), ["not-a-uuid"]) == set()  # type: ignore[arg-type]  # no query for an ID that is not one


class _Repeat(_Writes):
    """A repeat post with the same key: the first post inserts, the second meets the open in-app item and brings it up
    to date (`ON CONFLICT … DO UPDATE`), then refreshes the outside messages still waiting (`UPDATE`). A comment has
    no outside row of its own since DEC-138 (BLD-A255), so the in-app item is the first insert."""

    def __init__(self) -> None:
        super().__init__()
        self.updates: list[str] = []

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> desk._Rows:
        if sql.startswith("UPDATE notifications"):
            self.updates.append(sql)
            return desk._Rows([])
        if sql.startswith("INSERT INTO notifications") and len(self.inserts) >= 1:  # the in-app item is there
            self.inserts.append((sql, params))
            return desk._Rows([{"id": 1, "inserted": False}])
        return super().execute(sql, params)


def test_l_notify_dec113_a_repeat_as_committee_key_never_restores_the_member(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lane F's hourly key (`convo.comment:{idea}:{hour}:committee`) makes a repeat the normal path for a second
    committee comment within the hour: the item is brought up to date in place, and no SQL on that path sets
    `from_user_id`, so the member is never stored on it (BLD-A231, review N3)."""
    monkeypatch.setattr(notify.killswitch, "is_on", lambda *_: False)
    conn = _Repeat()
    refs = {**ENTRY, "as_committee": True}
    key = "convo.comment:c3d9a1f2:20261119T11:committee"
    first = notify.post(conn, "comment", [SHARER], idea_id=IDEA, sender=MEMBER, refs=refs, dedupe_key=key)  # type: ignore[arg-type]
    again = notify.post(conn, "comment", [SHARER], idea_id=IDEA, sender=MEMBER, refs=refs, dedupe_key=key)  # type: ignore[arg-type]
    assert (first.ids, again.ids, again.updated) == ([1], [], [1])
    # in-app, then the repeat; no email, the Inbox digest carries a comment (BLD-A255)
    assert [stored for _, _, stored in conn.stored()] == [None, None]
    repeat_sql, _ = conn.inserts[-1]
    assert "from_user_id" not in repeat_sql.split("DO UPDATE SET", 1)[1]
    assert conn.updates and all("from_user_id" not in u for u in conn.updates)
