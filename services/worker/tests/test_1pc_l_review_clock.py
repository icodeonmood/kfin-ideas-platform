"""L-REVIEW.clock and L-QUESTIONS.clock: deadlines, countdowns and the date words the review side shows.

Pure functions: no database, no stack. Dates are the boards' week (Saturday 14 to Monday 16 November 2026).
"""

from __future__ import annotations

import datetime as dt

import pytest

from desk import clock, when
from desk.promises import DEFAULTS

IST = when.IST
CAL = clock.Calendar(holidays=frozenset({dt.date(2026, 12, 25)}))


def at(y: int, m: int, d: int, h: int = 0, mi: int = 0, s: int = 0) -> dt.datetime:
    return dt.datetime(y, m, d, h, mi, s, tzinfo=IST)


NOW = at(2026, 11, 16, 11, 20)  # Monday, when Meera sends her questions


def test_L_REVIEW_clock_1_a_saturday_share_is_decided_by_friday() -> None:
    assert clock.decide_by(at(2026, 11, 14, 10), DEFAULTS, CAL) == at(2026, 11, 20, 18)


def test_L_REVIEW_clock_1_a_weekday_share_counts_its_own_day() -> None:
    assert clock.decide_by(at(2026, 11, 16, 9), DEFAULTS, CAL) == at(2026, 11, 20, 18)
    # after 6 pm the day is over: day 1 is the next working day
    assert clock.decide_by(at(2026, 11, 16, 19), DEFAULTS, CAL) == at(2026, 11, 23, 18)


def test_L_REVIEW_clock_1_holidays_do_not_count() -> None:
    assert clock.decide_by(at(2026, 12, 21, 9), DEFAULTS, CAL) == at(2026, 12, 28, 18)


def test_L_DECIDE_rules_6_team_chosen_ten_working_days_after_the_pick() -> None:
    assert clock.team_by(at(2026, 11, 16, 16, 58), DEFAULTS, CAL) == at(2026, 11, 27, 18)


@pytest.mark.parametrize(
    ("time_to_answer", "due"),
    [("3d", at(2026, 11, 19, 18)), ("1w", at(2026, 11, 23, 18)), ("1d", at(2026, 11, 17, 11, 20))],
)
def test_L_QUESTIONS_clock_5_deadlines(time_to_answer: str, due: dt.datetime) -> None:
    assert clock.answer_due(NOW, time_to_answer, DEFAULTS, CAL) == due


def test_L_QUESTIONS_clock_3_give_two_more_days_keeps_the_hour() -> None:
    assert clock.give_more_time(at(2026, 11, 19, 18), DEFAULTS) == at(2026, 11, 21, 18)


def test_L_QUESTIONS_clock_3_and_5_more_time_on_an_overdue_set_counts_from_now_to_a_working_day() -> None:
    due = at(2026, 11, 19, 18)
    assert clock.give_more_time(due, DEFAULTS, at(2026, 11, 19, 9)) == at(
        2026, 11, 21, 18
    )  # not yet due: as before
    late = at(2026, 11, 20, 10, 30)  # Friday: two days on is a Sunday, so the next working day, at 6 pm
    assert clock.give_more_time(due, DEFAULTS, late, CAL) == at(2026, 11, 23, 18)  # never left overdue
    # a working day two days on keeps that day, at the deadline hour (L-QUESTIONS.clock/5)
    assert clock.give_more_time(at(2026, 11, 17, 18), DEFAULTS, at(2026, 11, 18, 9), CAL) == at(
        2026, 11, 20, 18
    )


def test_L_QUESTIONS_clock_2_reminders_a_day_and_two_hours_before() -> None:
    due = clock.answer_due(NOW, "3d", DEFAULTS, CAL)
    assert clock.reminders(NOW, due, DEFAULTS) == [at(2026, 11, 18, 18), at(2026, 11, 19, 16)]
    # a 1-day set has no time for the day-before reminder
    due = clock.answer_due(NOW, "1d", DEFAULTS, CAL)
    assert clock.reminders(NOW, due, DEFAULTS) == [at(2026, 11, 17, 9, 20)]


def test_L_QUESTIONS_ask_4_a_deadline_after_decide_by_is_flagged() -> None:
    decide = at(2026, 11, 20, 18)
    assert clock.after_decide_by(clock.answer_due(NOW, "1w", DEFAULTS, CAL), decide)
    assert not clock.after_decide_by(clock.answer_due(NOW, "3d", DEFAULTS, CAL), decide)


@pytest.mark.parametrize(
    ("due", "suffix", "label", "variant"),
    [
        (at(2026, 11, 19, 18), "to answer", "3 days to answer", "normal"),
        (at(2026, 11, 17, 12, 0), "to answer", "1 day to answer", "normal"),
        (at(2026, 11, 16, 18, 58), "to answer", "07:38 to answer", "warn"),
        (at(2026, 11, 16, 11, 20, 30), "left", "00:01 left", "warn"),
        (at(2026, 11, 16, 6, 20), "to answer", "Overdue by 5 hours", "bad"),
        (at(2026, 11, 16, 11, 0), "to answer", "Overdue by 20 minutes", "bad"),
        (at(2026, 11, 14, 11, 0), "to decide", "Overdue by 2 days", "bad"),
        (at(2026, 11, 22, 18), "to decide", "6 days to decide", "normal"),
    ],
)
def test_S_R1_rules_2_countdowns(due: dt.datetime, suffix: str, label: str, variant: str) -> None:
    c = clock.countdown(due, NOW)
    assert (c.label(suffix), c.variant) == (label, variant)


def test_desk_dates_read_as_on_the_boards() -> None:
    assert when.day(at(2026, 11, 20, 18), NOW) == "Friday 20 November"
    assert when.day(at(2027, 2, 16), NOW) == "Tuesday 16 February 2027"
    assert when.short(at(2026, 11, 2, 15), NOW) == "2 November"
    assert when.day_time(at(2026, 11, 19, 18), NOW) == "Thursday 19 November, 6 pm"
    assert when.day_time(at(2026, 11, 16, 9, 50), NOW) == "Monday 16 November, 9:50 am"
    assert when.clock(at(2026, 11, 16, 12, 5)) == "12:05 pm"
    assert when.clock(at(2026, 11, 16, 0, 0)) == "12 am"
    assert when.deadline(at(2026, 11, 16, 19), NOW) == "7 pm today"
    assert when.deadline(at(2026, 11, 19, 18), NOW) == "Thursday 19 November, 6 pm"
    assert when.since(at(2026, 11, 16, 10, 15), NOW) == "1 hour ago"
    assert when.since(at(2026, 11, 16, 11, 19, 30), NOW) == "just now"
    assert when.since(at(2026, 11, 15, 18, 10), NOW) == "yesterday, 6:10 pm"
    assert when.since(at(2026, 11, 12, 9), NOW) == "Thursday 12 November"
    assert [when.times(n) for n in (1, 2, 3)] == ["once", "twice", "3 times"]


def test_times_without_a_zone_are_refused() -> None:
    with pytest.raises(ValueError, match="time zone"):
        when.day(dt.datetime(2026, 11, 16), NOW)


def test_promises_read_lane_a_rule_keys() -> None:
    """The adapter maps lane A's rules/promises.md (BLD-A181) onto lane B's names; codes stay in order."""
    from desk.promises import _from_rule

    p = _from_rule(
        DEFAULTS,
        {
            "review": {"decide_by_working_days": 4},
            "questions": {"answer_options_days": [1, 2, 5], "answer_default_days": 2, "deadline_hour": 17,
                          "reminder_hours_before": [12]},
            "notes": {"decision_reason_min_chars": 40, "reversal_note_min_chars": 35, "merge_note_min_chars": 25},
            "committee_window": {"days": 20, "extend_by_days": 15, "max_months": 2},
            "not_now": {"return_options_months": [2, 4, 8], "return_default_months": 4},
            "team_by": {"working_days": 8},
        },
    )  # fmt: skip
    assert p.answer_days == (("1d", 1), ("3d", 2), ("1w", 5)) and p.answer_default == "3d"
    assert (p.review_working_days, p.deadline_hour, p.reminders_before_hours) == (4, 17, (12,))
    assert (p.reason_min, p.reversal_note_min, p.merge_note_min) == (40, 35, 25)
    assert (p.window_days, p.window_extend_days, p.window_max_months) == (20, 15, 2)
    assert p.return_months == (("1m", 2), ("3m", 4), ("6m", 8)) and p.return_default == "3m"
    assert p.team_by_working_days == 8
    assert _from_rule(DEFAULTS, {}) == DEFAULTS


def test_S_R1_rules_2_the_shared_countdown_vectors_hold() -> None:
    """desk/countdown_vectors.json is what apps/web/src/lib/desk/countdown.ts is tested against too."""
    import json
    from pathlib import Path

    data = json.loads(Path(clock.__file__).with_name("countdown_vectors.json").read_text())
    for v in data["cases"]:
        c = clock.countdown(dt.datetime.fromisoformat(v["due"]), dt.datetime.fromisoformat(v["now"]))
        assert (c.count, c.variant) == (v["count"], v["variant"]), v
