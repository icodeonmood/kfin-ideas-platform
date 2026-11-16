"""L-QUESTIONS without a database: parts, guessing the part, suggestions, checks, set states and the words the desk,
the panel and the Answer screen show (V-FIELDS.review/1–3, V-FIELDS.answer/1–2, S-R1.layout/4)."""

from __future__ import annotations

import datetime as dt

import pytest

from desk import questions as q
from desk.promises import DEFAULTS as P
from desk.questions import SetFacts

IST = q.when.IST


def at(d: int, h: int = 0, mi: int = 0) -> dt.datetime:
    return dt.datetime(2026, 11, d, h, mi, tzinfo=IST)


NOW = at(16, 13, 20)
SENT, SEEN, DUE = at(16, 11, 20), at(16, 12, 5), at(19, 18)


@pytest.mark.parametrize(
    ("text", "part"),
    [
        ("Is it mostly R07, or all rejection codes?", "summary"),
        ("Is the 40 calls a day at one branch, or across Hyderabad?", "often"),
        ("Can you add a screenshot of the SMS, with the folio hidden?", "evidence"),
        ("Which customers or teams are hit hardest?", "who"),
        ("Roughly how long does one case take your team?", "cost"),
        ("Have you seen this solved anywhere, in KFin or outside?", "fix"),
        ("", "summary"),
    ],
)
def test_L_QUESTIONS_ask_2_the_part_is_guessed_from_the_wording(text: str, part: str) -> None:
    assert q.guess_part(text) == part


def test_L_QUESTIONS_ask_3_suggestions_start_with_the_ideas_gaps() -> None:
    filled = {"summary": True, "often": True, "who": True, "cost": False, "evidence": False, "fix": False}
    got = q.suggestions(filled)
    assert [(s.part, s.gap) for s in got[:2]] == [("cost", True), ("evidence", True)]
    assert [s.part for s in got] == ["cost", "evidence", "summary", "often", "who", "fix"]
    # nothing already queued is suggested again
    asked = ["Can you give one recent example, with the date?"]
    assert "summary" not in [s.part for s in q.suggestions(filled, asked)]


def test_S_R2_rules_2_ask_about_this_queues_that_parts_first_suggestion() -> None:
    full = dict.fromkeys(q.PARTS, True)
    s = q.first_for("often", full)
    assert s is not None and s.text == "Is it getting worse, better or about the same?"
    assert q.first_for("often", full, [s.text]) is None


def test_V_FIELDS_review_1_and_2_a_set_needs_questions_with_text_and_a_part() -> None:
    assert [e.code for e in q.check_set([], "3d", P)] == ["no_questions"]
    errors = q.check_set([{"text": " ", "part": "often"}, {"text": "x" * 301, "part": "nowhere"}], "2w", P)
    assert [e.code for e in errors] == [
        "question_empty", "question_too_long", "part_required", "time_to_answer_invalid"
    ]  # fmt: skip
    assert q.check_set([{"text": "Is it mostly R07?", "part": "summary"}], None, P) == []


def test_V_FIELDS_answer_1_answers_are_optional_up_to_2000_characters() -> None:
    assert q.check_answer(None, P) == [] and q.check_answer("x" * 2000, P) == []
    assert q.check_answer("x" * 2001, P)[0].message == "Keep your answer under 2,000 characters."


def test_L_QUESTIONS_states_follow_the_set() -> None:
    assert q.state(SetFacts(3, 0, None, None, None, None)) == "queued"
    assert q.state(SetFacts(3, 0, SENT, None, DUE, None)) == "sent"
    assert q.state(SetFacts(3, 0, SENT, SEEN, DUE, None)) == "seen"
    assert q.state(SetFacts(3, 1, SENT, SEEN, DUE, None)) == "partly_answered"
    assert q.state(SetFacts(3, 3, SENT, SEEN, DUE, at(16, 16, 32))) == "answered"
    assert q.state(SetFacts(3, 1, SENT, SEEN, DUE, None, closed=True)) == "closed"
    late = SetFacts(3, 1, SENT, SEEN, at(16, 8), None)
    assert q.overdue(late, NOW) and not q.overdue(SetFacts(3, 3, SENT, SEEN, at(16, 8), NOW), NOW)


def test_S_R1_layout_4_the_desks_questions_column() -> None:
    assert q.desk_line(None, NOW) == "No questions asked"
    assert q.desk_line(SetFacts(3, 0, SENT, None, DUE, None), NOW) == "Not seen yet"
    assert q.desk_line(SetFacts(3, 0, SENT, SEEN, DUE, None), NOW) == "0 of 3 answered, seen 12:05 pm"
    assert q.desk_line(SetFacts(2, 1, SENT, SEEN, DUE, None), NOW) == "1 of 2 answered"
    assert q.desk_line(SetFacts(2, 2, SENT, SEEN, DUE, at(16, 12, 20)), NOW) == "Both answered, 1 hour ago"
    assert q.desk_line(SetFacts(1, 1, SENT, SEEN, DUE, at(15, 18, 10)), NOW) == "Answered yesterday, 6:10 pm"
    assert (
        q.desk_line(SetFacts(1, 1, SENT, SEEN, DUE, NOW, closed=True), NOW, decided=True)
        == "1 question, answered"
    )
    assert (
        q.desk_line(SetFacts(2, 2, SENT, SEEN, DUE, NOW, closed=True), NOW, decided=True) == "Both answered"
    )


def test_S_R2_panel_2_words_while_asking() -> None:
    assert q.ready_line(2) == "2 questions ready" and q.ready_line(1) == "1 question ready"
    assert q.send_label(3, "Kavya") == "Send 3 questions to Kavya"
    assert q.deadline_line("Kavya", DUE, NOW) == "Kavya has until Thursday 19 November, 6 pm."
    assert q.AFTER_DECIDE_BY == "That’s after you decide, so you’d need to move your date."


def test_S_R2_panel_4_answered_with_time_to_spare() -> None:
    assert q.spare_line(at(16, 16, 32), DUE) == "Answered with 3 days to spare"
    assert q.spare_line(at(19, 13), DUE) == "Answered with 5 hours to spare"
    assert q.spare_line(at(19, 20), DUE) == "Answered 2 hours after the deadline"


def test_V_FIELDS_answer_2_sending_needs_one_answer() -> None:
    assert q.send_answers_label(0, "Meera") == "Answer at least one question"
    assert q.send_answers_label(1, "Meera") == "Send 1 answer to Meera"
    assert q.send_answers_label(3, "Meera") == "Send 3 answers to Meera"
