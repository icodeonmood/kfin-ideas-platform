"""L-CONVO entry point (`convo.post`, SHIP_PLAN §5a): the line other lanes write, by code and IDs only."""

from __future__ import annotations

from typing import Any

import pytest

from convo import ConvoError, post
from tests import convo_fixtures as fx


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
