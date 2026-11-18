"""F-COPY.plurals/3, L-QUESTIONS.clock/1, C-QCARD, S-H5 (BLD-A225): one countdown rule for every place.

Lane G's walk on Wednesday 18 November found one deadline (Friday 20 November, 2:40 pm) reading "1 day left" in the
Inbox and "2 days left" on the questions card and Home. Every clock now counts with `onepc.countdown`, held to the
vectors the web's `lib/countdown.ts` is held to. Pure functions: no database, no stack. Synthetic dates only.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

import pytest

from desk import clock
from ideapage import words as page_words
from notify import render
from onepc import countdown as one
from submit import words as submit_words

IST = one.IST
VECTORS: list[dict[str, Any]] = json.loads(
    Path(clock.__file__).with_name("countdown_vectors.json").read_text()
)["cases"]
DUE = dt.datetime(2026, 11, 20, 14, 40, tzinfo=IST)  # Friday 20 November, 2:40 pm
WED_1PM = dt.datetime(2026, 11, 18, 13, 0, tzinfo=IST)
WED_4PM = dt.datetime(2026, 11, 18, 16, 0, tzinfo=IST)


def _at(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s)


@pytest.mark.parametrize("v", VECTORS, ids=lambda v: f"{v['due']}<-{v['now']}")
def test_F_COPY_plurals_3_L_QUESTIONS_clock_1_C_QCARD_the_shared_vectors_hold_with_their_words(
    v: dict[str, Any],
) -> None:
    c = one.countdown(_at(v["due"]), _at(v["now"]))
    assert (c.count, c.variant, c.label("left")) == (v["count"], v["variant"], v["label"])
    assert one.label(_at(v["due"]), _at(v["now"]), "left") == v["label"]


def test_F_COPY_plurals_3_the_desk_counts_with_the_same_rule() -> None:
    """desk/clock.py re-exports the one rule; there is no second copy on the worker."""
    assert clock.countdown is one.countdown and clock.Countdown is one.Countdown


def test_F_COPY_plurals_3_every_place_says_the_walks_deadline_the_same_way() -> None:
    """J-TRACK/2: Wednesday 1 pm and 4 pm both read "2 days": the Inbox, the edit window and the desk agree."""
    for now in (WED_1PM, WED_4PM):
        assert render.countdown(DUE, now) == "2 days left"
        assert submit_words.countdown(DUE, now)["label"] == "2 days left"
        assert page_words.countdown(DUE, now)["label"] == "2 days left"
        assert clock.countdown(DUE, now).label("to answer") == "2 days to answer"


@pytest.mark.parametrize("v", VECTORS, ids=lambda v: f"{v['due']}<-{v['now']}")
def test_F_COPY_plurals_3_the_edit_window_pill_follows_the_vectors(v: dict[str, Any]) -> None:
    """S-06 and S-06B's edit window (C-PILL.rules/3): the same words; the pill says "neutral" for "normal"."""
    pill = {"normal": "neutral", "warn": "warn", "bad": "bad"}[v["variant"]]
    for words in (submit_words, page_words):
        got = words.countdown(_at(v["due"]), _at(v["now"]))
        assert (got["label"], got["variant"]) == (v["label"], pill)


def test_S_H5_the_inbox_item_for_the_walks_case_reads_2_days_left() -> None:
    """S-H5, J-TRACK/2: the questions item's countdown and its pill, at 1 pm and at 4 pm."""
    for now in (WED_1PM, WED_4PM):
        due = render.due("questions", DUE, now)
        assert due is not None
        assert (due["label"], due["variant"]) == ("2 days left", "normal")
        assert due["long"] == "Friday 20 November, 2:40 pm"


def test_S_H5_the_inbox_countdown_reads_hours_and_minutes_then_how_late() -> None:
    """F-COPY.plurals/3 in the Inbox: under a day "07:38 left" (warn); past due "Overdue by 5 hours" (bad). A kind
    that is not a countdown reads its date and has no pill."""
    seven38 = render.due("answer_reminder", DUE, DUE - dt.timedelta(hours=7, minutes=38))
    late = render.due("questions", DUE, DUE + dt.timedelta(hours=5))
    dated = render.due("build_ask", DUE, WED_1PM)
    assert seven38 is not None and (seven38["label"], seven38["variant"]) == ("07:38 left", "warn")
    assert late is not None and (late["label"], late["variant"]) == ("Overdue by 5 hours", "bad")
    assert dated is not None and dated["label"] == "By Fri, 20 Nov" and "variant" not in dated


def test_L_QUESTIONS_clock_2_a_reminder_says_what_is_left_as_the_countdown_counts_it() -> None:
    """J-TRACK/6: "2 days", "07:38" while the time is ahead; once passed, what was left when it was sent."""
    sent_day_before = {"due_at": DUE, "created_at": DUE - dt.timedelta(days=1)}
    sent_two_hours_before = {"due_at": DUE, "created_at": DUE - dt.timedelta(hours=2)}
    assert render._left(sent_day_before, WED_4PM) == "2 days"
    assert render._left(sent_day_before, DUE - dt.timedelta(hours=7, minutes=38)) == "07:38"
    assert render._left(sent_day_before, DUE + dt.timedelta(hours=1)) == "1 day"
    assert render._left(sent_two_hours_before, DUE + dt.timedelta(hours=1)) == "02:00"
