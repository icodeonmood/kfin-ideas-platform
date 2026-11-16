"""L-DECIDE checks and dates, and the reversal checks, without a database (V-ACC.review/9, V-ACC.committee/6)."""

from __future__ import annotations

import datetime as dt

from desk import clock, decide, when
from desk.promises import DEFAULTS as P

IST = when.IST
CAL = clock.Calendar()


def at(y: int, m: int, d: int, h: int = 0, mi: int = 0) -> dt.datetime:
    return dt.datetime(y, m, d, h, mi, tzinfo=IST)


DECIDED = at(2026, 11, 16, 16, 58)  # "Today, 4:58 pm. She has it now."


def test_V_ACC_review_9_a_decision_needs_a_choice_and_a_reason_of_a_line() -> None:
    errors = decide.check_decision(None, "too short", None, "Kavya", P)
    assert [(e.code, e.field, e.message) for e in errors] == [
        ("choice_required", "choice", "Choose Pick, Not now or Not picked first."),
        ("reason_too_short", "reason", "Give Kavya a reason of at least a line, 30 characters or more."),
    ]
    assert (
        decide.check_decision("pick", "A clear problem, a real number and a simple fix.", None, "Kavya", P)
        == []
    )
    # spaces around the words do not count towards the 30
    assert decide.check_decision("pick", " " * 40 + "short", None, "Kavya", P)[0].code == "reason_too_short"


def test_V_ACC_committee_6_a_reversal_needs_a_new_decision_and_a_note() -> None:
    errors = decide.check_reversal("pick", "pick", "short", None, P)
    assert [(e.code, e.message) for e in errors] == [
        ("to_required", "Choose what to change it to."),
        ("note_too_short", "Write a note of at least a line, 30 characters or more."),
    ]
    assert (
        decide.check_reversal(
            "not_now", "pick", "Right problem; the new mandate rules land in March.", "3m", P
        )
        == []
    )


def test_L_DECIDE_rules_1_the_counter_and_the_reason_label_follow_the_choice() -> None:
    assert decide.counter("Twelve chars", "Kavya", P) == "12 of at least 30 characters"
    assert decide.counter("x" * 30, "Kavya", P) == "Kavya reads this word for word."
    assert decide.REASON_LABELS["not_now"] == "Why not now, and what would change it?"


def test_L_DECIDE_rules_4_words_a_sharer_never_reads_are_flagged_not_blocked() -> None:
    notes = decide.wording_check("This is a Duplicate of 1412 and was already solved last year.")
    assert [n.word for n in notes] == ["Duplicate", "already solved"]
    assert decide.wording_check("Plain words for the redemption messages.") == []


def test_L_DECIDE_rules_6_and_7_dates_a_decision_sets() -> None:
    d = decide.dates_for("not_now", DECIDED, None, P, CAL)
    assert d.return_at == at(2027, 2, 16, 16, 58) and d.team_by is None
    assert decide.return_words(d.return_at, "Kavya", DECIDED) == (  # type: ignore[arg-type]
        "Comes back to you and Kavya on Tuesday 16 February 2027"
    )
    assert decide.dates_for("not_now", DECIDED, "1m", P, CAL).return_at == at(2026, 12, 16, 16, 58)
    assert decide.dates_for("pick", DECIDED, None, P, CAL).team_by == at(2026, 11, 27, 18)
    assert decide.dates_for("not_picked", DECIDED, None, P, CAL) == decide.DecisionDates(None, None)
