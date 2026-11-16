"""The review side's clocks, worked out on read from stored times (L-REVIEW.clock, L-QUESTIONS.clock).

Nothing here writes; a screen is right without any job having run. Timers (reminders, the decide-by digest,
Not now coming back, a window expiring) are lane A's engine calling lane B's handlers.

Working-day deadlines count the start day as day 1 when it is a working day and the start is before the deadline
hour; otherwise day 1 is the next working day. That reading matches the boards: shared Saturday 14 November,
decide by Friday 20 November (5 working days); picked Monday 16 November, team chosen by Friday 27 November
(10 working days) (BLD-B231).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Literal

from desk import when
from desk.promises import Promises

Variant = Literal["normal", "warn", "bad"]
DAY_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


@dataclass(frozen=True)
class Calendar:
    """Office time and working days, from the company repo's `calendar` rule."""

    tz: dt.tzinfo = when.IST
    weekend: frozenset[int] = frozenset({5, 6})
    holidays: frozenset[dt.date] = field(default_factory=frozenset)

    def working(self, d: dt.date) -> bool:
        return d.weekday() not in self.weekend and d not in self.holidays

    def at(self, d: dt.date, hour: int) -> dt.datetime:
        return dt.datetime.combine(d, dt.time(hour), tzinfo=self.tz)


def office_calendar() -> Calendar:
    from zoneinfo import ZoneInfo

    from core.config import get_settings
    from rules import load_rule

    data = load_rule(get_settings().company_repo_path, "calendar").data
    return Calendar(
        tz=ZoneInfo(str(data.get("timezone", "Asia/Kolkata"))),
        weekend=frozenset(DAY_NAMES.index(d) for d in data.get("weekend", ["sat", "sun"])),
        holidays=frozenset(dt.date.fromisoformat(str(h["date"])) for h in data.get("holidays") or []),
    )


def working_day_deadline(start: dt.datetime, n: int, hour: int, cal: Calendar) -> dt.datetime:
    """The deadline hour on the `n`th working day, counting the start day as day 1 (see the module note)."""
    local = start.astimezone(cal.tz)
    day = local.date()
    if not cal.working(day) or local >= cal.at(day, hour):
        day += dt.timedelta(days=1)
    counted = 0
    while True:
        if cal.working(day):
            counted += 1
            if counted == n:
                return cal.at(day, hour)
        day += dt.timedelta(days=1)


def decide_by(shared_at: dt.datetime, p: Promises, cal: Calendar) -> dt.datetime:
    """L-REVIEW.clock/1: 5 working days after sharing, at the deadline hour."""
    return working_day_deadline(shared_at, p.review_working_days, p.deadline_hour, cal)


def team_by(decided_at: dt.datetime, p: Promises, cal: Calendar) -> dt.datetime:
    """L-DECIDE.rules/6: a build team is chosen within 10 working days of the Pick."""
    return working_day_deadline(decided_at, p.team_by_working_days, p.deadline_hour, cal)


def answer_due(sent_at: dt.datetime, time_to_answer: str, p: Promises, cal: Calendar) -> dt.datetime:
    """L-QUESTIONS.clock/5: 1 day is 24 hours from sending; 3 days and 1 week end at 6 pm office time on the day."""
    days = p.answer_days_for(time_to_answer)
    if days == 1:
        return sent_at + dt.timedelta(hours=24)
    return cal.at(sent_at.astimezone(cal.tz).date() + dt.timedelta(days=days), p.deadline_hour)


def give_more_time(due_at: dt.datetime, p: Promises) -> dt.datetime:
    """'Give 2 more days': the deadline moves two days, keeping its time of day."""
    return due_at + dt.timedelta(days=p.give_more_days)


def reminders(sent_at: dt.datetime, due_at: dt.datetime, p: Promises) -> list[dt.datetime]:
    """L-QUESTIONS.clock/2: 1 day and 2 hours before the deadline, those still ahead of the sending."""
    return sorted(
        due_at - dt.timedelta(hours=h)
        for h in p.reminders_before_hours
        if due_at - dt.timedelta(hours=h) > sent_at
    )


def after_decide_by(due_at: dt.datetime, decide_by_at: dt.datetime) -> bool:
    """L-QUESTIONS.ask/4: the answer deadline falls after the reviewer's own date."""
    return due_at > decide_by_at


@dataclass(frozen=True)
class Countdown:
    """Time left on a clock, as the review side shows it.

    `count` is the amount: '3 days', '1 day', '07:38' under a day, or how late ('5 hours') once overdue.
    `variant` is the pill: normal, warn under a day, bad when overdue.
    """

    seconds: int
    count: str
    variant: Variant

    @property
    def overdue(self) -> bool:
        return self.variant == "bad"

    def label(self, suffix: str) -> str:
        """'3 days to answer', '07:38 left', 'Overdue by 5 hours' (the suffix is the place's own words)."""
        return f"Overdue by {self.count}" if self.overdue else f"{self.count} {suffix}"


def _amount(n: int, unit: str) -> str:
    return f"{n} {unit}{'s' * (n != 1)}"


def countdown(due_at: dt.datetime, now: dt.datetime) -> Countdown:
    left = int((due_at - now).total_seconds())
    if left <= 0:
        late = -left
        if late < 3600:
            return Countdown(left, _amount(max(1, -(-late // 60)), "minute"), "bad")
        if late < 86400:
            return Countdown(left, _amount(late // 3600, "hour"), "bad")
        return Countdown(left, _amount(late // 86400, "day"), "bad")
    if left < 86400:
        minutes = max(1, left // 60)
        return Countdown(left, f"{minutes // 60:02d}:{minutes % 60:02d}", "warn")
    return Countdown(left, _amount(left // 86400, "day"), "normal")
