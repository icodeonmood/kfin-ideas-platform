"""DEC-113 on S-08 (L-CONVO, BLD-F091): a sharer, a crew member, the build team and a mentioned person never read the
name, initials or users.id of a member of the Ones Committee; they read "The Ones Committee" (and "the Ones Committee"
inside a sentence), with no face. The review desk and the Ones Committee still read each other's names, and a member
reads their own lines as "You". J-COMMITTEE/3b's hand-off and J-TRACK/8–9: the sharer reading the conversation after
a reversal or an undone merge. Synthetic people only.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest
from psycopg.types.json import Jsonb

from convo import post
from convo.messages import remove, send
from convo.reads import conversation
from tests import convo_fixtures as fx

NOW = fx.at(17, 10, 30)  # Tuesday 17 November 2026, IST
COMMITTEE_REF = {"id": "", "name": "The Ones Committee", "first_name": "The Ones Committee", "initials": ""}
COMMITTEE_MENTION = {
    "id": "",
    "name": "the Ones Committee",
    "first_name": "the Ones Committee",
    "initials": "",
}
DESK_MENTION = {"id": "", "name": "the review desk", "first_name": "the review desk", "initials": ""}
MASKED = ["kavya", "ravi", "arjun", "tara"]  # the sharer, the crew, the build team, a mentioned person
# the review desk, the core committee, and the member who wrote (who reads "You")
NAMED = ["meera", "sunita", "rohan"]


@pytest.fixture
def db(db: Any) -> Iterator[Any]:
    yield db
    fx.clean(db)


@pytest.fixture
def world(db: Any) -> dict[str, Any]:
    """Kavya's idea with a crew (Ravi) and a build team (Arjun), Meera its reviewer. Rohan (committee) reverses the
    decision and undoes a merge with Nisha's idea; Sunita (core committee) reverses it again, as lane E's seed writes
    it. Rohan writes, mentioning Tara (a colleague, mentioned only) and Meera; Sunita writes with a file; Kavya writes,
    mentioning Rohan by id."""
    kavya, ravi, arjun = fx.person(db, "Kavya Menon"), fx.person(db, "Ravi Nair"), fx.person(db, "Arjun Rao")
    tara, nisha = fx.person(db, "Tara Joshi"), fx.person(db, "Nisha Kapoor")
    meera = fx.person(db, "Meera Iyer", roles=(("reviewer", None),))
    rohan = fx.person(db, "Rohan Mehta", roles=(("committee", None),))
    sunita = fx.person(db, "Sunita Bhatt", roles=(("core_committee", None),))
    idea = fx.idea(db, kavya, status="being_built", reviewer_id=meera["id"], opened_by=meera["id"])
    other = fx.idea(db, nisha, title="Branch staff cannot read the rejection code")
    fx.join_crew(db, idea, ravi, fx.at(15, 9))
    fx.build_team(db, idea, arjun)
    uuid_ = str(idea["id"])

    post(
        db,
        uuid_,
        "committee.reversed",
        author_user_id=rohan["id"],
        payload={"to": "not_now"},
        at=fx.at(16, 15),
    )
    decision = db.execute(
        "INSERT INTO idea_decisions (idea_uuid, choice, reason_encrypted, by_user_id, at) "
        "VALUES (%s, 'not_picked', '\\x00', %s, %s) RETURNING id",
        (idea["id"], meera["id"], fx.at(15, 11)),
    ).fetchone()["id"]
    window = db.execute(
        "INSERT INTO decision_windows (decision_id, state, opens_at, closes_at, max_closes_at) "
        "VALUES (%s, 'reversed', %s, %s, %s) RETURNING id",
        (decision, fx.at(15, 11), fx.at(25, 11), fx.at(30, 11)),
    ).fetchone()["id"]
    reversal = db.execute(
        "INSERT INTO decision_reversals (window_id, to_choice, note_encrypted, by_user_id, at) "
        "VALUES (%s, 'pick', '\\x00', %s, %s) RETURNING id",
        (window, sunita["id"], fx.at(16, 15, 30)),
    ).fetchone()["id"]
    db.execute(  # lane E's seed: no author, the reversal's id
        "INSERT INTO conversation_entries (idea_uuid, type, event, payload, at) VALUES (%s, 'event', %s, %s, %s)",
        (idea["id"], "decision_reversed", Jsonb({"reversal_id": str(reversal)}), fx.at(16, 15, 30)),
    )
    merge = db.execute(
        "INSERT INTO merges (lead_idea_uuid, merged_idea_uuid, via, by_user_id, at) "
        "VALUES (%s, %s, 'review_desk', %s, %s) RETURNING id",
        (idea["id"], other["id"], meera["id"], fx.at(16, 12)),
    ).fetchone()["id"]
    for i in (idea, other):
        post(db, str(i["id"]), "committee.merge_reversed", author_user_id=rohan["id"],
             payload={"merge_id": str(merge)}, at=fx.at(16, 16))  # fmt: skip

    send(db, idea["idea_id"], rohan["id"],
         {"text": "@Tara Joshi can you share the branch numbers? @Meera Iyer please note the reversal.",
          "mentions": [tara["id"], meera["id"]]}, at=fx.at(16, 17))  # fmt: skip
    att = fx.attachment(db, idea, sunita, name="committee-notes.xlsx")
    send(db, idea["idea_id"], sunita["id"], {"text": "Adding the committee’s notes.", "file_ids": [att]},
         at=fx.at(16, 17, 30))  # fmt: skip
    send(db, idea["idea_id"], kavya["id"],
         {"text": "@Rohan Mehta the numbers are in the sheet.", "mentions": [rohan["id"]]}, at=fx.at(17, 9))  # fmt: skip
    return {"kavya": kavya, "ravi": ravi, "arjun": arjun, "tara": tara, "nisha": nisha, "meera": meera,
            "rohan": rohan, "sunita": sunita, "idea": idea, "other": other}  # fmt: skip


def _read(db: Any, w: dict[str, Any], who: str, idea: str = "idea") -> dict[str, Any]:
    return conversation(db, w[idea]["idea_id"], w[who]["id"], at=NOW)


def _blob(view: dict[str, Any]) -> str:
    return json.dumps(view, default=str, ensure_ascii=False)


def _clean_of(blob: str, *people: dict[str, Any]) -> None:
    """Each person's full name, first name, surname, users.id and initials, as the JSON would carry them, appear
    nowhere (the DEC-111 tests' leak check)."""
    for p in people:
        first, last = p["name"].split()[0], p["name"].split()[-1]
        for word in (p["name"], first, last, p["id"], f'"{first[0]}{last[0]}"'):
            assert word not in blob, f"{word!r} reached a reader outside the review desk and the committee"


def _texts(view: dict[str, Any]) -> list[str]:
    return [e["text"] for e in view["entries"] if e["type"] == "event"]


def _has_line(view: dict[str, Any], sentence: str) -> bool:
    return any(t.startswith(sentence) for t in _texts(view))


def _message(view: dict[str, Any], text_start: str) -> dict[str, Any]:
    [m] = [e for e in view["entries"] if e["type"] == "message" and e["text"].startswith(text_start)]
    return m


# --- Readers outside the review desk and the committee ----------------------------------------------------------
@pytest.mark.parametrize("who", MASKED)
def test_dec_113_l_convo_a_reader_outside_the_desk_and_the_committee_never_gets_a_members_name(
    db: Any, world: dict[str, Any], who: str
) -> None:
    w = world
    _clean_of(_blob(_read(db, w, who)), w["rohan"], w["sunita"])


@pytest.mark.parametrize("who", ["kavya", "ravi", "arjun"])
def test_dec_113_l_convo_3_j_committee_3b_the_committees_event_lines_read_the_ones_committee(
    db: Any, world: dict[str, Any], who: str
) -> None:
    """committee.reversed, lane E's seeded decision_reversed and committee.merge_reversed (J-COMMITTEE/3b's hand-off,
    J-TRACK/8)."""
    view = _read(db, world, who)
    lines = [t for t in _texts(view) if t.startswith("The Ones Committee")]
    assert lines == [
        "The Ones Committee reversed the decision. It’s now Not now. Monday 16 November, 3:00 pm",
        "The Ones Committee reversed the decision. It’s now Picked. 3:30 pm",  # lane E's seeded line
        "The Ones Committee undid the merge. Each idea is on its own again. 4:00 pm",
    ]
    # The other idea's sharer reads the undone merge on their own idea the same way.
    other = _read(db, world, "nisha", "other")
    assert _has_line(other, "The Ones Committee undid the merge. Each idea is on its own again.")
    _clean_of(_blob(other), world["rohan"], world["sunita"])


@pytest.mark.parametrize("who", ["kavya", "ravi", "arjun"])
def test_dec_113_l_convo_8_a_members_message_its_files_and_in_this_conversation(
    db: Any, world: dict[str, Any], who: str
) -> None:
    view = _read(db, world, who)
    m = _message(view, "@Tara Joshi can you share")
    assert (m["from"], m["from_label"]) == (COMMITTEE_REF, "The Ones Committee")
    words = "@Tara Joshi can you share the branch numbers? @the review desk please note the reversal."
    assert m["text"] == words
    assert [x["name"] for x in m["mentions"]] == ["Tara Joshi", "the review desk"]
    assert m["mentions"][1] == DESK_MENTION
    s = _message(view, "Adding the committee’s notes.")
    assert (s["from"], s["from_label"]) == (COMMITTEE_REF, "The Ones Committee")
    # Only readers who may open files get them (BLD-F062): the sharer here; added by the committee, not a person.
    assert len(s["files"]) == (1 if who == "kavya" else 0)
    assert all(f["added_by"] == COMMITTEE_REF for f in s["files"])

    # One row for the committee, however many members took part; no face, so the @mention picker leaves it out.
    rows = [p for p in view["participants"] if p["label"] == "The Ones Committee"]
    assert [(p["person"], p["doing"]) for p in rows] == [(COMMITTEE_REF, "From the Ones Committee")]
    pickable = [p["person"]["name"] for p in view["participants"] if not p["you"] and p["person"]["id"]]
    assert "The Ones Committee" not in pickable and "Tara Joshi" in pickable


@pytest.mark.parametrize("who", ["kavya", "ravi", "arjun"])
def test_dec_113_l_convo_6_a_mention_of_a_member_reads_at_the_ones_committee(
    db: Any, world: dict[str, Any], who: str
) -> None:
    m = _message(_read(db, world, who), "@the Ones Committee the numbers")
    assert m["text"] == "@the Ones Committee the numbers are in the sheet."
    assert m["mentions"] == [COMMITTEE_MENTION]


def test_dec_113_l_convo_6_a_mentioned_person_replies_to_the_ones_committee(
    db: Any, world: dict[str, Any]
) -> None:
    view = _read(db, world, "tara")  # mentioned by Rohan, nothing else (BLD-F052)
    assert view["composer"]["placeholder"] == "Reply to the Ones Committee"
    [m] = [e for e in view["entries"] if e["type"] == "message"]
    assert (m["from"], m["from_label"]) == (COMMITTEE_REF, "The Ones Committee") and m["mentions_you"]
    rows = [(p["label"], p["doing"]) for p in view["participants"]]
    assert rows.count(("The Ones Committee", "From the Ones Committee")) == 1


def test_dec_113_l_convo_8_bld_f092_a_member_only_mentioned_reads_mentioned_until_a_member_writes(
    db: Any,
) -> None:
    """The review desk mentions a member before any member has written: the sharer's committee row reads "Mentioned".
    Once a member writes, the same one row reads "From the Ones Committee" (BLD-F092)."""
    kavya = fx.person(db, "Kavya Menon")
    meera = fx.person(db, "Meera Iyer", roles=(("reviewer", None),))
    rohan = fx.person(db, "Rohan Mehta", roles=(("committee", None),))
    idea = fx.idea(db, kavya, reviewer_id=meera["id"], opened_by=meera["id"])
    send(db, idea["idea_id"], meera["id"],
         {"text": "@Rohan Mehta can you look at this before Friday?", "mentions": [rohan["id"]]},
         at=fx.at(17, 9))  # fmt: skip

    def rows() -> list[tuple[str, str]]:
        view = conversation(db, idea["idea_id"], kavya["id"], at=NOW)
        _clean_of(_blob(view), rohan, meera)
        return [(p["label"], p["doing"]) for p in view["participants"] if p["label"] == "The Ones Committee"]

    assert rows() == [("The Ones Committee", "Mentioned")]
    send(db, idea["idea_id"], rohan["id"], {"text": "Looked at it; the numbers hold."}, at=fx.at(17, 9, 30))
    assert rows() == [("The Ones Committee", "From the Ones Committee")]


@pytest.mark.parametrize(
    "order", ["mentioned_then_another_member_writes", "a_member_writes_then_is_mentioned"]
)
def test_dec_113_l_convo_8_bld_f092_the_committee_row_reads_from_the_ones_committee_once_any_member_wrote(
    db: Any, order: str
) -> None:
    """Whichever member wrote, and whether before or after a member was mentioned, the one committee row reads "From
    the Ones Committee" (the f/followups-p1 review's two more orders)."""
    kavya = fx.person(db, "Kavya Menon")
    meera = fx.person(db, "Meera Iyer", roles=(("reviewer", None),))
    rohan = fx.person(db, "Rohan Mehta", roles=(("committee", None),))
    sunita = fx.person(db, "Sunita Bhatt", roles=(("committee", None),))
    idea = fx.idea(db, kavya, reviewer_id=meera["id"], opened_by=meera["id"])
    ref = idea["idea_id"]
    mention = {"text": "@Rohan Mehta can you look at this before Friday?", "mentions": [rohan["id"]]}
    if order == "mentioned_then_another_member_writes":
        send(db, ref, meera["id"], mention, at=fx.at(17, 9))
        send(db, ref, sunita["id"], {"text": "Looked at it; the numbers hold."}, at=fx.at(17, 9, 30))
    else:
        send(db, ref, rohan["id"], {"text": "Looked at it; the numbers hold."}, at=fx.at(17, 9))
        send(db, ref, meera["id"], mention, at=fx.at(17, 9, 30))
    view = conversation(db, ref, kavya["id"], at=NOW)
    _clean_of(_blob(view), rohan, sunita, meera)
    rows = [(p["label"], p["doing"]) for p in view["participants"] if p["label"] == "The Ones Committee"]
    assert rows == [("The Ones Committee", "From the Ones Committee")]


# --- The review desk and the committee keep the names ------------------------------------------------------------
@pytest.mark.parametrize("who", NAMED)
def test_dec_113_l_convo_the_review_desk_and_the_committee_read_the_members_by_name(
    db: Any, world: dict[str, Any], who: str
) -> None:
    w = world
    view = _read(db, w, who)
    me = who == "rohan"
    rohan_says = "You" if me else "Rohan Mehta from the Ones Committee"
    sunita_says = "You" if who == "sunita" else "Sunita Bhatt from the Ones Committee"
    assert _has_line(view, f"{rohan_says} reversed the decision. It’s now Not now.")
    assert _has_line(view, f"{sunita_says} reversed the decision. It’s now Picked.")
    assert _has_line(view, f"{rohan_says} undid the merge. Each idea is on its own again.")
    m = _message(view, "@Tara Joshi can you share")
    assert m["from_label"] == rohan_says and m["from"]["id"] == w["rohan"]["id"] and m["you"] is me
    assert m["text"] == "@Tara Joshi can you share the branch numbers? @Meera Iyer please note the reversal."
    assert [x["id"] for x in m["mentions"]] == [w["tara"]["id"], w["meera"]["id"]]
    k = _message(view, "@Rohan Mehta the numbers")
    assert [x["id"] for x in k["mentions"]] == [w["rohan"]["id"]]
    s = _message(view, "Adding the committee’s notes.")
    assert all(f["added_by"]["id"] == w["sunita"]["id"] for f in s["files"])
    assert len(s["files"]) == 1  # BLD-B270: a committee-only member opens files too (DEC-107)
    people = {p["person"]["id"]: p for p in view["participants"]}
    assert w["rohan"]["id"] in people and w["sunita"]["id"] in people
    assert people[w[who]["id"]]["label"] == "You"
    assert "The Ones Committee" not in [p["label"] for p in view["participants"]]


# --- What POST and DELETE return (entry_for) ---------------------------------------------------------------------
@pytest.mark.parametrize("who", ["kavya", "ravi"])
def test_dec_113_l_convo_7_10_what_post_and_delete_return_names_no_member(
    db: Any, world: dict[str, Any], who: str
) -> None:
    """The sharer or a crew member mentions a member by id (the picker never offers them; the API takes any id)."""
    w = world
    out = send(db, w["idea"]["idea_id"], w[who]["id"],
               {"text": "@Sunita Bhatt and @Rohan Mehta, the sheet is updated.",
                "mentions": [w["sunita"]["id"], w["rohan"]["id"]]}, at=fx.at(17, 10, 20))  # fmt: skip
    _clean_of(_blob(out), w["rohan"], w["sunita"])
    e = out["entry"]
    assert e["you"] and e["from_label"] == "You"
    assert e["text"] == "@the Ones Committee and @the Ones Committee, the sheet is updated."
    assert e["mentions"] == [COMMITTEE_MENTION]
    gone = remove(db, w["idea"]["idea_id"], w[who]["id"], e["id"], at=fx.at(17, 10, 21))
    _clean_of(_blob(gone), w["rohan"], w["sunita"])
    assert gone["entry"]["removed"] and gone["entry"]["text"] == "Message removed"


def test_dec_113_l_convo_7_a_member_reads_their_own_post_as_you(db: Any, world: dict[str, Any]) -> None:
    w = world
    out = send(db, w["idea"]["idea_id"], w["rohan"]["id"], {"text": "Thank you, all."}, at=fx.at(17, 10, 20))
    assert out["entry"]["from_label"] == "You" and out["entry"]["from"]["id"] == w["rohan"]["id"]


# --- The Inbox items a member's message posts (lane A's `as_committee`) ------------------------------------------
def _items(db: Any, entry_id: str) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (str(r["kind"]), str(r["to_user"])): dict(r)
        for r in db.execute(
            "SELECT kind, user_id::text AS to_user, payload, from_user_id::text AS from_user, dedupe_key "
            "FROM notifications WHERE channel = 'in_app' AND payload->>'entry_id' = %s",
            (entry_id,),
        ).fetchall()
    }


def test_dec_113_l_inbox_a_members_message_posts_comment_and_mention_as_the_ones_committee(
    db: Any, world: dict[str, Any]
) -> None:
    w = world
    out = send(db, w["idea"]["idea_id"], w["rohan"]["id"],
               {"text": "One more look at the numbers.",
                "mentions": [w["tara"]["id"], w["ravi"]["id"], w["meera"]["id"], w["sunita"]["id"]]},
               at=fx.at(17, 10, 10))  # fmt: skip
    entry_id = out["entry"]["id"]
    items = _items(db, entry_id)
    # Outside the review desk and the committee: the committee speaks (IDs and a bool only)
    for key in (("comment", w["kavya"]["id"]), ("mention", w["tara"]["id"]), ("mention", w["ravi"]["id"])):
        assert items[key]["payload"] == {"entry_id": entry_id, "as_committee": True}, key
        assert items[key]["from_user"] is None, key  # lane A's notify stores no member for it (BLD-A231)
    assert items[("comment", w["kavya"]["id"])]["dedupe_key"] == (
        f"convo.comment:{w['idea']['id']}:2026111710:committee"
    )
    # The desk and the committee read the members' names in the conversation, so their items carry no flag and
    # store the member who wrote
    for key in (("mention", w["meera"]["id"]), ("mention", w["sunita"]["id"])):
        assert items[key]["payload"] == {"entry_id": entry_id}, key
        assert items[key]["from_user"] == w["rohan"]["id"], key


def test_dec_113_l_inbox_the_committee_the_desk_and_the_crew_in_one_hour_post_three_comment_items(
    db: Any, world: dict[str, Any]
) -> None:
    w = world
    ref, hour = w["idea"]["idea_id"], f"convo.comment:{w['idea']['id']}:2026111711"
    send(db, ref, w["rohan"]["id"], {"text": "Noted."}, at=fx.at(17, 11, 5))
    send(db, ref, w["ravi"]["id"], {"text": "Adding last week’s calls today."}, at=fx.at(17, 11, 10))
    send(db, ref, w["meera"]["id"], {"text": "Thanks for the log."}, at=fx.at(17, 11, 15))
    found = {
        str(r["dedupe_key"]): dict(r)
        for r in db.execute(
            "SELECT dedupe_key, payload, from_user_id::text AS from_user FROM notifications "
            "WHERE channel = 'in_app' AND kind = 'comment' AND user_id = %s AND starts_with(dedupe_key, %s)",
            (w["kavya"]["id"], hour),
        ).fetchall()
    }
    keys = {k: dict(r["payload"]) for k, r in found.items()}
    assert set(keys) == {hour, f"{hour}:committee", f"{hour}:desk"}
    committee, desk = keys[f"{hour}:committee"], keys[f"{hour}:desk"]
    assert committee.get("as_committee") is True and "as_desk" not in committee
    assert desk.get("as_desk") is True and "as_committee" not in desk
    assert set(keys[hour]) == {"entry_id"}
    # The stored sender: none when the committee or the desk speaks as one; the crew member who wrote otherwise
    senders = {k: r["from_user"] for k, r in found.items()}
    assert senders == {f"{hour}:committee": None, f"{hour}:desk": None, hour: w["ravi"]["id"]}
