"""L-COMMITTEE window rules, without a database (V-ACC.committee/1–5)."""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable

import pytest

from desk import clock, when
from desk.promises import DEFAULTS as P
from desk.window import Window, WindowRefused, add_months, extend, open_window, reverse, words

IST = when.IST
CAL = clock.Calendar()


def at(y: int, m: int, d: int, h: int = 0, mi: int = 0) -> dt.datetime:
    return dt.datetime(y, m, d, h, mi, tzinfo=IST)


DECIDED = at(2026, 11, 16, 16, 58)  # "Today, 4:58 pm. She has it now."


def test_L_COMMITTEE_rules_1_window_opens_for_30_days_up_to_3_months() -> None:
    w = open_window(DECIDED, P)
    assert w.closes_at == at(2026, 12, 16, 16, 58) and w.max_closes_at == at(2027, 2, 16, 16, 58)
    ww = words(w, DECIDED, P)
    assert (ww.state, ww.left, ww.until) == ("open", "30 days left", "Until Wednesday 16 December")
    assert ww.extend_to == "Extend to Friday 15 January 2027" and ww.max_until == "Tuesday 16 February 2027"


def test_V_ACC_committee_1_a_five_day_old_decision_has_25_days_left() -> None:
    w = open_window(DECIDED, P)
    assert words(w, DECIDED + dt.timedelta(days=5, hours=1), P).left == "25 days left"


def test_V_ACC_committee_2_and_3_extend_30_days_at_a_time_to_the_limit() -> None:
    w = open_window(DECIDED, P)
    now = DECIDED + dt.timedelta(days=2)
    w = extend(w, now, P)
    ww = words(w, now, P)
    assert (ww.state, ww.extended, ww.until) == ("extended", "Extended once", "Until Friday 15 January 2027")
    # BLD-B263: a step that would end 2 days short of the cap goes to the cap
    assert ww.extend_to == "Extend to Tuesday 16 February 2027"
    w = extend(w, now, P)  # the second extension reaches the cap at three months
    assert w.closes_at == w.max_closes_at and w.extended_times == 2
    ww = words(w, now, P)
    assert (
        ww.extend_to is None and ww.limit_line == "At the 3-month limit" and ww.extended == "Extended twice"
    )
    with pytest.raises(WindowRefused) as refused:
        extend(w, now, P)
    assert refused.value.code == "at_limit"


def test_V_ACC_committee_4_a_reversal_is_final() -> None:
    w = reverse(open_window(DECIDED, P), DECIDED + dt.timedelta(days=1))
    assert w.state(DECIDED + dt.timedelta(days=2)) == "reversed"
    actions: tuple[Callable[[], object], ...] = (lambda: extend(w, DECIDED, P), lambda: reverse(w, DECIDED))
    for action in actions:
        with pytest.raises(WindowRefused) as refused:
            action()
        assert refused.value.code == "already_reversed"


def test_V_ACC_committee_5_a_window_left_alone_expires_and_the_decision_stands() -> None:
    w = open_window(at(2026, 10, 19, 10), P)
    now = at(2026, 11, 20, 9)
    ww = words(w, now, P)
    assert ww.state == "expired" and ww.left is None and ww.extend_to is None and ww.limit_line is None
    assert ww.closed_line == "Expired Wednesday 18 November. After 30 days. The decision stands."
    with pytest.raises(WindowRefused) as refused:
        reverse(w, now)
    assert refused.value.code == "window_closed"
    full = Window(w.opens_at, w.max_closes_at, w.max_closes_at, 3)
    assert words(full, at(2027, 2, 1), P).closed_line.endswith("After 3 months. The decision stands.")


def test_add_months_keeps_the_day_or_uses_the_month_end() -> None:
    assert add_months(at(2026, 11, 16), 3) == at(2027, 2, 16)
    assert add_months(at(2026, 11, 30), 3) == at(2027, 2, 28)
    assert add_months(at(2027, 12, 31), 2) == at(2028, 2, 29)
