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
from convo.messages import remove, send
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


# ---------------------------------------------------------------------------------------------------------------
# Follow-ups from the DEC-111 review (BLD-F084 to BLD-F087)
# ---------------------------------------------------------------------------------------------------------------
def _traces(*people: dict[str, Any]) -> list[str]:
    """Each person's full name, first name, surname, users.id and initials as the JSON would carry them."""
    out: list[str] = []
    for p in people:
        first, last = p["name"].split()[0], p["name"].split()[-1]
        out += [p["name"], first, last, p["id"], f'"{first[0]}{last[0]}"']
    return out


def _clean_of(blob: str, *people: dict[str, Any]) -> None:
    for word in _traces(*people):
        assert word not in blob, f"{word!r} reached a reader outside the review desk"


def _texts(view: dict[str, Any]) -> list[str]:
    return [e["text"] for e in view["entries"] if e["type"] == "event"]


@pytest.mark.parametrize(
    ("who", "roles"),
    [
        ("crew_and_desk", (("reviewer", None),)),
        ("sharer_and_desk", (("reviewer", None),)),
        ("core_committee", (("core_committee", None),)),
    ],
)
def test_dec_111_bld_f087_readers_at_the_desk_or_on_the_committee_read_names_whatever_else_they_are(
    db: Any, world: dict[str, Any], who: str, roles: tuple[tuple[str, None], ...]
) -> None:
    """Who reads the desk's names is the reader's role (BLD-F082): a reviewer who is also on the crew, a reviewer
    who shared the idea, and a `core_committee` member all read Meera and Harish by name, and their own lines as
    "You"."""
    w = world
    if who == "sharer_and_desk":
        # Kavya's own idea, read by Kavya once she also holds the reviewer role
        db.execute(fx.GRANT, (w["kavya"]["id"], "reviewer", None))
        reader_id = w["kavya"]["id"]
    else:
        person = fx.person(db, "Nisha Rao", roles=roles)
        if who == "crew_and_desk":
            fx.join_crew(db, w["idea"], person, fx.at(15, 10))
        reader_id = person["id"]
    view = conversation(db, w["idea"]["idea_id"], reader_id, at=NOW)
    m = _message(view, "@Harish Kulkarni please check")
    assert m["from"]["id"] == w["meera"]["id"] and m["from_label"] == "Meera from the review desk"
    assert m["mentions"][0]["id"] == w["harish"]["id"]
    assert "Meera from the review desk opened it. Monday 16 November, 9:50 am" in _texts(view)
    labels = [p["label"] for p in view["participants"]]
    assert "Meera from the review desk" in labels and "The review desk" not in labels
    if who == "sharer_and_desk":
        assert ("You", "Shared the idea") in [(p["label"], p["doing"]) for p in view["participants"]]


@pytest.fixture
def desk_lines(db: Any, world: dict[str, Any]) -> dict[str, Any]:
    """Lane E's seeded `decided` and `desk_merged`, and lane B's `desk.decided`, `desk.merged`, `desk.worth_revised`
    and `desk.decide_by_moved`, on Kavya's idea; Harish (a second reviewer, not the idea's `reviewer_id`) acts on two
    of them. Nisha's idea is joined into Kavya's."""
    from psycopg.types.json import Jsonb

    w = world
    idea, meera, harish = w["idea"], w["meera"], w["harish"]
    decision = db.execute(
        "INSERT INTO idea_decisions (idea_uuid, choice, reason_encrypted, by_user_id, at) "
        "VALUES (%s, 'pick', '\\x00', %s, %s) RETURNING id",
        (idea["id"], meera["id"], fx.at(16, 15)),
    ).fetchone()["id"]
    nisha = fx.person(db, "Nisha Rao")
    other = fx.idea(db, nisha, title="Branch staff cannot read the rejection code", status="merged")
    merge = db.execute(
        "INSERT INTO merges (lead_idea_uuid, merged_idea_uuid, via, by_user_id, at) "
        "VALUES (%s, %s, 'review_desk', %s, %s) RETURNING id",
        (idea["id"], other["id"], harish["id"], fx.at(16, 15, 30)),
    ).fetchone()["id"]

    def seeded(code: str, at: Any, payload: dict[str, Any]) -> None:  # as lane E's seed writes it: no author
        db.execute(
            "INSERT INTO conversation_entries (idea_uuid, type, event, payload, at) VALUES (%s, 'event', %s, %s, %s)",
            (idea["id"], code, Jsonb(payload), at),
        )

    seeded("decided", fx.at(16, 15), {"decision_id": str(decision)})
    seeded("desk_merged", fx.at(16, 15, 30), {"merge_id": str(merge)})
    post(db, str(idea["id"]), "desk.decided", author_user_id=harish["id"], payload={"choice": "not_now"},
         at=fx.at(16, 16))  # fmt: skip
    post(db, str(idea["id"]), "desk.merged", author_user_id=harish["id"], payload={"merge_id": str(merge)},
         at=fx.at(16, 16, 30))  # fmt: skip
    post(db, str(other["id"]), "desk.merged", author_user_id=harish["id"], payload={"merge_id": str(merge)},
         at=fx.at(16, 16, 30))  # fmt: skip
    post(db, str(idea["id"]), "desk.worth_revised", author_user_id=meera["id"], at=fx.at(16, 17))
    post(db, str(idea["id"]), "desk.decide_by_moved", author_user_id=meera["id"], at=fx.at(16, 17, 30))
    return {**w, "nisha": nisha, "other": other}


@pytest.mark.parametrize("who", ["kavya", "ravi", "arjun"])
def test_dec_111_l_convo_3_the_desks_event_lines_read_the_review_desk(
    db: Any, desk_lines: dict[str, Any], who: str
) -> None:
    w = desk_lines
    view = _read(db, w, who)
    _desk_never_named(view, w)
    ref = w["other"]["idea_id"]
    assert [t for t in _texts(view) if t.startswith("The review desk")] == [
        "The review desk opened it. Monday 16 November, 9:50 am",
        "The review desk picked it. 3:00 pm",  # lane E's seeded `decided`
        f"The review desk joined it with {ref}. 3:30 pm",  # lane E's seeded `desk_merged`
        "The review desk chose Not now. 4:00 pm",  # Harish, not the idea's reviewer
        f"The review desk joined it with {ref}. 4:30 pm",
        "The review desk revised what it’s worth. 5:00 pm",
        "The review desk moved the date to decide. 5:30 pm",
    ]
    # The joined idea's closing line, as its sharer reads it, with its link
    closing = conversation(db, ref, w["nisha"]["id"], at=NOW)
    _desk_never_named(closing, w)
    [last] = [e for e in closing["entries"] if e.get("code") == "desk.merged"]
    assert last["text"].startswith(
        f"The review desk joined it with {w['idea']['idea_id']}. The conversation carries on there."
    )
    assert last["link"] == {
        "label": w["idea"]["idea_id"],
        "to": f"/ideas/{w['idea']['idea_id']}/conversation",
    }


def test_dec_111_l_convo_3_the_desk_and_the_committee_still_read_who_did_each_line(
    db: Any, desk_lines: dict[str, Any]
) -> None:
    texts = _texts(_read(db, desk_lines, "rohan"))
    for line in (
        "Meera from the review desk picked it.",
        "Harish from the review desk chose Not now.",
        f"Harish from the review desk joined it with {desk_lines['other']['idea_id']}.",
        "Meera from the review desk revised what it’s worth.",
        "Meera from the review desk moved the date to decide.",
    ):
        assert any(t.startswith(line) for t in texts), line


@pytest.mark.parametrize("who", ["kavya", "ravi", "arjun", "tara"])
def test_dec_111_l_convo_a_second_reviewer_who_is_not_the_ideas_reviewer_writes_as_the_review_desk(
    db: Any, world: dict[str, Any], who: str
) -> None:
    w = world
    send(db, w["idea"]["idea_id"], w["harish"]["id"],
         {"text": "Checked the log. @Tara Joshi, thanks for the calls.", "mentions": [w["tara"]["id"]]},
         at=fx.at(16, 14))  # fmt: skip
    view = _read(db, w, who)
    _desk_never_named(view, w)
    m = _message(view, "Checked the log.")
    assert (m["from"], m["from_label"]) == (DESK_REF, "The review desk")
    desk_rows = [p for p in view["participants"] if p["label"] == "The review desk"]
    assert [p["person"] for p in desk_rows] == [DESK_REF]  # one row, however many of its people wrote
    if who == "tara":  # mentioned by both: replies to the desk, never to Harish
        assert view["composer"]["placeholder"] == "Reply to the review desk"


@pytest.mark.parametrize("who", ["kavya", "ravi"])
def test_dec_111_l_convo_7_10_what_post_and_delete_return_to_the_sharer_and_the_crew_names_no_reviewer(
    db: Any, world: dict[str, Any], who: str
) -> None:
    """The sharer or a crew member writes, mentioning someone at the desk by id (the picker never offers them, but
    the API takes any id): the POST's answer reads "@the review desk", and the DELETE's answer names no one at the
    desk either."""
    w = world
    out = send(db, w["idea"]["idea_id"], w[who]["id"],
               {"text": "@Meera Iyer the numbers are in the sheet.", "mentions": [w["meera"]["id"]]},
               at=fx.at(17, 10, 20))  # fmt: skip
    _clean_of(_blob(out), w["meera"], w["harish"])
    e = out["entry"]
    assert e["you"] and e["from_label"] == "You"
    assert e["text"] == "@the review desk the numbers are in the sheet."
    assert e["mentions"] == [
        {"id": "", "name": "the review desk", "first_name": "the review desk", "initials": ""}
    ]
    gone = remove(db, w["idea"]["idea_id"], w[who]["id"], e["id"], at=fx.at(17, 10, 21))
    _clean_of(_blob(gone), w["meera"], w["harish"])
    assert gone["entry"]["removed"] and gone["entry"]["text"] == "Message removed"


# --- BLD-F084: the Inbox items a message posts say when the review desk speaks (lane A's `as_desk`) ---------------
def _items(db: Any, entry_id: str) -> list[dict[str, Any]]:
    """The in-app Inbox items one message posted: kind, recipient, refs, stored sender, key."""
    return [
        dict(r)
        for r in db.execute(
            "SELECT kind, user_id::text AS to_user, payload, from_user_id::text AS from_user, dedupe_key "
            "FROM notifications WHERE channel = 'in_app' AND payload->>'entry_id' = %s ORDER BY kind, user_id",
            (entry_id,),
        ).fetchall()
    ]


def _as_desk(item: dict[str, Any]) -> bool:
    return item["payload"].get("as_desk") is True


def test_dec_111_bld_f084_l_inbox_a_reviewers_message_posts_comment_and_mention_as_the_review_desk(
    db: Any, world: dict[str, Any]
) -> None:
    import notify

    w = world
    out = send(db, w["idea"]["idea_id"], w["meera"]["id"],
               {"text": "One more question on the calls.",
                "mentions": [w["tara"]["id"], w["ravi"]["id"], w["harish"]["id"], w["rohan"]["id"]]},
               at=fx.at(17, 10, 10))  # fmt: skip
    items = {(i["kind"], i["to_user"]): i for i in _items(db, out["entry"]["id"])}
    # Outside the review desk and the committee: the desk speaks; lane A stores no sender for it
    for key in (("comment", w["kavya"]["id"]), ("mention", w["tara"]["id"]), ("mention", w["ravi"]["id"])):
        assert _as_desk(items[key]), key
        assert items[key]["payload"] == {"entry_id": out["entry"]["id"], "as_desk": True}
        if hasattr(notify, "as_the_desk"):  # lane A's half (BLD-A221) is on this base
            assert items[key]["from_user"] is None, key
    assert items[("comment", w["kavya"]["id"])]["dedupe_key"].endswith(":2026111710:desk")
    # The desk and the committee read the desk's names in the conversation, so their items name Meera
    for key in (("mention", w["harish"]["id"]), ("mention", w["rohan"]["id"])):
        assert not _as_desk(items[key]) and items[key]["from_user"] == w["meera"]["id"], key


@pytest.mark.parametrize("who", ["kavya", "ravi", "rohan", "builder"])
def test_dec_111_bld_f084_l_inbox_a_message_from_the_sharer_the_crew_the_committee_or_a_reviewer_on_the_build_team_is_not_the_desk(
    db: Any, world: dict[str, Any], who: str
) -> None:
    w = world
    if who == "builder":  # a reviewer on the build team speaks as that team, by name (_Speaking)
        writer = fx.person(db, "Vikram Shetty", roles=(("reviewer", None),))
        db.execute(fx.GRANT, (writer["id"], "build_team", w["idea"]["idea_id"]))
    else:
        writer = w[who]
    out = send(db, w["idea"]["idea_id"], writer["id"],
               {"text": "Adding a note for the team.", "mentions": [w["tara"]["id"]]},
               at=fx.at(17, 10, 12))  # fmt: skip
    items = _items(db, out["entry"]["id"])
    assert ("mention", w["tara"]["id"]) in [(i["kind"], i["to_user"]) for i in items]
    assert ("comment", w["kavya"]["id"]) in [(i["kind"], i["to_user"]) for i in items] or who == "kavya"
    for i in items:
        assert not _as_desk(i) and i["from_user"] == writer["id"], i["kind"]
        assert not i["dedupe_key"].endswith(":desk")


# --- BLD-F085: S-08's pill is the status S-06 shows the reader (J-TRACK/3) --------------------------------------
@pytest.mark.parametrize("stored", ["with_review_desk", "needs_you"])
def test_j_track_3_bld_f085_s_08_the_sharer_reads_needs_you_while_questions_are_open_and_the_crew_reads_the_desk(
    db: Any, stored: str
) -> None:
    kavya, ravi = fx.person(db, "Kavya Menon"), fx.person(db, "Ravi Nair")
    meera = fx.person(db, "Meera Iyer", roles=(("reviewer", None),))
    idea = fx.idea(db, kavya, status=stored, reviewer_id=meera["id"])
    fx.join_crew(db, idea, ravi, fx.at(15, 9))
    set_id = fx.question_set(db, idea, meera, ("summary", "often"), fx.at(16, 11, 20))

    def head(who: dict[str, str]) -> tuple[str, str]:
        i = conversation(db, idea["idea_id"], who["id"], at=NOW)["idea"]
        return i["status"], i["meta"]

    ref = idea["idea_id"]
    assert head(kavya) == ("needs_you", f"{ref}, needs you")
    assert head(ravi) == ("with_review_desk", f"{ref}, with the review desk")
    assert head(meera) == ("with_review_desk", f"{ref}, with the review desk")
    fx.answer_all(db, set_id, kavya, fx.at(16, 16))  # the set is answered
    if stored == "with_review_desk":  # nothing open: the sharer reads the desk again
        assert head(kavya) == ("with_review_desk", f"{ref}, with the review desk")
    assert head(ravi)[0] == "with_review_desk"


def test_j_track_3_bld_f085_other_statuses_read_as_stored(db: Any) -> None:
    kavya = fx.person(db, "Kavya Menon")
    idea = fx.idea(db, kavya, status="picked")
    assert conversation(db, idea["idea_id"], kavya["id"], at=NOW)["idea"]["status"] == "picked"


# --- BLD-F086: Teams is named only while it is on (DEC-105) -----------------------------------------------------
@pytest.mark.parametrize("state", ["on", "off"])
def test_dec_105_bld_f086_s_08_no_messages_yet_names_teams_only_while_it_is_on(db: Any, state: str) -> None:
    from core import killswitch

    db.execute("UPDATE kill_switches SET state = %s WHERE name = 'comms.teams'", (state,))
    killswitch.clear_cache()
    try:
        kavya = fx.person(db, "Kavya Menon")
        idea = fx.idea(db, kavya)
        view = conversation(db, idea["idea_id"], kavya["id"], at=NOW)
        assert view["teams_on"] is (state == "on")
        assert view["empty"] == {
            "title": "No messages yet",
            "body": (
                "If the review desk has a question, it shows here and in your Inbox, and we tell you on Teams."
                if state == "on"
                else "If the review desk has a question, it shows here and in your Inbox."
            ),
        }
    finally:
        killswitch.clear_cache()
