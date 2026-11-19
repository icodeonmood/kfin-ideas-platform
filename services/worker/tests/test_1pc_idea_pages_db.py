"""S-06, S-09, S-07 and L-SUBMIT.withdraw against a freshly migrated database loaded with the synthetic 1% Club seed
(bootstrap/club_seed.py; nobody from the pack's cast). One fixed "now" for the seed and the views, so dates are
stable. Test names carry the module IDs they cover."""

from __future__ import annotations

import datetime as dt
import json
import sys
import types
from collections.abc import Iterator
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest

from bootstrap import club_seed
from core import killswitch
from core.config import get_settings
from ideapage import read
from ideapage.colleague import Paused
from ideapage.mine import my_ideas, snippet
from ideapage.route import idea_view
from ideapage.withdraw import Refused, restore, withdraw
from ideapage.words import IST, day, day_time
from submit import clock
from tests import helpers

NOW = dt.datetime(2026, 11, 16, 6, 0, tzinfo=dt.UTC)  # Monday 16 November, 11:30 am in the office


@pytest.fixture
def club(db: Any, monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    monkeypatch.setenv("COMPANY_REPO_PATH", str(helpers.SEED))
    get_settings.cache_clear()
    killswitch.clear_cache()
    made = club_seed.load(db, NOW)
    people = {
        str(r["name"]).split()[0].lower(): str(r["id"]) for r in db.execute("SELECT id, name FROM users")
    }
    yield {"conn": db, "m": made, "p": people}
    club_seed.remove(db)  # the seed's people and all that is theirs, so no rows outlive the test (rule 14)
    get_settings.cache_clear()
    killswitch.clear_cache()


def view(club: dict[str, Any], key: str, who: str, **kw: Any) -> dict[str, Any]:
    return idea_view(club["conn"], key, club["p"][who], now=NOW, **kw)


def ref(club: dict[str, Any], key: str) -> str:
    return str(club["m"][key].ref)


def nodes(v: dict[str, Any]) -> list[tuple[str, str, str | None]]:
    return [(n["stage"], n["state"], n.get("detail")) for n in v["idea"]["stages"]]


# --- S-06: the sharer's page --------------------------------------------------------------------------------------


def test_s06_states_just_shared_shows_the_decide_by_date(club: dict[str, Any]) -> None:
    v = view(club, ref(club, "T5"), "tanvi")
    idea = club["conn"].execute("SELECT * FROM ideas WHERE idea_id = %s", (ref(club, "T5"),)).fetchone()
    page = v["page"]
    assert v["view"] == "sharer" and page["state"] == "just_shared" and page["state_label"] == "Just shared"
    assert page["pill"] == {"status": "with_review_desk", "label": "With the review desk", "variant": "blue"}
    assert page["card"]["lead"] == f"The review desk will look at it by {day(idea['decide_by'], NOW)}."
    assert page["card"]["rest"] == "We’ll tell you on Teams and by email when anything changes."
    # S-06.phone (PhoneStatus.md): the shorter lines and the reference line under the title
    assert page["card"]["phone_rest"] == "We’ll tell you on Teams and by email."
    assert page["window"]["phone_line"] == (
        f"Open to changes until {day(idea['edit_closes_at'], NOW)}. Edit or withdraw it before the review desk "
        "opens it."
    )
    assert page["reference_line"] == (
        f"Reference {ref(club, 'T5')}, shared {day(idea['shared_at'], NOW)}, {idea['area']}"
    )
    assert page["conversation"]["phone_empty_line"] == (
        "No messages yet. If the review desk has a question, it shows up here and in your Inbox."
    )
    assert page["window"]["open"] and page["window"]["line"].startswith(
        f"Open to changes until {day(idea['edit_closes_at'], NOW)}."
    )
    assert page["window"]["countdown"]["label"] == "2 days left"
    assert {"edit", "withdraw", "conversation"} <= set(page["actions"])
    assert page["actions"]["withdraw"]["confirm"]["confirm_label"] == "Withdraw it"
    assert page["breadcrumb"] == {"label": "My ideas", "to": "/my-ideas", "current": ref(club, "T5")}
    assert nodes(v)[2] == ("reviewed", "now", f"By {day(idea['decide_by'], NOW)}")
    # BLD-E012: no question set is open, so the card is lane E's own and nothing is composed from lane B's.
    assert v["idea"]["has_open_questions"] is False and "card_from" not in page


def test_s06_layout_breadcrumb_names_where_the_sharer_came_from(club: dict[str, Any]) -> None:
    """S-06.layout/1, S-06.rules/6, J-BROWSE/5: the breadcrumb returns to My ideas' filtered view, to the Wall's
    own view when the sharer opened it from the Wall, and Home after first sharing; an off-site back is dropped."""
    t5 = ref(club, "T5")

    def crumb(**kw: Any) -> dict[str, Any]:
        return dict(view(club, t5, "tanvi", **kw)["page"]["breadcrumb"])

    assert crumb(came_from="my-ideas", back="/my-ideas?filter=needs_you&row=X") == {
        "label": "My ideas, Needs you",
        "to": "/my-ideas?filter=needs_you&row=X",
        "current": t5,
    }
    assert crumb(came_from="wall", back="/wall?sort=popular&at=X&dy=120") == {
        "label": "Wall",
        "to": "/wall?sort=popular&at=X&dy=120",
        "current": t5,
    }
    assert crumb(came_from="wall", back="https://example.com/wall")["to"] == "/wall"
    assert crumb(came_from="wall", back="/my-ideas")["to"] == "/wall"
    assert crumb(came_from="share")["label"] == "Home"


def test_s06_states_questions_from_the_review_desk_leaves_the_card_to_lane_b(club: dict[str, Any]) -> None:
    v = view(club, ref(club, "T6"), "tanvi")
    page = v["page"]
    assert page["state_label"] == "Questions from the review desk"
    assert page["pill"]["label"] == "Needs you" and v["idea"]["status"] == "needs_you"
    assert v["idea"]["has_open_questions"] is True
    # The questions card is lane B's (C-QCARD, GET /ideas/:id/question-set): none of it is built here.
    assert page["card"] is None and page["card_from"] == "question_set" and "questions" not in page
    assert page["lane_b"]["question_set"] == f"/api/ideas/{ref(club, 'T6')}/question-set"
    assert "answer" not in page["actions"]
    assert not page["window"]["open"] and page["window"]["line"].startswith("The review desk opened it on")
    assert "withdraw" not in page["actions"] and "edit" not in page["actions"]
    # T6's set is due at 6 pm today, so it went on Friday 13 November (3 days to answer; club_seed, BLD-E067)
    assert nodes(v)[2][2] == "3 questions for you since Friday 13 November"


def test_s06_states_answers_sent_after_a_partial_send_keeps_the_open_set_for_its_card(
    club: dict[str, Any],
) -> None:
    """J-TRACK.steps/4-5, S-06.states "Answers sent", BLD-E051: "Send 2 answers to Harish" with one question skipped
    leaves the set partly answered and the idea Needs you (lane B, desk/asking.py). The page says "Sent." with the
    review desk's date, and keeps the open set, so lane B's card sits under the sentence for the question left."""
    conn, t6 = club["conn"], ref(club, "T6")
    conn.execute(
        "UPDATE question_sets SET state = 'partly_answered' WHERE idea_uuid = %s", (club["m"]["T6"].uuid,)
    )
    conn.execute("UPDATE ideas SET status = 'needs_you' WHERE idea_id = %s", (t6,))
    v = view(club, t6, "tanvi")
    page = v["page"]
    assert page["state"] == "answers_sent" and page["state_label"] == "Answers sent"
    assert (
        page["card"]["lead"] == "Sent. The review desk has your answers."
    )  # DEC-111: never the reviewer's name
    assert page["card"]["rest"].startswith(
        "Each answer was added to its part of your idea, under What you shared."
    )
    assert "card_from" not in page and v["idea"]["has_open_questions"] is True
    assert not page["window"]["open"] and "withdraw" not in page["actions"]

    # Every question answered: the same sentence, and no set left open
    conn.execute("UPDATE question_sets SET state = 'answered' WHERE idea_uuid = %s", (club["m"]["T6"].uuid,))
    conn.execute("UPDATE ideas SET status = 'with_review_desk' WHERE idea_id = %s", (t6,))
    v = view(club, t6, "tanvi")
    assert v["page"]["state"] == "answers_sent" and v["idea"]["has_open_questions"] is False
    assert v["page"]["card"]["lead"] == "Sent. The review desk has your answers."


def test_s06_states_needs_you_as_lane_b_stores_it(club: dict[str, Any]) -> None:
    """Lane B writes `needs_you` on the idea when it sends questions (E-ENUMS.idea-status)."""
    conn, t6 = club["conn"], ref(club, "T6")
    conn.execute("UPDATE ideas SET status = 'needs_you' WHERE idea_id = %s", (t6,))
    v = view(club, t6, "tanvi")
    assert v["page"]["state"] == "questions" and v["page"]["pill"]["label"] == "Needs you"
    assert v["idea"]["edit_window"]["open"] is False and nodes(v)[2][1] == "now"
    other = view(club, t6, "rekha")
    assert (
        other["idea"]["status"] == "with_review_desk"
        and other["page"]["pill"]["label"] == "With the review desk"
    )
    row = next(i for i in mine(club, "tanvi")["items"] if i["id"] == t6)
    assert row["pill"]["label"] == "Needs you" and row["group"] == "needs_you"
    with pytest.raises(Refused):
        withdraw(conn, t6, club["p"]["tanvi"], None, now=NOW)


def test_s06_states_decisions_leave_the_decision_to_lane_b(club: dict[str, Any]) -> None:
    """Picked, Not now, Not picked and Reversed: the decision, its reason, the committee's window and any reversal
    are lane B's (GET /ideas/:id/decision). This page keeps the state, the pill and the track; the only places it
    says the reason and the committee's note are the desk's and the committee's messages in the conversation card
    (BLD-E058)."""
    expected = {
        "T7": ("Picked", "Picked", ["decision"]),
        "T8": ("Not now", "Not now", ["decision"]),
        "T9": ("Reversed by the Ones Committee", "Picked", ["decision", "reversal"]),
    }
    for key, (label, pill_label, kinds) in expected.items():
        v = view(club, ref(club, key), "tanvi")
        page = v["page"]
        assert page["state_label"] == label and page["pill"]["label"] == pill_label
        assert page["card"] is None and page["card_from"] == "decision"
        assert page["lane_b"]["decision"] == f"/api/ideas/{ref(club, key)}/decision"
        assert "decision" not in v["idea"] and "join_build" not in page["actions"]
        conv = dict(page["conversation"])
        assert [m["kind"] for m in conv.pop("messages")] == kinds
        rest = json.dumps({**v, "page": {**page, "conversation": conv}}, ensure_ascii=False, default=str)
        for words in (
            "compliance sign-off",
            "pricing policy",
            "exchange calendar",
            "Failed dividends cost more",
        ):
            assert words not in rest  # the reason and the note are said once, in their messages
    picked = nodes(view(club, ref(club, "T7"), "tanvi"))
    assert picked[2][1] == "done" and str(picked[2][2]).startswith("Picked, ")
    assert picked[3][1] == "now" and str(picked[3][2]).startswith("Team chosen by ")
    assert (
        nodes(view(club, ref(club, "T9"), "tanvi"))[2][2]
        == "Not picked, then moved to picked by the Ones Committee"
    )
    assert str(nodes(view(club, ref(club, "T8"), "tanvi"))[3][2]).startswith("Looked at again on ")


def test_l_questions_answer_5_answers_under_their_parts_come_from_lane_b(
    club: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Lane B's desk.asking is on main (82668c1), so the page reads whatever it returns. A stand-in fixes what it
    # returns, so this test checks lane E's mapping (an answer under its part, its line) and not lane B's data.
    t7 = ref(club, "T7")
    asked = NOW - dt.timedelta(days=6)
    fake = types.ModuleType("desk.asking")
    fake.answers_by_part = lambda conn, uuid: {
        "often": [
            {
                "question_id": "q1",
                "question": "Across branches?",
                "asked_by": "Harish",
                "asked_at": asked.isoformat(),
                "answer": "Yes, across the six largest branches.",
                "answered_at": asked.isoformat(),
                "by": "Tanvi",
                "files": [],
            },
            {
                "question_id": "q2",
                "question": "Since when?",
                "asked_by": "Harish",
                "asked_at": asked.isoformat(),
                "answer": None,
                "answered_at": None,
                "by": None,
                "files": [],
            },
        ]
    }
    monkeypatch.setitem(sys.modules, "desk.asking", fake)
    often = next(r for r in view(club, t7, "tanvi")["page"]["shared"]["rows"] if r["part"] == "often")
    assert [a["text"] for a in often["answers"]] == ["Yes, across the six largest branches."]
    # DEC-111: lane B's `asked_by` is not read for a sharer outside the desk and the committee
    assert often["answers"][0]["line"] == f"From your answer to the review desk, {day(asked, NOW)}"


def test_s06_layout_5_l_questions_answer_5_seeded_t7_answers_come_through_lane_b_desk_asking_unmocked(
    club: dict[str, Any],
) -> None:
    """The seam, with nothing stubbed: lane B's real `desk.asking.answers_by_part` reads the seeded T7 set (asked by
    Harish, answered by Tanvi, closed with the pick) and S-06 shows each sent answer under its part, with its line,
    exactly as lane B returns it (S-06.layout/5, L-QUESTIONS.answer/5; J-BROWSE/4)."""
    from desk import asking
    from ideapage import adapters

    conn, m = club["conn"], club["m"]
    assert adapters._lane_b_answers() is asking.answers_by_part  # the real module, not a stand-in
    raw = asking.answers_by_part(conn, m["T7"].uuid)
    assert list(raw) == ["often"]
    [sent] = raw["often"]
    assert (sent["asked_by"], sent["by"], sent["answer"]) == (
        "the review desk",  # DEC-111: lane B names the desk, never the reviewer, on the sharer's page
        "Tanvi",
        "Yes, across the six largest branches.",
    )
    answered = dt.datetime.fromisoformat(str(sent["answered_at"]))
    assert answered == NOW - dt.timedelta(days=7.5) + dt.timedelta(hours=20)  # club_seed._questions for T7

    rows = {r["part"]: r for r in view(club, ref(club, "T7"), "tanvi")["page"]["shared"]["rows"]}
    assert rows["often"]["answers"] == [
        {
            "id": sent["question_id"],
            "text": "Yes, across the six largest branches.",
            "at": answered.isoformat(),
            "line": f"From your answer to the review desk, {day(answered, NOW)}",  # DEC-111
            "files": [],
        }
    ]
    assert all(not r.get("answers") for part, r in rows.items() if part != "often")


# --- DEC-111: the review desk, never the reviewer's name, outside the desk and the Ones Committee ------------------

REVIEWERS = ("Harish", "Venkatesan", "Lavanya", "Krishnan")  # the seed's review desk (club_seed.PEOPLE)


def grant(club: dict[str, Any], who: str, role: str) -> None:
    club["conn"].execute("INSERT INTO role_grants (user_id, role) VALUES (%s, %s)", (club["p"][who], role))


def revoke_all(club: dict[str, Any], who: str) -> None:
    club["conn"].execute("DELETE FROM role_grants WHERE user_id = %s", (club["p"][who],))


REVIEWER_KEYS = ("harish", "lavanya")  # their users.id, from the club fixture
REVIEWER_INITIALS = ("HV", "LK")  # Harish Venkatesan, Lavanya Krishnan, as a person object carries them


def no_reviewer_named(payload: dict[str, Any], club: dict[str, Any]) -> bool:
    """No reviewer's name, users.id or initials (as a person object's `initials`) anywhere in the payload."""
    dump = json.dumps(payload, ensure_ascii=False, default=str)
    traces = [*REVIEWERS, *(str(club["p"][k]) for k in REVIEWER_KEYS)]
    traces += [f'"initials": "{i}"' for i in REVIEWER_INITIALS]
    return not any(t in dump for t in traces)


def test_s06_dec111_a_sharer_outside_the_desk_and_committee_never_sees_the_reviewers_name(
    club: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """DEC-111 (J-TRACK/3, /5, /7; BLD-E053): on S-06 a sharer who is not on the review desk or the Ones Committee
    reads "the review desk" wherever a reviewer would be named (the Answers sent card, the track's line, each
    answer's line under its part, the revised worth's by-line) and gets no reviewer on the review card, so no name,
    avatar or initials anywhere in the payload. A sharer on the desk or the committee still reads the name."""
    conn, t6, t7 = club["conn"], ref(club, "T6"), ref(club, "T7")
    conn.execute("UPDATE question_sets SET state = 'answered' WHERE idea_uuid = %s", (club["m"]["T6"].uuid,))
    conn.execute("UPDATE ideas SET status = 'with_review_desk' WHERE idea_id = %s", (t6,))
    row6 = conn.execute("SELECT decide_by FROM ideas WHERE idea_id = %s", (t6,)).fetchone()
    by = day(row6["decide_by"], NOW)
    # T7's answer, as lane B's reader returns it, names who asked (`asked_by`): lane E must not pass it on.
    asked = NOW - dt.timedelta(days=6)
    fake = types.ModuleType("desk.asking")
    fake.answers_by_part = lambda conn, uuid: {
        "often": [
            {
                "question_id": "q1",
                "question": "Across branches?",
                "asked_by": "Harish",
                "answer": "Yes, across the six largest branches.",
                "answered_at": asked.isoformat(),
                "files": [],
            }
        ]
    }
    monkeypatch.setitem(sys.modules, "desk.asking", fake)

    def pages() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        v6, v7 = view(club, t6, "tanvi"), view(club, t7, "tanvi")
        return v6, v7, {r["part"]: r for r in v7["page"]["shared"]["rows"]}

    v6, v7, rows7 = pages()
    assert no_reviewer_named(v6, club) and no_reviewer_named(v7, club)
    assert "reviewer" not in v6["idea"]["review"] and "reviewer" not in v7["idea"].get("review", {})
    assert v6["page"]["card"]["lead"] == "Sent. The review desk has your answers."
    assert nodes(v6)[2] == ("reviewed", "now", f"The review desk has your answers. By {by}")
    assert rows7["cost"]["figures"]["reviewer"]["by_line"] == "Revised by the review desk"
    assert rows7["often"]["answers"][0]["line"] == f"From your answer to the review desk, {day(asked, NOW)}"

    for role in ("committee", "reviewer"):  # the Ones Committee and the review desk keep the name
        grant(club, "tanvi", role)
        v6, v7, rows7 = pages()
        assert v6["page"]["card"]["lead"] == "Sent. Harish has your answers."
        assert nodes(v6)[2] == ("reviewed", "now", f"Harish has your answers. By {by}")
        assert v6["idea"]["review"]["reviewer"]["first_name"] == "Harish"
        assert rows7["cost"]["figures"]["reviewer"]["by_line"] == "Revised by Harish"
        assert rows7["often"]["answers"][0]["line"] == f"From your answer to Harish, {day(asked, NOW)}"
        revoke_all(club, "tanvi")
    assert no_reviewer_named(view(club, t6, "tanvi"), club)  # the grant gone, the name goes with it
    # The decided ideas too: T8 (Not now) and T9 (moved by the Ones Committee), as their sharer reads them
    assert no_reviewer_named(view(club, ref(club, "T8"), "tanvi"), club)
    assert no_reviewer_named(view(club, ref(club, "T9"), "tanvi"), club)


DECIDED_LINE = "The review desk has decided. The full conversation, with every answer, is one tap away."
COMMITTEE_LINE = (
    "The Ones Committee has the last word on this decision. The full conversation is one tap away."
)
THE_DESK = {"id": "", "name": "The review desk", "first_name": "The review desk", "initials": ""}


def lane_b(club: dict[str, Any], key: str, who: str) -> dict[str, Any]:
    """The decision as S-06's reason block and reversal card read it: lane B's `GET /ideas/:id/decision`."""
    from desk.committee import decision_for_viewer

    got = decision_for_viewer(club["conn"], ref(club, key), club["p"][who], NOW)
    assert got is not None and "stage_only" not in got
    return got


def desk_reason(club: dict[str, Any], key: str, who: str) -> str:
    return str(lane_b(club, key, who)["decision"]["reason"])


def decided_at(club: dict[str, Any], key: str) -> dt.datetime:
    row = (
        club["conn"]
        .execute("SELECT at FROM idea_decisions WHERE idea_uuid = %s", (club["m"][key].uuid,))
        .fetchone()
    )
    return row["at"]


def the_desks_message(club: dict[str, Any], key: str, said: str, msg_id: str) -> dict[str, Any]:
    """The desk's message as a sharer outside the desk and the committee reads it (DEC-111)."""
    at = decided_at(club, key)
    return {
        "id": msg_id,
        "kind": "decision",
        "from": THE_DESK,
        "from_label": "The review desk",
        "at": at.isoformat(),
        "at_label": day_time(at, NOW),
        "by_line": f"The review desk, {day_time(at, NOW)}",
        "text": f"{said}. {desk_reason(club, key, 'tanvi')}",
    }


def the_committees_message(club: dict[str, Any], key: str, msg_id: str) -> dict[str, Any]:
    """The committee's message, named as lane B's reversal card names the member, its words the card's note."""
    d = lane_b(club, key, "tanvi")
    by, at = d["reversal"]["by"], dt.datetime.fromisoformat(d["reversal"]["at"])
    return {
        "id": msg_id,
        "kind": "reversal",
        "from": {
            "id": by["id"],
            "name": by["name"],
            "first_name": by["first_name"],
            "initials": by["initials"],
            "role_label": "from the Ones Committee",
        },
        "from_label": f"{by['name']} from the Ones Committee",
        "at": at.isoformat(),
        "at_label": day_time(at, NOW),
        "by_line": d["lines"]["reversal"]["from_line"],
        "text": d["reversal"]["note"],
    }


def test_s06_layout_8_j_track_7_j_review_6_bld_e058_the_decision_is_the_desks_message_in_the_card(
    club: dict[str, Any],
) -> None:
    """BLD-E058 (S-06.layout/8; Status.md and PhoneStatus.md "Picked", "Not now"; J-TRACK/7, J-REVIEW/6): once the
    desk has decided, "You and the review desk" ends with the desk's message, the choice and then the reason word for
    word, the same masked words as the reason block. No empty line next to the decided line. DEC-111: the sharer
    reads it from "The review desk", with no face and nothing of the reviewer."""
    for key, said in (("T7", "Picked"), ("T8", "Not now")):
        v = view(club, ref(club, key), "tanvi")
        conv = v["page"]["conversation"]
        assert conv["sub_line"] == DECIDED_LINE
        assert "empty_line" not in conv and "phone_empty_line" not in conv
        assert conv["messages"] == [the_desks_message(club, key, said, conv["messages"][0]["id"])]
        assert no_reviewer_named(v, club)
    # T8 has no other entry: the decision is the card's one message, and the count says so
    assert view(club, ref(club, "T8"), "tanvi")["page"]["conversation"]["count"] == 1
    t7 = view(club, ref(club, "T7"), "tanvi")["page"]["conversation"]
    assert t7["messages"][0]["text"].startswith("Picked. This is a clear problem with a simple fix.")
    entries = (
        club["conn"]
        .execute(
            "SELECT count(*) AS n FROM conversation_entries WHERE idea_uuid = %s AND type <> 'event'",
            (club["m"]["T7"].uuid,),
        )
        .fetchone()
    )
    assert t7["count"] == int(entries["n"]) + 1


def test_s06_layout_8_l_committee_bld_e058_after_a_reversal_the_committees_message_follows_the_desks(
    club: dict[str, Any],
) -> None:
    """BLD-E058 (Status.md "Reversed by the Ones Committee", L-COMMITTEE.rules/5): the desk's decision stays on
    record as its message, then the committee member's message at the time they reversed it, its words the note the
    reversal card shows (lane B's masked copy), its sender named as the card names them, with their initials. The
    sub-line is the committee's. T9: the desk said Not picked, the committee moved it to Picked. Then it is built
    and shipped: both messages and the committee's sub-line stay, so the card never ends on the desk's Not picked
    alone under "The review desk has decided"."""
    conn, t9 = club["conn"], ref(club, "T9")
    for status, state in (("picked", "reversed"), ("being_built", "being_built"), ("shipped", "shipped")):
        conn.execute("UPDATE ideas SET status = %s WHERE id = %s", (status, club["m"]["T9"].uuid))
        v = view(club, t9, "tanvi")
        conv = v["page"]["conversation"]
        assert v["page"]["state"] == state
        desk, committee = conv["messages"]
        assert desk == the_desks_message(club, "T9", "Not picked", desk["id"])
        assert committee == the_committees_message(club, "T9", committee["id"])
        assert committee["from_label"] == "Manoj Agarwal from the Ones Committee"
        assert committee["from"]["initials"] == "MA" and committee["from"]["id"] == club["p"]["manoj"]
        assert (
            committee["text"]
            == "We can ask the exchange to move the reminder. Failed dividends cost more than the change."
        )
        assert dt.datetime.fromisoformat(desk["at"]) < dt.datetime.fromisoformat(committee["at"])
        assert conv["sub_line"] == COMMITTEE_LINE and DECIDED_LINE not in json.dumps(v, ensure_ascii=False)
        assert "empty_line" not in conv and conv["count"] >= 2
        assert no_reviewer_named(v, club)  # the desk's message still reads "The review desk"
    # A Pick nobody reversed, now being built: the desk's message alone, under the desk's sub-line
    a1 = view(club, ref(club, "A1"), "aparna")["page"]
    assert a1["state"] == "being_built" and a1["conversation"]["sub_line"] == DECIDED_LINE
    assert [m["kind"] for m in a1["conversation"]["messages"]] == ["decision"]


def test_s06_layout_8_dec111_bld_e058_the_desk_and_the_committee_read_who_decided(
    club: dict[str, Any],
) -> None:
    """DEC-111, BLD-E058: a sharer on the review desk or the Ones Committee reads the decision from the person who
    made it, "Lavanya from the review desk, <day>, <time>", with her initials for the face, as Status.md draws
    Meera's. The grant gone, the desk speaks again and the reviewer leaves the payload."""
    t8 = ref(club, "T8")
    at = decided_at(club, "T8")
    for role in ("reviewer", "committee"):
        grant(club, "tanvi", role)
        (m,) = view(club, t8, "tanvi")["page"]["conversation"]["messages"]
        assert m["from"] == {
            "id": club["p"]["lavanya"],
            "name": "Lavanya Krishnan",
            "first_name": "Lavanya",
            "initials": "LK",
            "role_label": "from the review desk",
        }
        assert m["from_label"] == "Lavanya from the review desk"
        assert m["by_line"] == f"Lavanya from the review desk, {day_time(at, NOW)}"
        assert m["text"].startswith("Not now. The right idea, but fees need a pricing policy first.")
        revoke_all(club, "tanvi")
    v = view(club, t8, "tanvi")
    assert v["page"]["conversation"]["messages"][0]["from"] == THE_DESK and no_reviewer_named(v, club)


def test_s06_layout_8_j_review_6_j_track_7_bld_e058_a_decision_sent_after_answers_comes_after_them_masked(
    club: dict[str, Any],
) -> None:
    """J-REVIEW/6 to J-TRACK/7 through lane B's own send (L-DECIDE): B1's answers are in, the desk picks it with a
    reason that holds a customer's PAN. S-06's card then ends with the desk's message, after the answers in time,
    and the reason is the masked copy lane B stored (L-HIDE, DEC-103): the PAN is nowhere in the page. Before the
    decision the card is as it was: no message, and no empty line next to the answers."""
    from desk import decide

    conn, b1 = club["conn"], ref(club, "B1")
    before = view(club, b1, "bhavesh")["page"]["conversation"]
    assert "messages" not in before and "empty_line" not in before
    pan = "ABCPK4321L"  # synthetic, in the PAN pattern
    reason = (
        f"A searchable log saves a day a week. The courier for {pan} came back twice before anyone found it."
    )
    decide.send(conn, b1, club["p"]["lavanya"], {"choice": "pick", "reason": reason}, NOW)
    v = view(club, b1, "bhavesh")
    conv = v["page"]["conversation"]
    (m,) = conv["messages"]
    answered = conn.execute(
        "SELECT max(at) AS at FROM conversation_entries WHERE idea_uuid = %s AND type = 'answers'",
        (club["m"]["B1"].uuid,),
    ).fetchone()["at"]
    assert answered is not None and dt.datetime.fromisoformat(m["at"]) == NOW > answered
    assert m["by_line"] == f"The review desk, {day_time(NOW, NOW)}" and m["from"] == THE_DESK
    assert m["text"] == f"Picked. {desk_reason(club, 'B1', 'bhavesh')}"
    assert m["text"].startswith("Picked. A searchable log saves a day a week. The courier for ")
    assert pan not in json.dumps(v, ensure_ascii=False, default=str)
    assert conv["sub_line"] == DECIDED_LINE and "empty_line" not in conv
    assert no_reviewer_named(v, club)


def test_s06_layout_8_bld_e058_before_a_decision_and_withdrawn_the_card_is_unchanged(
    club: dict[str, Any],
) -> None:
    """BLD-E058 changes nothing before a decision or after a withdrawal: Just shared keeps its empty line and no
    message, Questions from the review desk has no message, and a withdrawn idea has no card."""
    just = view(club, ref(club, "T5"), "tanvi")["page"]["conversation"]
    assert "messages" not in just and just["empty_line"].startswith("No messages yet.") and just["count"] == 0
    asked = view(club, ref(club, "T6"), "tanvi")["page"]
    assert asked["state"] == "questions" and "messages" not in asked["conversation"]
    assert view(club, ref(club, "T10"), "tanvi")["page"]["conversation"] is None


def test_s06_states_withdrawn_offers_restore_it(club: dict[str, Any]) -> None:
    v = view(club, ref(club, "T10"), "tanvi")
    page = v["page"]
    assert (
        page["state_label"] == "Withdrawn" and page["card"]["lead"] == "Withdrawn. It’s back in your drafts."
    )
    assert "No reason given." in page["card"]["rest"]
    assert page["actions"]["restore"]["label"] == "Restore it" and "withdraw" not in page["actions"]
    assert [n[1] for n in nodes(v)][2:] == ["not_going_ahead"] * 3
    assert nodes(v)[2][2] == "Withdrawn before review"
    assert page["conversation"] is None


def test_s06_rules_4_a_merged_idea_shows_where_it_went(club: dict[str, Any]) -> None:
    v = view(club, ref(club, "T11"), "tanvi")
    merged = v["page"]["merged"]
    assert merged["line"] == f"Merged into {ref(club, 'R2')} by the review desk"
    # Said once: the card carries the line, the merged block the note and the link
    assert v["page"]["card"]["lead"] == f"Merged into {ref(club, 'R2')} by the review desk."
    assert merged["note"] == "Both ideas ask for one clear message after a failed debit."
    assert v["idea"]["stages"] == [] and v["idea"]["merged_into"] == ref(club, "R2")
    # No board draws a merged page's conversation card; the rule names the sentence, the note and the link (BLD-E069)
    assert v["page"]["conversation"] is None


def _merge_lines(club: dict[str, Any], key: str, who: str) -> list[str]:
    """The merge lines lane F's S-08 shows this person on this idea (`convo.reads.conversation`), by event code, not
    by their words, so a reworded line in lane F can't make this precondition fail for the wrong reason."""
    from convo.reads import conversation
    from ideapage.read import MERGE_EVENTS

    out = conversation(club["conn"], ref(club, key), club["p"][who], at=NOW)
    return [str(e["code"]) for e in out["entries"] if e["type"] == "event" and e.get("code") in MERGE_EVENTS]


def test_s06_layout_8_l_merge_effects_6_j_similar_7_merged_pages_never_say_no_messages_yet(
    club: dict[str, Any],
) -> None:
    """S-06.layout/8, L-MERGE.effects/6 (BLD-E065; J-SIMILAR/7): T11 was merged into R2 by the review desk. Lane F's
    S-08 shows the merge line on both conversations, so R2's S-06 card does not say "No messages yet": the line is
    counted, as the decision is (BLD-E058), and no message or new line is added for it. Without the merge line the
    count drops by one, so it is that line that counts. T11, the merged idea, has no card at all (BLD-E069): no
    board draws a merged page, and S-06.rules/4 gives it the sentence, the note and the link."""
    conn, m = club["conn"], club["m"]
    for key, who in (("T11", "tanvi"), ("R2", "rekha")):
        assert _merge_lines(club, key, who), key
    assert view(club, ref(club, "T11"), "tanvi")["page"]["conversation"] is None
    conv = view(club, ref(club, "R2"), "rekha")["page"]["conversation"]
    assert conv is not None and conv["count"] >= 1
    assert "empty_line" not in conv and "phone_empty_line" not in conv
    assert "messages" not in conv
    conn.execute(
        "DELETE FROM conversation_entries WHERE idea_uuid = ANY(%s) AND event = 'desk_merged'",
        ([m["T11"].uuid, m["R2"].uuid],),
    )
    after = view(club, ref(club, "R2"), "rekha")["page"]["conversation"]
    assert after["count"] == conv["count"] - 1
    assert ("empty_line" in after) == (after["count"] == 0)


def test_s06_layout_8_l_merge_desk_j_review_m3_after_a_desk_merge_both_pages_drop_no_messages_yet(
    club: dict[str, Any],
) -> None:
    """S-06.layout/8, L-MERGE.desk (BLD-E065; J-REVIEW/M3): Lavanya merges Jatin's J2 into Faisal's F2 from the desk,
    as the walk does, through lane B's `desk_merge`. Lane F's S-08 shows the merge line on both. Faisal's S-06 card,
    still with the review desk, no longer says "No messages yet", and Jatin's merged idea has no card (BLD-E069;
    the walk's row 7: the card was the heading and the link only)."""
    from desk import merging

    conn = club["conn"]
    for key, who in (("J2", "jatin"), ("F2", "faisal")):
        assert view(club, ref(club, key), who)["page"]["conversation"]["empty_line"].startswith(
            "No messages yet."
        )
    merging.desk_merge(
        conn,
        ref(club, "J2"),
        club["p"]["lavanya"],
        {
            "other_idea_id": ref(club, "F2"),
            "note": "You both see bank changes held up by a cheque in the post.",
        },
        NOW,
    )
    for key, who in (("J2", "jatin"), ("F2", "faisal")):
        assert _merge_lines(club, key, who), key
    assert view(club, ref(club, "J2"), "jatin")["page"]["conversation"] is None
    conv = view(club, ref(club, "F2"), "faisal")["page"]["conversation"]
    assert conv is not None and "empty_line" not in conv and "messages" not in conv


def test_s06_sharer_sees_masked_words_until_lane_c_reader_lands(club: dict[str, Any]) -> None:
    v = view(club, ref(club, "T6"), "tanvi")
    words = json.dumps(v["idea"]["own_words"], ensure_ascii=False)
    assert "PAN ••••9Z" in words and "AAAPZ9999Z" not in words
    assert v["page"]["own_words_unmasked"] is False
    assert v["page"]["shared"]["hidden"]["chips"] == ["PAN ••••9Z"]


# --- P-ROUTES.screens: who gets what at /ideas/:id ---------------------------------------------------------------


def test_p_routes_a_non_sharer_never_gets_s06_data(club: dict[str, Any]) -> None:
    v = view(club, ref(club, "T6"), "rekha")
    assert v["view"] == "colleague"
    for private in ("own_words", "hidden", "files", "answers_by_part", "decision", "edit_window", "review"):
        assert private not in v["idea"]
    assert "shared" not in v["page"] and "actions" not in v["page"]


def test_p_routes_a_reviewer_lands_on_the_desk_page(club: dict[str, Any]) -> None:
    v = view(club, ref(club, "R1"), "harish")
    assert v == {"view": "desk", "to": f"/desk/ideas/{ref(club, 'R1')}"}


def test_p_routes_nobody_but_the_owner_sees_a_draft(club: dict[str, Any]) -> None:
    draft = club["m"]["T2"].uuid
    assert view(club, draft, "tanvi") == {"view": "draft", "to": f"/share/{draft}"}
    for who in ("rekha", "harish", "manoj", "kunal"):
        with pytest.raises(read.NotFound):
            view(club, draft, who)


def test_p_routes_a_withdrawn_idea_is_seen_by_its_sharer_alone(club: dict[str, Any]) -> None:
    for who in ("rekha", "harish"):
        with pytest.raises(read.NotFound):
            view(club, ref(club, "T10"), who)


def test_s09_rules_2_bld_e011_a_former_crew_member_gets_one_line_for_a_withdrawn_idea(
    club: dict[str, Any],
) -> None:
    conn, t10 = club["conn"], ref(club, "T10")
    code = conn.execute(
        "SELECT contributor_code FROM contributor_map WHERE user_id = %s", (club["p"]["rekha"],)
    ).fetchone()
    conn.execute(
        "INSERT INTO crew_members (idea_uuid, contributor_code, role, via, joined_at, left_at, left_how) "
        "VALUES (%s, %s, 'crew', 'teamup', %s, %s, 'idea_withdrawn')",
        (
            club["m"]["T10"].uuid,
            code["contributor_code"],
            NOW - dt.timedelta(days=3),
            NOW - dt.timedelta(days=1),
        ),
    )
    v = view(club, t10, "rekha")
    assert v["view"] == "colleague" and v["page"]["state"] == "withdrawn"
    assert (
        v["page"]["team_up"]["line"] == "The person who shared it withdrew it, so nobody else can see it now."
    )
    assert set(v["idea"]) == {"id", "ref", "status"}  # no title, summary, crew, track or name
    with pytest.raises(read.NotFound):
        view(club, t10, "harish")


def test_p_routes_others_reach_an_idea_by_its_reference_only(club: dict[str, Any]) -> None:
    with pytest.raises(read.NotFound):
        view(club, club["m"]["R1"].uuid, "tanvi")
    with pytest.raises(read.NotFound):
        view(club, "IDEA-2026-999999", "tanvi")


# --- S-09: a colleague's idea ----------------------------------------------------------------------------------------


def test_dec_104_s09_never_returns_raw_words(club: dict[str, Any]) -> None:
    conn = club["conn"]
    for key in ("T5", "T6", "T7", "T9"):
        v = view(club, ref(club, key), "rekha")
        dump = json.dumps(v, default=str)
        uid = club["m"][key].uuid
        for m in conn.execute(
            "SELECT id, text_encrypted FROM idea_messages WHERE idea_uuid = %s", (uid,)
        ).fetchall():
            from onepc.context import open_text

            masked = open_text("idea_messages", "text_encrypted", str(m["id"]), m["text_encrypted"])
            assert masked and masked not in dump
        assert "SR40021187" not in dump and "AAAPZ9999Z" not in dump
        assert "reason" not in v["idea"] and "compliance sign-off" not in dump
        assert v["idea"]["summary"] == club["m"][key].spec.summary


def test_s09_omits_the_name_when_hidden_on_the_wall(club: dict[str, Any]) -> None:
    v = view(club, ref(club, "C1"), "tanvi")
    dump = json.dumps(v, default=str)
    assert "Charulata" not in dump and v["idea"]["sharer"] is None
    assert v["page"]["shared_line"] == f"Shared {day(NOW - dt.timedelta(days=16), NOW)}, Compliance, Kolkata"
    assert "The sharer’s own words stay with them" in v["page"]["summary_note"]


def test_s06_layout_5_s09_layout_5_who_it_affects_is_a_list_with_commas(club: dict[str, Any]) -> None:
    """S-06.layout/5 and S-09.layout/5, BLD-E068 (lane G's walk of 19 Nov, row 4; J-SHARE/12, J-RECOVER/14, /15):
    Status.md and Compose.md draw "Investors, KFin teams", Idea.md and PhoneIdea.md "Investors, branch teams": a list
    with commas, never "Investors and KFin teams". What it's worth keeps its sentence ("Saves time and cost")."""
    t8 = ref(club, "T8")  # Tanvi's, affecting investors and KFin teams
    own = {r["part"]: r for r in view(club, t8, "tanvi")["page"]["shared"]["rows"]}
    assert own["who"]["value"] == "Investors, KFin teams"
    about = {a["label"]: a["value"] for a in view(club, t8, "rekha")["page"]["about"]}
    assert about["Who it affects"] == "Investors, KFin teams"
    one = {r["part"]: r for r in view(club, ref(club, "T6"), "tanvi")["page"]["shared"]["rows"]}
    assert one["who"]["value"] == "Investors"


def test_s09_layout_names_the_sharer_and_bld_e008_uses_no_pronoun(club: dict[str, Any]) -> None:
    v = view(club, ref(club, "R1"), "pallavi")
    page = v["page"]
    assert (
        page["shared_line"]
        == f"Shared {day(NOW - dt.timedelta(days=6), NOW)} by Rekha Saxena, Investor service, Hyderabad"
    )
    assert page["summary_note"] == (
        "This is the short summary everyone at KFintech sees. Rekha’s own words stay with them and the review desk."
    )
    assert [a["label"] for a in page["about"]] == [
        "Who it affects",
        "What it’s worth",
        "Area",
        "Linked",
        "Who can see it",
    ]
    assert page["back"] == {"from": "wall", "label": "Back to the Wall", "to": "/wall"}
    for word in (" him", " her ", " his ", " she ", " he "):
        assert word not in json.dumps(page)


def test_s09_states_not_asked_request_sent_and_on_the_crew(club: dict[str, Any]) -> None:
    r1 = ref(club, "R1")
    assert view(club, r1, "pallavi")["page"]["team_up"]["state"] == "not_asked"
    sent = view(club, r1, "bhavesh")["page"]["team_up"]
    assert sent["state"] == "request_sent" and sent["heading"] == "Waiting for Rekha"
    assert sent["line"] == "Rekha reads your note and decides. You’ll hear in your Inbox."
    crew = view(club, r1, "zoya")["page"]["team_up"]
    assert crew["state"] == "on_crew" and crew["line"] == "You’re on the crew. You’ll get its updates."
    assert crew["action"] == {"label": "Say hello", "to": f"/ideas/{r1}/conversation#say-hello"}  # BLD-F069
    assert crew["count_line"].startswith("2 colleagues on it. Rekha leads it and decides who joins.")


def test_s09_rules_2_a_closed_idea_offers_no_team_up(club: dict[str, Any]) -> None:
    t = view(club, ref(club, "F1"), "tanvi")["page"]["team_up"]
    assert t["state"] == "closed" and t["can_team_up"] is False
    m = view(club, ref(club, "T11"), "rekha")["page"]["team_up"]
    assert m["state"] == "merged" and m["link"]["to"].startswith(f"/ideas/{ref(club, 'R2')}")


def test_p_routes_state_s09_back_link_names_where_you_came_from(club: dict[str, Any]) -> None:
    r1 = ref(club, "R1")
    b = view(club, r1, "pallavi", came_from="my-ideas", back="/my-ideas?list=teamed&sort=stage")["page"][
        "back"
    ]
    assert b == {"from": "my-ideas", "label": "Back to My ideas", "to": "/my-ideas?list=teamed&sort=stage"}
    b = view(club, r1, "tanvi", came_from=ref(club, "T5"))["page"]["back"]
    assert b["label"] == f"Back to {ref(club, 'T5')}" and b["to"] == f"/ideas/{ref(club, 'T5')}"
    b = view(club, r1, "pallavi", came_from="wall", back="https://example.org/wall")["page"]["back"]
    assert b["to"] == "/wall"


def test_s09_the_wall_switch_hides_colleagues_ideas(club: dict[str, Any]) -> None:
    club["conn"].execute("UPDATE kill_switches SET state = 'off' WHERE name = 'wall.public'")
    killswitch.clear_cache()
    with pytest.raises(Paused):
        view(club, ref(club, "R1"), "pallavi")
    assert view(club, ref(club, "T5"), "tanvi")["view"] == "sharer"  # the sharer's own page stays


def test_l_wall_justin_4_a_colleague_opening_counts_once_a_day(club: dict[str, Any]) -> None:
    conn, uid, who = club["conn"], club["m"]["R1"].uuid, club["p"]["pallavi"]
    today = NOW.astimezone(IST).date()
    # Start from no open today, whatever the seed spread over the week.
    conn.execute("DELETE FROM idea_opens WHERE idea_uuid = %s AND user_id = %s", (uid, who))
    for _ in range(2):
        view(club, ref(club, "R1"), "pallavi")
    rows = conn.execute(
        "SELECT day FROM idea_opens WHERE idea_uuid = %s AND user_id = %s", (uid, who)
    ).fetchall()
    assert [r["day"] for r in rows] == [today]  # the view's own day in India time, once
    idea_view(conn, ref(club, "R1"), who, now=NOW + dt.timedelta(days=1))
    assert (
        conn.execute(
            "SELECT count(*) AS n FROM idea_opens WHERE idea_uuid = %s AND user_id = %s", (uid, who)
        ).fetchone()["n"]
        == 2
    )


def code_of(club: dict[str, Any], who: str) -> str:
    row = (
        club["conn"]
        .execute("SELECT contributor_code FROM contributor_map WHERE user_id = %s", (club["p"][who],))
        .fetchone()
    )
    return str(row["contributor_code"])


def hide_name(club: dict[str, Any], who: str) -> None:
    """The person hides their name from the Wall (DEC-104). The seed's people are removed with all that is theirs
    after each test, so the setting goes with them."""
    club["conn"].execute(
        "INSERT INTO person_settings (user_id, show_name_on_wall) VALUES (%s, false) "
        "ON CONFLICT (user_id) DO UPDATE SET show_name_on_wall = false",
        (club["p"][who],),
    )


def test_p_product_privacy_s09_a_colleague_sees_the_stage_not_the_committee_reversal(
    club: dict[str, Any],
) -> None:
    """C-TRACK, P-PRODUCT.privacy, DEC-104: T9 was moved by the Ones Committee. Its sharer, its crew and the
    committee read "then moved to picked by the Ones Committee"; a colleague reads the stage and its date only."""
    conn, t9 = club["conn"], ref(club, "T9")
    reversed_at = conn.execute(
        "SELECT r.at FROM decision_reversals r JOIN decision_windows w ON w.id = r.window_id "
        "JOIN idea_decisions d ON d.id = w.decision_id JOIN ideas i ON i.id = d.idea_uuid WHERE i.idea_id = %s",
        (t9,),
    ).fetchone()["at"]
    moved = "Not picked, then moved to picked by the Ones Committee"
    assert nodes(view(club, t9, "tanvi"))[2][2] == moved
    colleague = view(club, t9, "rekha")
    assert colleague["view"] == "colleague"
    assert nodes(colleague)[2] == ("reviewed", "done", f"Picked, {day(reversed_at, NOW)}")
    dump = json.dumps(colleague, ensure_ascii=False, default=str)
    assert "Ones Committee" not in dump and "then moved" not in dump and "Not picked" not in dump
    conn.execute(
        "INSERT INTO crew_members (idea_uuid, contributor_code, role, via, joined_at) "
        "VALUES (%s, %s, 'crew', 'teamup', %s)",
        (club["m"]["T9"].uuid, code_of(club, "zoya"), NOW - dt.timedelta(days=1)),
    )
    assert nodes(view(club, t9, "zoya"))[2][2] == moved  # crew
    assert nodes(view(club, t9, "manoj"))[2][2] == moved  # the Ones Committee


def test_s06_rules_4_dec_104_a_merge_by_a_lead_who_hides_their_name_says_by_its_lead(
    club: dict[str, Any],
) -> None:
    """S-06.rules/4, L-MERGE.effects/1, DEC-104: the merged line names the lead who accepted the merge, unless they
    hide their name from the Wall."""
    conn, t11 = club["conn"], ref(club, "T11")
    conn.execute(
        "UPDATE merges SET via = 'lead_accepted', by_code = %s, by_user_id = NULL WHERE merged_idea_uuid = %s",
        (code_of(club, "rekha"), club["m"]["T11"].uuid),
    )
    assert view(club, t11, "tanvi")["page"]["merged"]["line"] == f"Merged into {ref(club, 'R2')} by Rekha"
    hide_name(club, "rekha")
    v = view(club, t11, "tanvi")
    assert v["page"]["merged"]["line"] == f"Merged into {ref(club, 'R2')} by its lead"
    assert "Rekha" not in json.dumps(v["page"]["merged"], ensure_ascii=False)


def test_s06_layout_l_worth_1_about_only_before_figures_the_sharer_marked_as_approximate(
    club: dict[str, Any],
) -> None:
    """S-06.layout/5, L-WORTH/1 (J-TRACK/1): "About" goes before a worth figure only where the sharer wrote it as
    approximate (`idea_worth.hours_about`, `cost_about`, `revenue_about`); an exact figure, a range, NULL (rows
    written before the flags) and the reviewer's revision read plain."""
    conn, t7, uid = club["conn"], ref(club, "T7"), club["m"]["T7"].uuid

    def figures() -> dict[str, Any]:
        rows = {r["part"]: r for r in view(club, t7, "tanvi")["page"]["shared"]["rows"]}
        return dict(rows["cost"]["figures"])

    seeded = figures()  # the seed: a range of hours, and "about 40k" for the cost
    assert {k: seeded["sharer"][k] for k in ("hours", "cost")} == {
        "hours": "120 to 200 hours a month",
        "cost": "About ₹40,000 a month",
    }
    assert {k: seeded["reviewer"][k] for k in ("hours", "cost")} == {
        "hours": "150 to 220 hours a month",
        "cost": "₹40,000 to ₹60,000 a month",
    }
    conn.execute(
        "UPDATE idea_worth SET hours_low = 80, hours_high = NULL, hours_about = false, cost_about = NULL, "
        "revenue_low = 15000, revenue_about = true WHERE idea_uuid = %s AND by_side = 'sharer'",
        (uid,),
    )
    mixed = figures()["sharer"]
    assert (mixed["hours"], mixed["cost"], mixed["revenue"]) == (
        "80 hours a month",  # exact
        "₹40,000 a month",  # not marked (NULL)
        "About ₹15,000 a month",  # marked as approximate
    )
    conn.execute(
        "UPDATE idea_worth SET hours_about = true, cost_about = false, revenue_about = false "
        "WHERE idea_uuid = %s AND by_side = 'sharer'",
        (uid,),
    )
    flipped = figures()["sharer"]
    assert (flipped["hours"], flipped["cost"], flipped["revenue"]) == (
        "About 80 hours a month",
        "₹40,000 a month",
        "₹15,000 a month",
    )
    assert not any(str(v).startswith("About") for v in figures()["reviewer"].values())


def test_c_track_l_hide_the_checked_line_counts_only_details_still_hidden(club: dict[str, Any]) -> None:
    """C-TRACK, L-HIDE: a detail the sharer brought back with "Show it" is not counted as hidden."""
    conn, t6 = club["conn"], ref(club, "T6")
    uid = club["m"]["T6"].uuid
    similar = nodes(view(club, t6, "tanvi"))[1][2]
    assert str(similar).startswith("1 PAN hidden, ")
    rest = str(similar).removeprefix("1 PAN hidden")
    folio = conn.execute(
        "INSERT INTO hidden_details (idea_uuid, source, source_id, kind, masked) "
        "VALUES (%s, 'message', 'synthetic-p3', 'folio', 'Folio ••••89') RETURNING id",
        (uid,),
    ).fetchone()["id"]
    assert nodes(view(club, t6, "tanvi"))[1][2] == "Personal details hidden" + rest
    conn.execute(
        "UPDATE hidden_details SET state = 'shown', reason = 'made_up_example', shown_at = %s WHERE id = %s",
        (NOW, folio),
    )
    assert nodes(view(club, t6, "tanvi"))[1][2] == "1 PAN hidden" + rest
    conn.execute(
        "UPDATE hidden_details SET state = 'shown', reason = 'made_up_example', shown_at = %s "
        "WHERE idea_uuid = %s",
        (NOW, uid),
    )
    assert nodes(view(club, t6, "tanvi"))[1][2] == "No personal details found" + rest
    conn.execute("DELETE FROM hidden_details WHERE id = %s", (folio,))


def test_c_track_l_similar_failure_the_checked_line_follows_whether_similar_ideas_were_checked(
    club: dict[str, Any],
) -> None:
    """C-TRACK, L-SIMILAR.failure (S-06 at J-SHARE's end and J-TRACK/1, S-09): a check that failed never reads as
    "none found"; nothing recorded says nothing about similar ideas; a done check keeps the count wording. Linked
    ideas are counted whatever was recorded (BLD-E052)."""
    conn, t5, uid = club["conn"], ref(club, "T5"), club["m"]["T5"].uuid
    conn.execute("DELETE FROM similar_links WHERE idea_uuid = %s", (uid,))

    def lines() -> tuple[str | None, str | None]:
        return nodes(view(club, t5, "tanvi"))[1][2], nodes(view(club, t5, "rekha"))[1][2]

    def check(value: str | None) -> None:
        conn.execute("UPDATE ideas SET similar_check = %s WHERE id = %s", (value, uid))

    couldnt = "Couldn’t check for similar ideas. The review desk will."
    check("failed")
    sharer, colleague = lines()
    assert sharer == f"No personal details found. {couldnt}" and colleague == couldnt
    assert "no similar ideas found" not in str(sharer) and "0 similar" not in str(colleague)
    check(None)
    assert lines() == ("No personal details found", None)
    check("done")
    assert lines() == ("No personal details found, no similar ideas found", "0 similar ideas linked")
    for other in ("R1", "P1"):
        conn.execute(
            "INSERT INTO similar_links (idea_uuid, other_idea_uuid, strength, reason) VALUES (%s, %s, 'related', %s)",
            (uid, club["m"][other].uuid, "Related: synthetic"),
        )
    two = ("No personal details found, 2 similar ideas found", "2 similar ideas linked")
    assert lines() == two
    for value in ("failed", None):
        check(value)
        assert lines() == two  # links found after a failed check, or with nothing recorded, are still counted


def test_c_track_l_similar_failure_the_couldnt_check_line_is_lane_c_handover_line() -> None:
    """J-SHARE's end hands over to J-TRACK/1: lane C's handover (`submit.send.checked_line`) and S-06's track say
    the same when similar ideas could not be checked, with the pack's own sentence (L-SIMILAR.failure)."""
    from ideapage import track
    from submit import check as submit_check
    from submit import send

    assert track.COULDNT_CHECK == submit_check.COULDNT_CHECK
    for hidden in (0, 2):
        mine = track.checked_line(hidden, ["pan"] * hidden, 0, "failed", for_sharer=True)
        assert mine == send.checked_line(hidden, None)
    assert track.checked_line(2, ["pan", "folio"], 2, "done", for_sharer=True) == send.checked_line(2, 2)
    assert track.checked_line(0, [], 0, "done", for_sharer=True) == send.checked_line(0, 0)


@pytest.fixture
def similar_runs(club: dict[str, Any]) -> Iterator[Any]:
    """Lane C's `similar_runs` (c/similar, not on main yet): made here with the columns a row needs when it is
    missing, and dropped again; when a migration has made it, only this test's rows are removed."""
    conn = club["conn"]
    made = not conn.execute("SELECT to_regclass('similar_runs') IS NOT NULL AS here").fetchone()["here"]
    if made:
        conn.execute(
            "CREATE TABLE similar_runs (idea_uuid uuid PRIMARY KEY REFERENCES ideas (id) ON DELETE CASCADE, "
            "state text NOT NULL CHECK (state IN ('done', 'failed')), found_while text NOT NULL, "
            "found smallint NOT NULL DEFAULT 0)"
        )
    uids = [m.uuid for m in club["m"].values()]

    def put(uid: str, state: str, found: int = 0) -> None:
        conn.execute(
            "INSERT INTO similar_runs (idea_uuid, state, found_while, found) VALUES (%s, %s, 'checking', %s) "
            "ON CONFLICT (idea_uuid) DO UPDATE SET state = EXCLUDED.state, found = EXCLUDED.found",
            (uid, state, found),
        )

    yield put
    if made:
        conn.execute("DROP TABLE similar_runs")
    else:
        conn.execute("DELETE FROM similar_runs WHERE idea_uuid = ANY(%s::uuid[])", (uids,))


def test_l_similar_failure_similar_status_reads_lane_c_run_first_then_the_idea(
    club: dict[str, Any], monkeypatch: pytest.MonkeyPatch, similar_runs: Any
) -> None:
    """L-SIMILAR.failure: `similar_status` is "done", "failed" or "none". Lane C's `similar_runs` row wins when there
    is one (its retries after sharing write only there); otherwise `ideas.similar_check`, NULL being "none"."""
    from ideapage import adapters
    from ideapage.adapters import similar_status

    conn, uid = club["conn"], club["m"]["T5"].uuid
    lane_c_reader = adapters._lane_c_last_run  # put back by name below, not with undo(): `club` patches too
    monkeypatch.delitem(sys.modules, "similar.matching", raising=False)
    monkeypatch.setattr(
        "ideapage.adapters._lane_c_last_run", lambda: None
    )  # c/similar's reader not here: SQL

    def check(value: str | None) -> None:
        conn.execute("UPDATE ideas SET similar_check = %s WHERE id = %s", (value, uid))

    for value, status in ((None, "none"), ("done", "done"), ("failed", "failed")):
        check(value)
        assert similar_status(conn, uid) == status  # no run for the idea: the idea's own record
    check("done")
    similar_runs(uid, "failed")
    assert similar_status(conn, uid) == "failed"  # the run wins over the idea
    check("failed")
    similar_runs(uid, "done", found=4)
    assert similar_status(conn, uid) == "done"
    check(None)
    assert similar_status(conn, uid) == "done"
    # Through c/similar's own reader once it is here: only its state is read, never `found`.
    fake = types.ModuleType("similar.matching")
    fake.last_run = lambda c, i: {"state": "failed", "found": 4} if i == uid else None
    monkeypatch.setattr("ideapage.adapters._lane_c_last_run", lane_c_reader)
    monkeypatch.setitem(sys.modules, "similar.matching", fake)
    assert similar_status(conn, uid) == "failed"
    other = club["m"]["T6"].uuid
    conn.execute("UPDATE ideas SET similar_check = 'done' WHERE id = %s", (other,))
    assert similar_status(conn, other) == "done"  # no run from the reader: the idea's record


def test_dec_104_s09_a_colleague_never_sees_hidden_names_in_the_crew_or_its_faces(
    club: dict[str, Any],
) -> None:
    """DEC-104, S-09.layout/6: a crew member and a lead who hide their names from the Wall are counted but never
    named, in the idea's crew or in the Team up card's faces."""
    r1 = ref(club, "R1")
    before = view(club, r1, "pallavi")
    assert [m["first_name"] for m in before["idea"]["crew"]["members"]] == ["Zoya"]
    hide_name(club, "zoya")
    v = view(club, r1, "pallavi")
    assert v["idea"]["crew"]["members"] == [] and v["idea"]["crew"]["count"] == 2
    assert [f["first_name"] for f in v["page"]["team_up"]["faces"]] == ["Rekha"]
    assert "Zoya" not in json.dumps(v, ensure_ascii=False, default=str)
    hide_name(club, "rekha")
    v = view(club, r1, "pallavi")
    assert v["idea"]["crew"]["lead"] is None and v["idea"]["sharer"] is None
    assert v["page"]["team_up"]["faces"] == [] and v["page"]["team_up"]["count"] == 2
    dump = json.dumps(v, ensure_ascii=False, default=str)
    assert "Zoya" not in dump and "Rekha" not in dump
    # The sharer still sees their whole crew (crew_of's names_for_all).
    assert [m["first_name"] for m in view(club, r1, "rekha")["idea"]["crew"]["members"]] == ["Zoya"]


# --- L-SUBMIT.withdraw ----------------------------------------------------------------------------------------------


@pytest.fixture
def restore_rows(club: dict[str, Any]) -> Iterator[list[tuple[str, str]]]:
    """(reference, ideas.id) of each idea a test restores: its review clock rows and queued check jobs are removed
    before the seed's own teardown, so nothing a restore wrote outlives the test."""
    restored: list[tuple[str, str]] = []
    yield restored
    for key, uid in restored:
        club["conn"].execute(
            "DELETE FROM sla_timers WHERE entity_type = 'idea' AND entity_id = %s AND stage = 'decide_by'",
            (key,),
        )
        club["conn"].execute("DELETE FROM jobs WHERE dedupe_key = %s", (f"submit.check:{uid}",))


def test_l_submit_withdraw_inside_the_window_then_restore_with_the_same_reference(
    club: dict[str, Any], monkeypatch: pytest.MonkeyPatch, restore_rows: list[tuple[str, str]]
) -> None:
    # Lane E's own path: no restore hook. Importing the worker app plugs lane C's `submit.adapters.on_restored` in
    # (it leaves the idea `checking` and queues `submit.check`, tested in test_1pc_l_sort_submit_db.py), so pin it
    # here rather than depend on which test imported the app first, and leave no job for a later `run_one`.
    from ideapage import withdraw as withdraw_module

    monkeypatch.setattr(withdraw_module, "ON_RESTORED_HOOK", None)
    conn, t5 = club["conn"], ref(club, "T5")
    restore_rows.append((t5, club["m"]["T5"].uuid))
    out = withdraw(conn, t5, club["p"]["tanvi"], "Folio 1234567890 is already being fixed", now=NOW)
    assert out["page"]["state"] == "withdrawn"
    rest = out["page"]["card"]["rest"]
    assert "1234567890" not in rest and "Your reason:" in rest
    assert (
        withdraw(conn, t5, club["p"]["tanvi"], None, now=NOW)["page"]["state"] == "withdrawn"
    )  # repeat: no change
    with pytest.raises(read.NotFound):
        view(club, t5, "rekha")
    back = restore(conn, t5, club["p"]["tanvi"], now=NOW + dt.timedelta(hours=1))
    row = conn.execute("SELECT * FROM ideas WHERE idea_id = %s", (t5,)).fetchone()
    assert back["idea"]["id"] == t5 and row["status"] == "with_review_desk"
    assert row["withdraw_reason_encrypted"] is None
    # L-SUBMIT.send/4, L-SUBMIT.edit/1: first sharing's clocks (submit.clock), from the restore. Restored Monday
    # 16 November at 12:30 pm: decided by Friday 20 November, 6 pm, open to changes until Thursday 19 November.
    p = read.promises()
    assert row["decide_by"] == clock.decide_by(NOW + dt.timedelta(hours=1), p)
    assert row["decide_by"] == dt.datetime(2026, 11, 20, 18, 0, tzinfo=IST)
    assert row["edit_closes_at"] == clock.edit_closes(NOW + dt.timedelta(hours=1), p)
    running = conn.execute(
        "SELECT due_at FROM sla_timers WHERE entity_type = 'idea' AND entity_id = %s AND stage = 'decide_by' "
        "AND state = 'running'",
        (t5,),
    ).fetchall()
    # One review clock, due at the idea's decide-by.
    assert [r["due_at"] for r in running] == [row["decide_by"]]
    assert back["page"]["state"] == "just_shared" and back["page"]["window"]["open"]
    history = [
        r["to_status"]
        for r in conn.execute(
            "SELECT to_status FROM idea_status_history WHERE idea_uuid = %s ORDER BY id", (row["id"],)
        ).fetchall()
    ]
    assert history[-3:] == ["withdrawn", "checking", "with_review_desk"]
    audit = [
        r["action"]
        for r in conn.execute(
            "SELECT action FROM audit_log WHERE entity = %s ORDER BY id", (f"idea:{t5}",)
        ).fetchall()
    ]
    assert audit == ["idea.withdraw", "idea.restore"]
    assert (
        restore(conn, t5, club["p"]["tanvi"], now=NOW)["page"]["state"] == "just_shared"
    )  # repeat: no change
    assert view(club, t5, "rekha")["view"] == "colleague"


def test_l_submit_withdraw_3_restore_through_lane_c_hook_leaves_it_checking_with_one_check_queued(
    club: dict[str, Any], monkeypatch: pytest.MonkeyPatch, restore_rows: list[tuple[str, str]]
) -> None:
    """L-SUBMIT.withdraw/3, L-SUBMIT.send/3–4 (J-RECOVER's restore, the production path): with lane C's hook
    installed as the worker app installs it, a restore leaves the idea `checking` with exactly one `submit.check`
    queued, and decide-by, the edit window and the review clock are written once, by lane C's submit.clock, from the
    restore's own time: `restored_at` and the review clock's start are the same instant (BLD-C154)."""
    from ideapage import withdraw as withdraw_module
    from submit import adapters

    monkeypatch.setattr(withdraw_module, "ON_RESTORED_HOOK", None)  # put back as it was at teardown
    assert adapters.install_hooks()  # as submit.routes.build does when the worker app starts
    assert withdraw_module.ON_RESTORED_HOOK is adapters.on_restored
    conn, t5, uid = club["conn"], ref(club, "T5"), club["m"]["T5"].uuid
    restore_rows.append((t5, uid))
    withdraw(conn, t5, club["p"]["tanvi"], None, now=NOW)
    # No `now`: restore reads the real clock, as in production, and hands that same time to lane C's hook.
    back = restore(conn, t5, club["p"]["tanvi"])
    row = conn.execute("SELECT * FROM ideas WHERE idea_id = %s", (t5,)).fetchone()
    assert row["status"] == "checking" and back["idea"]["id"] == t5
    jobs = conn.execute(
        "SELECT state, dedupe_key FROM jobs WHERE type = 'submit.check' AND payload->>'idea_uuid' = %s",
        (uid,),
    ).fetchall()
    assert jobs == [{"state": "queued", "dedupe_key": f"submit.check:{uid}"}]
    p = read.promises()
    restored = row["restored_at"]
    assert row["decide_by"] == clock.decide_by(
        restored, p
    )  # first sharing's reading, from the restore's time
    assert row["edit_closes_at"] == clock.edit_closes(restored, p)
    assert row["decide_by"].astimezone(IST).time() == dt.time(18, 0)
    running = conn.execute(
        "SELECT started_at, due_at FROM sla_timers WHERE entity_type = 'idea' AND entity_id = %s "
        "AND stage = 'decide_by' AND state = 'running'",
        (t5,),
    ).fetchall()
    # One review clock, started at the very instant of the restore and due at the idea's decide-by.
    assert [(r["started_at"], r["due_at"]) for r in running] == [(restored, row["decide_by"])]
    assert nodes(back)[1] == ("checked_matched", "now", "Checking…")
    history = [
        r["to_status"]
        for r in conn.execute(
            "SELECT to_status FROM idea_status_history WHERE idea_uuid = %s ORDER BY id", (uid,)
        ).fetchall()
    ]
    assert history[-2:] == ["withdrawn", "checking"]
    audit = [
        r["action"]
        for r in conn.execute(
            "SELECT action FROM audit_log WHERE entity = %s ORDER BY id", (f"idea:{t5}",)
        ).fetchall()
    ]
    assert audit == ["idea.withdraw", "idea.restore"]


def test_l_submit_withdraw_is_refused_once_the_desk_opened_it(club: dict[str, Any]) -> None:
    with pytest.raises(Refused) as exc:
        withdraw(club["conn"], ref(club, "T6"), club["p"]["tanvi"], None, now=NOW)
    assert exc.value.status == 409 and exc.value.code == "edit_window_closed"
    assert "opened_by_desk_at" in exc.value.body()["error"]


def test_l_submit_withdraw_only_the_sharer_may_withdraw_or_restore(club: dict[str, Any]) -> None:
    for fn, key in ((withdraw, "T5"), (restore, "T10")):
        with pytest.raises(read.NotFound):
            fn(club["conn"], ref(club, key), club["p"]["rekha"], now=NOW)
    with pytest.raises(Refused) as exc:
        restore(club["conn"], ref(club, "T7"), club["p"]["tanvi"], now=NOW)
    assert exc.value.code == "not_withdrawn"


# --- S-07: My ideas ------------------------------------------------------------------------------------------------


def mine(club: dict[str, Any], who: str, **params: Any) -> dict[str, Any]:
    return my_ideas(club["conn"], club["p"][who], params, now=NOW)


def test_p_routes_state_j_browse_3_dec_110_my_ideas_restores_tab_filter_sort_from_the_url_and_q_from_the_body(
    club: dict[str, Any],
) -> None:
    r2 = ref(club, "R2")
    out = mine(club, "tanvi", list="teamed", filter="with_review_desk", sort="stage", q="debit", row=r2)
    assert out["state"] == {
        "list": "teamed",
        "filter": "with_review_desk",
        "sort": "stage",
        "q": "debit",
        "row": r2,
    }
    # DEC-110: the search is in the state, never in the canonical query or any link built from it
    assert out["query"] == f"list=teamed&filter=with_review_desk&sort=stage&row={r2}"
    assert out["url"] == f"/my-ideas?{out['query']}"
    links = (
        [t["to"] for t in out["tabs"]] + [f["to"] for f in out["filters"]] + [s["to"] for s in out["sorts"]]
    )
    links += [out["sort_cycle"]["to"], out["copy_link"]["url"], out["search"]["clear"]["to"]]
    assert not [link for link in links if "debit" in link or "q=" in link]
    assert [i["id"] for i in out["items"]] == [r2]
    assert out["arrival"] == {"line": "Back where you were: Teamed up.", "row": r2}
    # The row's link carries this exact view back (J-BROWSE/2 and /3), the opened row included.
    href = out["items"][0]["href"]
    assert href.startswith(f"/ideas/{r2}?from=my-ideas&back=")
    back = parse_qs(urlsplit(href).query)["back"][0]
    assert back == out["url"] and "debit" not in href
    assert [t["selected"] for t in out["tabs"]] == [False, True]
    assert [f["filter"] for f in out["filters"] if f["selected"]] == ["with_review_desk"]
    assert [s["sort"] for s in out["sorts"] if s["selected"]] == ["stage"]
    # A filter the opened row is not in shows nothing to come back to, and says nothing about arriving.
    elsewhere = mine(club, "tanvi", list="teamed", filter="shipped", q="debit", row=r2)
    assert elsewhere["items"] == [] and "arrival" not in elsewhere
    # Unknown values fall back to the defaults; defaults are left out of the canonical URL.
    plain = mine(club, "tanvi", list="nope", filter="nope", sort="nope")
    assert plain["query"] == "" and plain["url"] == "/my-ideas"


def test_s07_filters_counts_per_filter_and_per_list(club: dict[str, Any]) -> None:
    out = mine(club, "tanvi")
    assert out["counts"] == {
        "all": 10,
        "needs_you": 1,
        "drafts": 3,
        "with_review_desk": 2,
        "picked_and_building": 2,
        "shipped": 0,
        "closed": 3,
    }
    assert out["lists"] == {"yours": 10, "teamed": 2}
    needs = mine(club, "tanvi", filter="needs_you")
    assert needs["lists"] == {"yours": 1, "teamed": 0} and [i["ref"] for i in needs["items"]] == [
        ref(club, "T6")
    ]


def test_s07_rows_next_step_and_action_per_status(club: dict[str, Any]) -> None:
    rows = {i["id"]: i for i in mine(club, "tanvi")["items"]}
    t6 = rows[ref(club, "T6")]
    assert t6["pill"]["label"] == "Needs you"
    assert t6["next_step"]["sentence"] == "The review desk asked you 3 questions on Friday."
    # S-07.phone (PhoneMyIdeas.md) names who asked; DEC-111: only to the review desk and the Ones Committee, so the
    # sharer's phone says the desktop's sentence (test_s07_dec111_…)
    assert "phone_sentence" not in t6["next_step"]
    assert t6["next_step"]["action"]["label"] == "Answer the questions"
    assert t6["next_step"]["action"]["to"] == f"/ideas/{ref(club, 'T6')}/answer"
    assert (
        t6["next_step"]["action"]["accessible_name"]
        == "Answer the questions: PAN mismatch holds new folios for days"
    )
    assert t6["track"]["label"] == "2 of 5 stages done. Now: reviewed"
    t10 = rows[ref(club, "T10")]
    assert t10["next_step"]["action"]["label"] == "Restore it" and t10["next_step"]["sentence"].startswith(
        "Withdrawn on "
    )
    t9 = rows[ref(club, "T9")]
    assert t9["meta"].startswith(f"{ref(club, 'T9')}, Picked by the Ones Committee, ")
    assert t9["next_step"]["sentence"].startswith(
        "The committee reversed the review desk’s not picked: We can ask"
    )
    assert t9["next_step"]["action"]["label"] == "Read the decision"
    draft = rows[club["m"]["T2"].uuid]
    assert draft["pill"]["label"] == "Draft" and draft["track"] is None
    assert draft["next_step"]["action"] == {
        "label": "Carry on",
        "to": f"/share/{club['m']['T2'].uuid}",
        "style": "line",
        "accessible_name": "Carry on: SIP failure SMS gives no reason",
    }
    assert draft["next_step"]["sentence"].startswith("Waiting for Rekha")  # its merge request waits on Rekha
    assert club["m"]["T3"].uuid not in rows  # archived: only under Drafts


def test_s07_dec111_my_ideas_names_the_review_desk_not_the_reviewer(club: dict[str, Any]) -> None:
    """DEC-111 (J-BROWSE/1-4; BLD-E053): S-07's rows never name the reviewer to a sharer outside the review desk and
    the Ones Committee: no phone sentence naming who asked, and "The review desk has your answers. It decides by …"
    once the answers are in. A sharer on the desk or the committee still reads the name in both."""
    conn, t6 = club["conn"], ref(club, "T6")

    def t6_row() -> tuple[dict[str, Any], dict[str, Any]]:
        out = mine(club, "tanvi")
        return out, next(i for i in out["items"] if i["id"] == t6)

    out, row = t6_row()
    assert no_reviewer_named(out, club)
    assert row["next_step"]["sentence"] == "The review desk asked you 3 questions on Friday."
    assert "phone_sentence" not in row["next_step"]
    for role in ("committee", "reviewer"):
        grant(club, "tanvi", role)
        _, row = t6_row()
        assert (
            row["next_step"]["phone_sentence"]
            == "Harish from the review desk asked you 3 questions on Friday."
        )
        revoke_all(club, "tanvi")

    conn.execute("UPDATE question_sets SET state = 'answered' WHERE idea_uuid = %s", (club["m"]["T6"].uuid,))
    conn.execute("UPDATE ideas SET status = 'with_review_desk' WHERE idea_id = %s", (t6,))
    by = day(
        conn.execute("SELECT decide_by FROM ideas WHERE idea_id = %s", (t6,)).fetchone()["decide_by"], NOW
    )
    out, row = t6_row()
    assert no_reviewer_named(out, club)
    assert row["next_step"]["sentence"] == f"The review desk has your answers. It decides by {by}."
    for role in ("committee", "reviewer"):
        grant(club, "tanvi", role)
        _, row = t6_row()
        assert row["next_step"]["sentence"] == f"Harish has your answers. The review desk decides by {by}."
        revoke_all(club, "tanvi")


def test_l_draft_autosave_8_archived_drafts_are_listed_under_drafts(club: dict[str, Any]) -> None:
    rows = {i["id"]: i for i in mine(club, "tanvi", filter="drafts")["items"]}
    t3 = rows[club["m"]["T3"].uuid]
    assert t3["archived"] is True and t3["meta"].startswith("Archived ")
    assert (
        t3["next_step"]["action"]["label"] == "Restore it"
        and t3["next_step"]["action"]["op"] == "draft.restore"
    )


def test_s07_teamed_up_rows_read_as_everyone_sees_them(club: dict[str, Any]) -> None:
    rows = {i["id"]: i for i in mine(club, "tanvi", list="teamed")["items"]}
    v1 = rows[ref(club, "V1")]
    assert v1["meta"].startswith("Varun Chopra’s idea, you teamed up ") and v1["meta"].endswith(
        ref(club, "V1")
    )
    assert v1["next_step"]["action"]["label"] == "See the result"
    r2 = rows[ref(club, "R2")]
    assert r2["next_step"]["sentence"].endswith("You’ll get a note either way.")


def test_s07_search_matches_title_summary_and_reference(club: dict[str, Any]) -> None:
    out = mine(club, "tanvi", q="SIP")
    assert out["search"]["sentence"].startswith("Found ") and "Closest: “" in out["search"]["sentence"]
    assert out["search"]["matched_on"] == ["title", "summary", "reference"]
    assert {i["id"] for i in out["items"]} >= {club["m"]["T2"].uuid, ref(club, "T11")}
    by_ref = mine(club, "tanvi", q=ref(club, "T7"))
    assert [i["id"] for i in by_ref["items"]] == [ref(club, "T7")]
    none = mine(club, "tanvi", q="nothing like this")
    assert none["empty"]["kind"] == "no_results" and none["total"] == 0


def test_s07_search_rows_carry_a_snippet_of_the_summary(club: dict[str, Any]) -> None:
    out = mine(club, "tanvi", q=ref(club, "T7"))
    row = out["items"][0]
    summary = club["m"]["T7"].spec.summary
    assert row["snippet"] == snippet(summary) and len(row["snippet"]) <= 97
    assert "snippet" not in mine(club, "tanvi")["items"][0]
    assert out["search"]["clear"]["to"] == "/my-ideas"


def test_s07_phone_sort_cycler_copy_link_and_short_filter_label(club: dict[str, Any]) -> None:
    out = mine(club, "tanvi", sort="stage", filter="with_review_desk", row="x")
    assert out["sort_cycle"] == {
        "label": "Sorted by stage",
        "next": "latest",
        "to": "/my-ideas?filter=with_review_desk",
    }
    assert out["copy_link"]["url"] == "/my-ideas?filter=with_review_desk&sort=stage"
    chip = next(f for f in out["filters"] if f["filter"] == "with_review_desk")
    assert (
        chip["label"] == "With the review desk"
        and chip["short_label"] == "With the desk"
        and chip["selected"]
    )


def test_s07_states_empty_first_time_and_filtered(club: dict[str, Any]) -> None:
    first = mine(club, "kunal")
    assert first["empty"]["kind"] == "first_time" and first["empty"]["title"] == "Nothing shared yet"
    assert first["empty"]["actions"][0] == {
        "label": "Share your first problem",
        "to": "/share",
        "style": "primary",
    }
    shipped = mine(club, "tanvi", filter="shipped")
    assert shipped["empty"]["title"] == "Nothing shipped yet."
    assert [a["label"] for a in shipped["empty"]["actions"]] == ["See 1 in Teamed up", "Show all ideas"]
    # S-07.phone: the phone says "impact" where the desktop says "effect", and offers "Show all ideas" alone
    assert shipped["empty"]["line"] == "Ideas land here once they ship and their effect is measured."
    assert shipped["empty"]["phone_line"] == "Ideas land here once they ship and their impact is measured."
    assert [a["label"] for a in shipped["empty"]["actions"] if not a.get("desk_only")] == ["Show all ideas"]
    closed = mine(club, "tanvi", list="teamed", filter="closed")["empty"]
    assert "phone_line" not in closed
    desk = mine(club, "tanvi", list="teamed", filter="with_review_desk")
    assert desk["total"] == 1  # R2


def test_j_browse_6_a_shared_link_shows_only_what_that_person_may_see(club: dict[str, Any]) -> None:
    tanvis = {i["id"] for i in mine(club, "tanvi", filter="closed")["items"]}
    rekhas = {i["id"] for i in mine(club, "rekha", filter="closed")["items"]}
    assert tanvis and not tanvis & rekhas


# --- DEC-104: a lead who hid their name, or has left, is never named outside the crew, desk and committee ---------


def leave(club: dict[str, Any], who: str) -> None:
    """The person has left KFintech (`users.active = false`). The seed's people are removed after each test, so the
    flag goes with them."""
    club["conn"].execute("UPDATE users SET active = false WHERE id = %s", (club["p"][who],))


GONE = {"hid_their_name": hide_name, "has_left": leave}


@pytest.mark.parametrize("how", sorted(GONE))
def test_dec_104_s07_a_draft_waiting_on_a_lead_who_hid_their_name_or_left_says_the_lead(
    club: dict[str, Any], how: str
) -> None:
    """DEC-104, S-07 Drafts, J-SIMILAR/4, J-BROWSE/4 (BLD-E048): T2 is Tanvi's draft with a merge request waiting
    on Rekha, R1's lead. Tanvi is not on R1's crew, so Rekha is named only while she shows her name on the Wall
    and is still here."""
    r1, t2 = ref(club, "R1"), club["m"]["T2"].uuid
    before = {i["id"]: i for i in mine(club, "tanvi", filter="drafts")["items"]}[t2]
    assert (
        before["next_step"]["sentence"]
        == f"Waiting for Rekha to answer about joining {r1}. Your words are kept."
    )
    GONE[how](club, "rekha")
    drafts = mine(club, "tanvi", filter="drafts")
    row = {i["id"]: i for i in drafts["items"]}[t2]
    assert row["next_step"]["sentence"] == (
        f"Waiting for the lead to answer about joining {r1}. Your words are kept."
    )
    assert "Rekha" not in json.dumps(drafts, ensure_ascii=False, default=str)
    all_rows = {i["id"]: i for i in mine(club, "tanvi")["items"]}
    assert all_rows[t2]["next_step"]["sentence"].startswith("Waiting for the lead to answer")


def test_s07_drafts_l_teamup_rules_10_a_draft_waits_on_the_live_crew_lead_not_the_sharer(
    club: dict[str, Any],
) -> None:
    """S-07 Drafts, L-TEAMUP.rules/10, DEC-104: Rekha shared R1 and hands its lead to Zoya, already on its crew. Tanvi's
    T2 draft, whose merge request waits on R1, now waits on Zoya (lane F's `teamup.store.lead_code`), and Rekha is not
    named. Zoya is named only while she shows her name on the Wall and is still here."""
    conn, r1, t2 = club["conn"], ref(club, "R1"), club["m"]["T2"].uuid
    r1_uuid = club["m"]["R1"].uuid
    conn.execute(
        "UPDATE crew_members SET role = 'crew' WHERE idea_uuid = %s AND contributor_code = %s AND left_at IS NULL",
        (r1_uuid, code_of(club, "rekha")),
    )
    conn.execute(
        "UPDATE crew_members SET role = 'lead' WHERE idea_uuid = %s AND contributor_code = %s AND left_at IS NULL",
        (r1_uuid, code_of(club, "zoya")),
    )
    drafts = mine(club, "tanvi", filter="drafts")
    row = {i["id"]: i for i in drafts["items"]}[t2]
    names = f"Waiting for Zoya to answer about joining {r1}. Your words are kept."
    assert row["next_step"]["sentence"] == names
    assert "Rekha" not in json.dumps(drafts, ensure_ascii=False, default=str)
    hide_name(club, "zoya")
    drafts = mine(club, "tanvi", filter="drafts")
    row = {i["id"]: i for i in drafts["items"]}[t2]
    waits = f"Waiting for the lead to answer about joining {r1}. Your words are kept."
    assert row["next_step"]["sentence"] == waits
    dump = json.dumps(drafts, ensure_ascii=False, default=str)
    assert "Zoya" not in dump and "Rekha" not in dump


def test_dec_104_s09_a_sharer_who_has_left_is_never_named_to_a_colleague(club: dict[str, Any]) -> None:
    """DEC-104, S-09.layout/2 and /6 (BLD-E048): once Rekha has left, a colleague reads R1 as the Wall shows it, with
    no name in the shared line, the note, the crew, the faces or the Team up card; one who asked to join waits for
    "the lead"."""
    r1 = ref(club, "R1")
    leave(club, "rekha")
    v = view(club, r1, "pallavi")
    page = v["page"]
    assert v["idea"]["sharer"] is None and v["idea"]["crew"]["lead"] is None
    assert "Rekha" not in page["shared_line"] and page["shared_line"].startswith("Shared ")
    assert "The sharer’s own words stay with them" in page["summary_note"]
    assert page["team_up"]["count_line"].startswith("2 colleagues on it. The person who shared it leads it")
    assert "Send the lead a note about what you bring." in page["team_up"]["line"]
    assert [f["first_name"] for f in page["team_up"]["faces"]] == ["Zoya"]
    assert "Rekha" not in json.dumps(v, ensure_ascii=False, default=str)
    sent = view(club, r1, "bhavesh")
    assert sent["page"]["team_up"]["heading"] == "Waiting for the lead"
    assert (
        sent["page"]["team_up"]["line"] == "The lead reads your note and decides. You’ll hear in your Inbox."
    )
    assert "Rekha" not in json.dumps(sent, ensure_ascii=False, default=str)


def test_dec_104_s06_similar_tiles_and_the_merged_line_never_name_a_lead_who_has_left(
    club: dict[str, Any],
) -> None:
    """DEC-104, S-06 'Colleagues on something similar' (C-SIMGRID) and S-06.rules/4 (BLD-E048): Tanvi's T5 lists
    Pallavi's P1 as similar, and T11 was merged into R2 by Rekha as its lead. Once Pallavi has left, P1's tile has no
    lead and no face for her; once Rekha has left, the merged line says "by its lead"."""
    conn, t5, t11, p1 = club["conn"], ref(club, "T5"), ref(club, "T11"), ref(club, "P1")
    conn.execute(
        "UPDATE merges SET via = 'lead_accepted', by_code = %s, by_user_id = NULL WHERE merged_idea_uuid = %s",
        (code_of(club, "rekha"), club["m"]["T11"].uuid),
    )

    def tile() -> dict[str, Any]:
        tiles = view(club, t5, "tanvi")["page"]["similar"]["tiles"]
        return dict(next(t for t in tiles if t["idea"]["id"] == p1))

    assert tile()["idea"]["lead"]["first_name"] == "Pallavi"
    leave(club, "pallavi")
    t = tile()
    assert t["idea"]["lead"] is None and t["idea"]["crew_faces"] == [] and t["idea"]["crew_count"] == 1
    assert "Pallavi" not in json.dumps(t, ensure_ascii=False, default=str)
    assert view(club, t11, "tanvi")["page"]["merged"]["line"] == f"Merged into {ref(club, 'R2')} by Rekha"
    leave(club, "rekha")
    merged = view(club, t11, "tanvi")["page"]["merged"]
    assert merged["line"] == f"Merged into {ref(club, 'R2')} by its lead"
    assert "Rekha" not in json.dumps(merged, ensure_ascii=False)


# --- Lane G's 13:00 walk (run 44273019908): S-06's similar tiles, an empty part, and Teams while it is off ----------


def test_s06_rules_4_c_simgrid_tile_j_similar_7_j_review_m3_no_tile_for_where_it_went_no_team_up_on_your_crew(
    club: dict[str, Any],
) -> None:
    """S-06.rules/4, C-SIMGRID.tile (BLD-E056; J-SIMILAR/7, J-REVIEW/M3): T11 was merged into R2 by the review desk,
    and Tanvi is on R2's crew. T11's "Colleagues on something similar" has no tile for R2 (its card and merged block
    link there already). On any other page, a tile for an idea whose crew she is in offers Preview only, with "On
    the crew" where Team up would be; once she leaves that crew, Team up is back."""
    conn, m = club["conn"], club["m"]
    t11, r2 = ref(club, "T11"), ref(club, "R2")
    page = view(club, t11, "tanvi")["page"]
    assert page["merged"]["to"] == r2
    assert r2 not in [t["idea"]["id"] for t in page["similar"]["tiles"]]
    # The tile is gone only for where it went: undo the merge and R2 is back, with the crew she is on
    conn.execute("UPDATE merges SET reversed_at = now() WHERE merged_idea_uuid = %s", (m["T11"].uuid,))
    tiles = view(club, t11, "tanvi")["page"]["similar"]["tiles"]
    tile = next(t for t in tiles if t["idea"]["id"] == r2)
    assert tile["my_state"] == "on_crew" and tile["done_line"] == "On the crew"
    assert [a["op"] for a in tile["actions"]] == ["preview"]

    # T5 lists P1; Tanvi is not on P1's crew, so it offers Team up and no "On the crew"
    def p1_tile() -> dict[str, Any]:
        tiles = view(club, ref(club, "T5"), "tanvi")["page"]["similar"]["tiles"]
        return dict(next(t for t in tiles if t["idea"]["id"] == ref(club, "P1")))

    t5_tile = p1_tile()
    assert [a["op"] for a in t5_tile["actions"]] == ["preview", "team_up"] and "done_line" not in t5_tile
    # On P1's crew, it does not; left the crew, it does again
    conn.execute(
        "INSERT INTO crew_members (idea_uuid, contributor_code, role, via) VALUES (%s, %s, 'crew', 'teamup')",
        (m["P1"].uuid, code_of(club, "tanvi")),
    )
    t5_tile = p1_tile()
    assert [a["op"] for a in t5_tile["actions"]] == ["preview"] and t5_tile["done_line"] == "On the crew"
    conn.execute(
        "UPDATE crew_members SET left_at = now(), left_how = 'left' WHERE idea_uuid = %s AND contributor_code = %s",
        (m["P1"].uuid, code_of(club, "tanvi")),
    )
    assert [a["op"] for a in p1_tile()["actions"]] == ["preview", "team_up"]


def test_s06_c_simgrid_tile_l_teamup_rules_1_j_share_12_a_closed_idea_offers_no_team_up(
    club: dict[str, Any],
) -> None:
    """C-SIMGRID.tile, L-TEAMUP.rules/1 (BLD-E063; J-SHARE/12): a tile offers Team up only where lane F's
    `POST /ideas/:id/team-up` would take the ask. T5 lists P1 (shared, open) and, here, Geetanjali's G1 (Not now):
    P1 offers Preview and Team up; G1 offers Preview alone, with no "On the crew" line, and lane F refuses the ask
    with `idea_closed`. Not picked is closed too; back with the desk, Team up returns."""
    from teamup import requests as teamup_requests
    from teamup.store import Refused as TeamUpRefused

    conn, m = club["conn"], club["m"]
    t5, p1, g1 = ref(club, "T5"), ref(club, "P1"), ref(club, "G1")
    conn.execute(
        "INSERT INTO similar_links (idea_uuid, other_idea_uuid, strength, reason) VALUES (%s, %s, 'related', %s)",
        (m["T5"].uuid, m["G1"].uuid, "Related: papers investors ask for"),
    )

    def tiles() -> dict[str, dict[str, Any]]:
        return {t["idea"]["id"]: t for t in view(club, t5, "tanvi")["page"]["similar"]["tiles"]}

    got = tiles()
    assert got[g1]["pill"]["label"] == "Not now"
    assert [a["op"] for a in got[g1]["actions"]] == ["preview"] and "done_line" not in got[g1]
    assert got[g1]["my_state"] == "none"
    assert [a["op"] for a in got[p1]["actions"]] == ["preview", "team_up"] and "done_line" not in got[p1]
    # The tile agrees with lane F: the ask on G1 is refused as closed, and lane F's own read says so
    with pytest.raises(TeamUpRefused) as refused:
        teamup_requests.send(
            conn, g1, club["p"]["tanvi"], {"note": "I see the same with statements at my branch."}
        )
    assert (refused.value.status, refused.value.code) == (409, "idea_closed")
    assert teamup_requests.my_state(conn, p1, club["p"]["tanvi"])["can_request"] is True
    # Not picked is closed as well; back with the review desk, it is open again
    conn.execute("UPDATE ideas SET status = 'not_picked' WHERE id = %s", (m["G1"].uuid,))
    assert [a["op"] for a in tiles()[g1]["actions"]] == ["preview"]
    conn.execute("UPDATE ideas SET status = 'with_review_desk' WHERE id = %s", (m["G1"].uuid,))
    assert [a["op"] for a in tiles()[g1]["actions"]] == ["preview", "team_up"]


def test_s06_layout_5_j_review_1_j_track_7_an_empty_how_often_reads_not_given(club: dict[str, Any]) -> None:
    """S-06.layout/5 (BLD-E057; J-REVIEW/1, /3, /6, J-TRACK/7): a part the sharer left empty, or wrote only spaces
    in, reads "Not given.", as S-R2 reads it, never a blank row. A part with words has no empty line."""
    conn, k1 = club["conn"], ref(club, "K1")  # Kiran's K1: How often left empty
    rows = {r["part"]: r for r in view(club, k1, "kiran")["page"]["shared"]["rows"]}
    assert rows["often"]["value"] == "" and rows["often"]["empty_line"] == "Not given."
    assert rows["who"]["value"] and "empty_line" not in rows["who"]
    conn.execute("UPDATE ideas SET affects = '{}' WHERE idea_id = %s", (k1,))
    rows = {r["part"]: r for r in view(club, k1, "kiran")["page"]["shared"]["rows"]}
    assert rows["who"]["empty_line"] == "Not given."
    conn.execute("UPDATE ideas SET often = '   ', affects = ARRAY['  ', ' '] WHERE idea_id = %s", (k1,))
    rows = {r["part"]: r for r in view(club, k1, "kiran")["page"]["shared"]["rows"]}
    for part in ("often", "who"):
        assert rows[part]["value"] == "" and rows[part]["empty_line"] == "Not given.", part
    t5 = {r["part"]: r for r in view(club, ref(club, "T5"), "tanvi")["page"]["shared"]["rows"]}
    assert t5["often"]["value"] and "empty_line" not in t5["often"]


def test_bld_e054_dec_105_s06_names_teams_only_while_its_switch_is_on(club: dict[str, Any]) -> None:
    """BLD-E054, DEC-105 (S-06.layout/4, /8, S-06.states "Just shared", "Answers sent"): Teams is built but off until
    IT approves it. With `comms.teams` on, S-06 says the drawn words; off, each sentence names only email."""
    conn, t5, t6 = club["conn"], ref(club, "T5"), ref(club, "T6")
    conn.execute("UPDATE question_sets SET state = 'answered' WHERE idea_uuid = %s", (club["m"]["T6"].uuid,))

    def lines() -> dict[str, str]:
        just = view(club, t5, "tanvi")["page"]
        sent = view(club, t6, "tanvi")["page"]
        assert just["state"] == "just_shared" and sent["state"] == "answers_sent"
        return {
            "window": just["window"]["line"].split(". ", 2)[-1],
            "rest": just["card"]["rest"],
            "phone_rest": just["card"]["phone_rest"],
            "empty": just["conversation"]["empty_line"],
            "phone_empty": just["conversation"].get("phone_empty_line"),
            "sent": sent["card"]["rest"].split(", and you hear in your ")[-1],
        }

    killswitch.clear_cache()
    assert killswitch.is_on("comms.teams", conn)  # the test database starts with every switch on
    assert lines() == {
        "window": "We tell you on Teams and by email when anything moves.",
        "rest": "We’ll tell you on Teams and by email when anything changes.",
        "phone_rest": "We’ll tell you on Teams and by email.",
        "empty": "No messages yet. If the review desk has a question, it shows up here and in your Inbox, and we "
        "tell you on Teams.",
        "phone_empty": "No messages yet. If the review desk has a question, it shows up here and in your Inbox.",
        "sent": "Inbox, on Teams and by email.",
    }
    conn.execute("UPDATE kill_switches SET state = 'off' WHERE name = 'comms.teams'")
    killswitch.clear_cache()
    off = lines()
    assert off == {
        "window": "We tell you by email when anything moves.",
        "rest": "We’ll tell you by email when anything changes.",
        "phone_rest": "We’ll tell you by email.",
        "empty": "No messages yet. If the review desk has a question, it shows up here and in your Inbox.",
        "phone_empty": None,  # the phone's line is the same one: sent once, so the page says it once
        "sent": "Inbox and by email.",
    }
    pages = [view(club, t5, "tanvi"), view(club, t6, "tanvi")]
    assert "Teams" not in json.dumps(pages, ensure_ascii=False, default=str)
