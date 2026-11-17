"""L-CONVO entry point (`convo.post`, SHIP_PLAN §5a): the line other lanes write, by code and IDs only."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from typing import Any

import pytest

from convo import LOCK, ConvoError, Ref, post
from tests import convo_fixtures as fx


@pytest.fixture
def db(db: Any) -> Iterator[Any]:
    """The shared `db` fixture, plus clean-up: the people and ideas these tests made are deleted when each test ends."""
    yield db
    fx.clean(db)


def test_l_convo_3_post_writes_an_event_with_ids_and_returns_its_id(db: Any) -> None:
    sharer = fx.person(db, "Kavya Menon")
    reviewer = fx.person(db, "Meera Iyer", roles=(("reviewer", None),))
    idea = fx.idea(db, sharer)
    entry_id = post(db, str(idea["id"]), "desk.opened", author_user_id=reviewer["id"], at=fx.at(16, 9, 50))
    [row] = fx.entries(db, idea["id"])
    assert str(row["id"]) == entry_id
    assert (row["type"], row["event"], str(row["author_user_id"])) == ("event", "desk.opened", reviewer["id"])
    assert row["payload"] == {} and row["text_encrypted"] is None


def test_l_convo_4_post_writes_questions_by_reference(db: Any) -> None:
    sharer = fx.person(db, "Kavya Menon")
    reviewer = fx.person(db, "Meera Iyer", roles=(("reviewer", None),))
    idea = fx.idea(db, sharer, status="needs_you")
    set_id = db.execute(
        "INSERT INTO question_sets (idea_uuid, by_user_id) VALUES (%s, %s) RETURNING id",
        (idea["id"], reviewer["id"]),
    ).fetchone()["id"]
    post(db, str(idea["id"]), "desk.asked", author_user_id=reviewer["id"], payload={"set_id": str(set_id), "count": 3},
         question_set_id=str(set_id), entry_type="questions")  # fmt: skip
    [row] = fx.entries(db, idea["id"])
    assert row["type"] == "questions" and row["question_set_id"] == set_id
    assert row["payload"] == {"set_id": str(set_id), "count": 3}


@pytest.mark.parametrize(
    ("event", "kwargs"),
    [
        ("Desk Opened", {}),
        ("desk.opened", {"payload": {"note": ["free", "text"]}}),
        (
            "desk.opened",
            {"payload": {"reason": "The crew is full for now, so the review desk asked to wait a week."}},
        ),
        ("desk.opened", {"payload": {"score": float("nan")}}),  # JSON cannot hold it
        ("desk.asked", {"entry_type": "questions"}),
        ("desk.note", {"entry_type": "message"}),
    ],
)
def test_l_convo_3_post_refuses_what_breaks_the_contract(db: Any, event: str, kwargs: dict[str, Any]) -> None:
    sharer = fx.person(db, "Kavya Menon")
    idea = fx.idea(db, sharer)
    with pytest.raises(ConvoError):
        post(db, str(idea["id"]), event, **kwargs)
    assert fx.entries(db, idea["id"]) == []


def test_l_convo_3_post_takes_any_json_scalar_so_a_callers_decision_never_rolls_back_over_its_payload(
    db: Any,
) -> None:
    """Lane B's `desk/adapters.say` passes times and numbers as they are: an ISO time (a space, a "+"), a float, a
    boolean, None. None of them may refuse, or the whole decision rolls back (review item 3)."""
    sharer = fx.person(db, "Kavya Menon")
    reviewer = fx.person(db, "Meera Iyer", roles=(("reviewer", None),))
    idea = fx.idea(db, sharer)
    payload: dict[str, Ref] = {"decide_by": "2026-11-20 18:00:00+05:30", "worth": 2.5, "joined": True, "merge_id": None,
               "count": 3, "choice": "not_now"}  # fmt: skip
    with db.transaction():
        post(db, str(idea["id"]), "desk.decide_by_moved", author_user_id=reviewer["id"], payload=payload)
    [row] = fx.entries(db, idea["id"])
    assert row["payload"] == payload


def _holds_convo_lock(db: Any, idea_uuid: str) -> bool:
    """Whether this connection holds the idea's conversation lock: pg_locks shows a one-key advisory lock as its
    high and low 32 bits (classid, objid) with objsubid 1."""
    h = db.execute("SELECT hashtext(%s::uuid::text)::bigint AS h", (idea_uuid,)).fetchone()["h"]
    key = h & 0xFFFFFFFFFFFFFFFF
    row = db.execute(
        "SELECT count(*) AS n FROM pg_locks WHERE locktype = 'advisory' AND pid = pg_backend_pid() "
        "AND objsubid = 1 AND classid::bigint = %s AND objid::bigint = %s AND granted",
        (key >> 32, key & 0xFFFFFFFF),
    ).fetchone()
    return int(row["n"]) == 1


def test_bld_f057_l_convo_3_post_and_send_take_the_ideas_lock_before_reading_the_last_lines_time(
    db: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One connection only (lane A's rule for the shared database): the lock is held inside the transaction after
    each write and gone after it ends; and it is taken before the INSERT that reads max(at)."""
    from convo.messages import send

    ravi, kavya = fx.person(db, "Ravi Nair"), fx.person(db, "Kavya Menon")
    idea = fx.idea(db, ravi)
    fx.join_crew(db, idea, kavya)
    uuid_ = str(idea["id"])
    monkeypatch.setattr("convo.adapters.notify_post", lambda *a, **k: None)
    monkeypatch.setattr("convo.adapters._hide_message", None)  # the pattern mask: no other lane's statements

    with db.transaction():
        assert not _holds_convo_lock(db, uuid_)
        post(db, uuid_, "crew.joined", author_code=kavya["code"])
        assert _holds_convo_lock(db, uuid_)  # held to the end of the caller's transaction
    assert not _holds_convo_lock(db, uuid_)
    with db.transaction():
        send(db, idea["idea_id"], kavya["id"], {"text": "Hello, crew."})
        assert _holds_convo_lock(db, uuid_)
    assert not _holds_convo_lock(db, uuid_)

    # The order of statements: the lock comes before the INSERT that reads the idea's last line, in both writers.
    issued: list[str] = []
    real = type(db).execute

    def spy(self: Any, query: Any, *args: Any, **kwargs: Any) -> Any:
        issued.append(str(query))
        return real(self, query, *args, **kwargs)

    monkeypatch.setattr(type(db), "execute", spy)
    with db.transaction():
        post(db, uuid_, "crew.left", author_code=kavya["code"])
        send(db, idea["idea_id"], ravi["id"], {"text": "Thanks, Kavya."})
    monkeypatch.undo()
    marks = [("lock" if q == LOCK else "insert") for q in issued
             if q == LOCK or q.startswith("INSERT INTO conversation_entries")]  # fmt: skip
    assert marks == ["lock", "insert", "lock", "insert"]


def test_bld_f057_l_convo_3_lines_written_in_one_transaction_read_back_in_the_order_written(db: Any) -> None:
    """One action writes several lines in one transaction: one `now()` and random ids. They (and a message written
    at that same moment) read back in the order they were written, for every caller of `convo.post`."""
    from convo.messages import send
    from convo.reads import conversation

    ravi, kavya = fx.person(db, "Ravi Nair"), fx.person(db, "Kavya Menon")
    idea = fx.idea(db, ravi)
    fx.join_crew(db, idea, kavya)
    uuid_ = str(idea["id"])
    with db.transaction():
        now = db.execute("SELECT now() AS t").fetchone()["t"]
        written = [
            post(db, uuid_, "teamup.approved_team_only", author_code=ravi["code"]),
            post(db, uuid_, "crew.joined", author_code=kavya["code"]),
            post(db, uuid_, "crew.left", author_code=kavya["code"], at=now - dt.timedelta(seconds=30)),
        ]
        said = send(db, idea["idea_id"], kavya["id"], {"text": "Hello, crew."}, at=now)
        written.append(said["entry"]["id"])
    rows = fx.entries(db, idea["id"])  # ORDER BY at, id: what the reads use
    assert [str(r["id"]) for r in rows] == written
    assert [r["at"] for r in rows] == [now + dt.timedelta(microseconds=n) for n in range(4)]
    assert said["entry"]["at"] == rows[-1]["at"]
    view = conversation(db, idea["idea_id"], ravi["id"], at=now)
    assert [e["id"] for e in view["entries"] if not e["id"].startswith("shared:")] == written


def test_the_fixtures_leave_no_people_or_ideas_behind(db: Any) -> None:
    """The seed's HR import refuses while active users are left in the shared test database (8425f2d)."""
    from convo.messages import send

    ravi, kavya = fx.person(db, "Ravi Nair"), fx.person(db, "Kavya Menon", roles=(("reviewer", None),))
    idea = fx.idea(db, ravi)
    fx.join_crew(db, idea, kavya)
    post(db, str(idea["id"]), "crew.joined", author_code=kavya["code"])
    send(db, idea["idea_id"], kavya["id"], {"text": "Hello."})
    fx.clean(db)
    for table in ("users", "contributor_map", "role_grants", "ideas", "crew_members", "conversation_entries"):
        assert db.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"] == 0, table  # noqa: S608
