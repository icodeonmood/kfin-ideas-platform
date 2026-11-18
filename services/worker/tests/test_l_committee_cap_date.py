"""L-COMMITTEE.rules/1-2 (BLD-B258): the committee's 3-month cap is the decision's own office date 3 months on.

Lane G's walk found a decision on Sunday 8 November that read "up to Sunday 7 February 2027": the seed stored the cap
as 91 days, and `add_months` worked on the date in the zone it was given, so a UTC time from the database just after
midnight in India could land on the wrong day. The cap is now added on the India calendar date at the same India
wall time, whatever zone the time comes in. Pure rules first; the seed's windows are checked against the database
last. Synthetic data only.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from desk import when
from desk.promises import DEFAULTS as P
from desk.window import WindowRefused, add_months, extend, open_window, words

IST = when.IST
UTC = dt.UTC


def ist(y: int, m: int, d: int, h: int = 0, mi: int = 0) -> dt.datetime:
    return dt.datetime(y, m, d, h, mi, tzinfo=IST)


SUNDAY_8_NOV = ist(2026, 11, 8, 0, 30)  # 00:30 IST is 19:00 UTC on Saturday 7 November


@pytest.mark.parametrize("decided", [SUNDAY_8_NOV, SUNDAY_8_NOV.astimezone(UTC)], ids=["ist", "utc"])
def test_L_COMMITTEE_rules_2_a_decision_at_8_nov_0030_ist_is_capped_at_8_feb_2027(
    decided: dt.datetime,
) -> None:
    """L-COMMITTEE.rules/2, J-COMMITTEE/2: "up to Monday 8 February 2027", whether the time comes as IST or UTC."""
    w = open_window(decided, P)
    assert w.max_closes_at == ist(2027, 2, 8, 0, 30)
    assert w.max_closes_at.tzinfo == decided.tzinfo  # back in the zone it came in
    assert words(w, decided, P).max_until == "Monday 8 February 2027"


@pytest.mark.parametrize(
    ("start", "months", "end"),
    [
        (ist(2027, 1, 31, 0, 30), 1, ist(2027, 2, 28, 0, 30)),  # UTC would say 30 Jan + 1 month = 1 March IST
        (ist(2028, 1, 31, 0, 30), 1, ist(2028, 2, 29, 0, 30)),  # a leap year
        (ist(2026, 11, 30, 23, 59), 3, ist(2027, 2, 28, 23, 59)),
        (ist(2027, 3, 1, 0, 30), 3, ist(2027, 6, 1, 0, 30)),  # UTC would say 28 Feb + 3 months = 29 May IST
    ],
)
def test_L_COMMITTEE_rules_2_31_jan_gives_the_end_of_february_on_the_office_calendar(
    start: dt.datetime, months: int, end: dt.datetime
) -> None:
    """L-COMMITTEE.rules/2: a day the month lacks becomes its last day, counted on the India date."""
    assert add_months(start, months) == end
    assert add_months(start.astimezone(UTC), months) == end
    assert add_months(start.astimezone(UTC), months).tzinfo == UTC


def test_L_COMMITTEE_rules_2_a_naive_time_stays_naive_at_the_same_wall_time() -> None:
    """L-COMMITTEE.rules/2: a time without a zone is taken as office time as it stands; 3 months on, it comes back
    without a zone at the same wall time (31 January + 3 months is 30 April)."""
    got = add_months(dt.datetime(2026, 11, 8, 0, 30), 3)
    assert got == dt.datetime(2027, 2, 8, 0, 30) and got.tzinfo is None
    assert add_months(dt.datetime(2027, 1, 31, 23, 45), 3) == dt.datetime(2027, 4, 30, 23, 45)


def test_L_COMMITTEE_rules_2_the_30_day_extensions_and_the_cap_agree() -> None:
    """L-COMMITTEE.rules/1-2, J-COMMITTEE/3a: 30 days, then 30 more twice, then the last step to the cap and no more.
    After the second extension "Extend to" names the cap, Monday 8 February 2027, and it is the same date the "up
    to" line names."""
    decided = SUNDAY_8_NOV.astimezone(UTC)  # as the database hands it back
    w = open_window(decided, P)
    now = decided + dt.timedelta(days=1)
    ww = words(w, now, P)
    assert (ww.until, ww.extend_to) == ("Until Tuesday 8 December", "Extend to Thursday 7 January 2027")
    w = extend(w, now, P)
    assert words(w, now, P).extend_to == "Extend to Saturday 6 February 2027"
    w = extend(w, now, P)
    ww = words(w, now, P)
    assert w.closes_at == ist(2027, 2, 6, 0, 30)
    assert ww.extend_to == f"Extend to {ww.max_until}" == "Extend to Monday 8 February 2027"
    w = extend(w, now, P)
    assert w.closes_at == w.max_closes_at == ist(2027, 2, 8, 0, 30) and w.extended_times == 3
    ww = words(w, now, P)
    assert (ww.extend_to, ww.limit_line, ww.until) == (
        None,
        "At the 3-month limit",
        "Until Monday 8 February 2027",
    )
    with pytest.raises(WindowRefused) as refused:
        extend(w, now, P)
    assert refused.value.code == "at_limit"


def test_L_COMMITTEE_rules_2_the_seeds_windows_and_return_dates_are_3_calendar_months(db: Any) -> None:
    """L-COMMITTEE.rules/2, L-DECIDE.rules/7: every seeded window's cap, and every seeded Not now's return date, is
    the desk's own `add_months` of the decision or merge time, never a count of 91 days."""
    from bootstrap import club_seed

    club_seed.load(db)
    try:
        windows = db.execute("SELECT opens_at, max_closes_at FROM decision_windows").fetchall()
        assert windows
        for r in windows:
            assert r["max_closes_at"] == add_months(r["opens_at"], P.window_max_months)
        returns = db.execute(
            "SELECT at, return_at FROM idea_decisions WHERE choice = 'not_now' AND return_in = '3m'"
        ).fetchall()
        assert returns
        for r in returns:
            assert r["return_at"] == add_months(r["at"], 3)
    finally:
        club_seed.remove(db)
