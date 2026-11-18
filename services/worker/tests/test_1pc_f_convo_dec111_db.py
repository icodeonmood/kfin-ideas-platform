"""DEC-111 (2) on S-08 (L-CONVO, BLD-F082, BLD-F083): a sharer, a crew member, the build team and a mentioned person
never read the name, initials or users.id of the person at the review desk; they read "The review desk". The review
desk and the Ones Committee still read each other's names. Synthetic people only.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest

from convo import post
from convo.messages import send
from convo.reads import conversation
from tests import convo_fixtures as fx

NOW = fx.at(17, 10, 30)  # Tuesday 17 November 2026, IST
DESK_REF = {"id": "", "name": "The review desk", "first_name": "The review desk", "initials": ""}


@pytest.fixture
def db(db: Any) -> Iterator[Any]:
    yield db
    fx.clean(db)


@pytest.fixture
def world(db: Any) -> dict[str, Any]:
    """Kavya's idea with a crew (Ravi) and a build team (Arjun). Meera at the review desk opens it, asks two
    questions, writes with a file and mentions Harish (also at the desk) and Tara (a colleague, mentioned only);
    Rohan of the Ones Committee writes too."""
    kavya = fx.person(db, "Kavya Menon")
    ravi = fx.person(db, "Ravi Nair")
    arjun = fx.person(db, "Arjun Rao")
    tara = fx.person(db, "Tara Joshi")
    meera = fx.person(db, "Meera Iyer", roles=(("reviewer", None),))
    harish = fx.person(db, "Harish Kulkarni", roles=(("reviewer", None),))
    rohan = fx.person(db, "Rohan Mehta", roles=(("committee", None),))
    idea = fx.idea(db, kavya, status="being_built", reviewer_id=meera["id"], opened_by=meera["id"])
    fx.join_crew(db, idea, ravi, fx.at(15, 9))
    fx.build_team(db, idea, arjun)
    post(db, str(idea["id"]), "desk.opened", author_user_id=meera["id"], at=fx.at(16, 9, 50))
    set_id = fx.question_set(db, idea, meera, ("summary", "often"), fx.at(16, 11, 20))
    post(db, str(idea["id"]), "desk.asked", author_user_id=meera["id"], payload={"set_id": set_id, "count": 2},
         question_set_id=set_id, entry_type="questions", at=fx.at(16, 11, 20))  # fmt: skip
    att = fx.attachment(db, idea, meera, name="branch-call-log.xlsx")
    send(db, idea["idea_id"], meera["id"],
         {"text": "@Harish Kulkarni please check the call log. @Tara Joshi, can you add last week’s calls?",
          "file_ids": [att], "mentions": [harish["id"], tara["id"]]}, at=fx.at(16, 12))  # fmt: skip
    send(db, idea["idea_id"], rohan["id"], {"text": "The committee is following this one."}, at=fx.at(16, 13))
    return {"kavya": kavya, "ravi": ravi, "arjun": arjun, "tara": tara, "meera": meera, "harish": harish,
            "rohan": rohan, "idea": idea, "set_id": set_id}  # fmt: skip


def _read(db: Any, w: dict[str, Any], who: str) -> dict[str, Any]:
    return conversation(db, w["idea"]["idea_id"], w[who]["id"], at=NOW)


def _blob(view: dict[str, Any]) -> str:
    return json.dumps(view, default=str, ensure_ascii=False)


def _desk_never_named(view: dict[str, Any], w: dict[str, Any]) -> None:
    """No reviewer's name, initials or users.id anywhere in what the reader is sent."""
    blob = _blob(view)
    for p in (w["meera"], w["harish"]):
        for word in (p["name"], p["name"].split()[0], p["name"].split()[1], p["id"]):
            assert word not in blob, f"{word!r} reached a reader outside the review desk"
    assert '"MI"' not in blob and '"HK"' not in blob  # their initials


def _message(view: dict[str, Any], text_start: str) -> dict[str, Any]:
    [m] = [e for e in view["entries"] if e["type"] == "message" and e["text"].startswith(text_start)]
    return m


@pytest.mark.parametrize("who", ["kavya", "ravi", "arjun"])
def test_dec_111_l_convo_the_sharer_the_crew_and_the_build_team_read_the_review_desk(
    db: Any, world: dict[str, Any], who: str
) -> None:
    view = _read(db, world, who)
    _desk_never_named(view, world)

    # The desk's message: its author, its files, its mentions and its words.
    m = _message(view, "@the review desk please check")
    assert (m["from"], m["from_label"]) == (DESK_REF, "The review desk")
    assert (
        m["text"] == "@the review desk please check the call log. @Tara Joshi, can you add last week’s calls?"
    )
    assert [x["name"] for x in m["mentions"]] == ["the review desk", "Tara Joshi"]
    assert m["mentions"][0] == {
        "id": "",
        "name": "the review desk",
        "first_name": "the review desk",
        "initials": "",
    }
    # Only readers who may open files get them (BLD-F062): the sharer here; added by the desk, not a person.
    assert len(m["files"]) == (1 if who == "kavya" else 0)
    assert all(f["added_by"] == DESK_REF for f in m["files"])
    # The committee keeps its name (DEC-111 names the review desk only, BLD-F082).
    assert _message(view, "The committee is following")["from_label"] == "Rohan Mehta from the Ones Committee"

    # The desk's events and the questions.
    events = [e["text"] for e in view["entries"] if e["type"] == "event"]
    assert "The review desk opened it. Monday 16 November, 9:50 am" in events
    [q] = [e for e in view["entries"] if e["type"] == "questions"]
    assert (q["by"], q["by_label"]) == (DESK_REF, "The review desk")
    if who == "kavya":
        assert q["title"] == "The review desk has 2 questions about your idea"
        assert view["composer"]["questions_line"].startswith("Answer the review desk’s 2 questions with ")
    else:
        assert q["title"] == "The review desk asked 2 questions."

    # "In this conversation": one row for the desk, no face; the mention picker (people with an id) leaves it out.
    rows = [(p["label"], p["doing"]) for p in view["participants"]]
    assert rows.count(("The review desk", "Reviewing it")) == 1
    assert not any(
        p["label"] == "The review desk" and p["doing"] != "Reviewing it" for p in view["participants"]
    )
    desk_rows = [p for p in view["participants"] if p["label"] == "The review desk"]
    assert [p["person"] for p in desk_rows] == [DESK_REF]
    pickable = [p["person"]["name"] for p in view["participants"] if not p["you"] and p["person"]["id"]]
    assert "The review desk" not in pickable and ("Tara Joshi" in pickable)


def test_dec_111_l_convo_6_a_mentioned_person_replies_to_the_review_desk(
    db: Any, world: dict[str, Any]
) -> None:
    view = _read(db, world, "tara")  # mentioned by Meera, nothing else (BLD-F052)
    _desk_never_named(view, world)
    assert view["composer"]["placeholder"] == "Reply to the review desk"
    [m] = [e for e in view["entries"] if e["type"] == "message"]
    assert m["from_label"] == "The review desk" and m["mentions_you"]


@pytest.mark.parametrize("who", ["harish", "rohan"])
def test_dec_111_the_review_desk_and_the_committee_still_read_each_others_names(
    db: Any, world: dict[str, Any], who: str
) -> None:
    view = _read(db, world, who)
    meera, harish = world["meera"], world["harish"]
    m = _message(view, "@Harish Kulkarni please check")
    assert m["from"]["id"] == meera["id"] and m["from"]["initials"] == "MI"
    assert m["from_label"] == "Meera from the review desk"
    assert [x["id"] for x in m["mentions"]] == [harish["id"], world["tara"]["id"]]
    assert all(f["added_by"]["id"] == meera["id"] for f in m["files"])
    events = [e["text"] for e in view["entries"] if e["type"] == "event"]
    assert "Meera from the review desk opened it. Monday 16 November, 9:50 am" in events
    [q] = [e for e in view["entries"] if e["type"] == "questions"]
    assert q["by"]["id"] == meera["id"] and q["title"] == "Meera from the review desk asked 2 questions."
    labels = [p["label"] for p in view["participants"]]
    assert "Meera from the review desk" in labels
    assert ("You" in labels) if who == "harish" else ("Harish Kulkarni" in labels)
    if who == "rohan":  # the committee can mention the desk's people by name (BLD-F066)
        assert any(p["person"]["id"] == harish["id"] for p in view["participants"])


def test_dec_111_a_reviewer_reads_their_own_lines_as_you(db: Any, world: dict[str, Any]) -> None:
    view = _read(db, world, "meera")
    assert "You opened it. Monday 16 November, 9:50 am" in [
        e["text"] for e in view["entries"] if e["type"] == "event"
    ]
    assert _message(view, "@Harish Kulkarni please check")["from_label"] == "You"
    [q] = [e for e in view["entries"] if e["type"] == "questions"]
    assert q["title"] == "You asked 2 questions."


def test_dec_111_l_convo_4_the_sharers_answers_and_the_date_the_desk_decides(db: Any) -> None:
    kavya = fx.person(db, "Kavya Menon")
    meera = fx.person(db, "Meera Iyer", roles=(("reviewer", None),))
    idea = fx.idea(db, kavya, decide_by=fx.at(20, 18), reviewer_id=meera["id"])
    set_id = fx.question_set(db, idea, meera, ("summary", "often"), fx.at(16, 11, 20))
    fx.answer_all(db, set_id, kavya, fx.at(16, 16, 32))
    post(db, str(idea["id"]), "sharer.answered", author_code=kavya["code"], payload={"set_id": set_id, "count": 2},
         question_set_id=set_id, entry_type="answers", at=fx.at(16, 16, 32))  # fmt: skip
    view = conversation(db, idea["idea_id"], kavya["id"], at=NOW)
    [a] = [e for e in view["entries"] if e["type"] == "answers"]
    assert a["title"] == "Your answers to the review desk’s 2 questions"
    assert (
        a["footer"]
        == "Each answer was added to its part of your idea. The review desk decides by Friday 20 November."
    )
    blob = _blob(view)
    assert "Meera" not in blob and meera["id"] not in blob
