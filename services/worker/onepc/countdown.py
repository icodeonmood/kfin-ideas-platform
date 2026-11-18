"""One countdown rule for every clock a person reads (F-COPY.plurals/3, L-QUESTIONS.clock/1, C-QCARD; BLD-A225).

The same deadline reads the same everywhere: the Inbox ("3 days left"), the questions card and Home ("3 days left"),
Answer ("3 days left to answer"), the desk ("3 days to answer"), the committee's window ("25 days left") and an
idea's edit window ("3 days left"). Only the place's own words after the count differ; the count and the pill come
from here. The web's twin is `apps/web/src/lib/countdown.ts`; both are held to `desk/countdown_vectors.json`.

- 24 hours or more ahead: calendar days in office time (India) from today to the due day, as people count them. A
  deadline of Friday 20 November, 2:40 pm reads "2 days left" all of Wednesday 18 November, morning and afternoon.
- Ahead by less than 24 hours: hours and minutes, "07:38", in the warn pill.
- At or past the deadline: how late, "Overdue by 5 hours" ("1 minute" for the first minute), in the bad pill.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Literal
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
DAY = 86400

Variant = Literal["normal", "warn", "bad"]


@dataclass(frozen=True)
class Countdown:
    """Time left on a clock.

    `count` is the amount: '3 days', '1 day', '07:38' under a day, or how late ('5 hours') once overdue.
    `variant` is the pill: normal, warn under a day, bad when overdue. `seconds` is left (negative once late).
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


def countdown(due_at: dt.datetime, now: dt.datetime, tz: dt.tzinfo = IST) -> Countdown:
    """A day or more ahead counts calendar days in office time, as people do: a 30-day window decided on Monday
    16 November has 25 days left on Saturday 21 November at any hour (V-ACC.committee/1). Under a day it is
    hours and minutes; once late, how late."""
    left = int((due_at - now).total_seconds())
    if left <= 0:
        late = -left
        if late < 3600:
            return Countdown(left, _amount(max(1, -(-late // 60)), "minute"), "bad")
        if late < DAY:
            return Countdown(left, _amount(late // 3600, "hour"), "bad")
        return Countdown(left, _amount(late // DAY, "day"), "bad")
    if left < DAY:
        minutes = max(1, left // 60)
        return Countdown(left, f"{minutes // 60:02d}:{minutes % 60:02d}", "warn")
    days = (due_at.astimezone(tz).date() - now.astimezone(tz).date()).days
    return Countdown(left, _amount(days, "day"), "normal")


def label(due_at: dt.datetime, now: dt.datetime, suffix: str, tz: dt.tzinfo = IST) -> str:
    """The whole words for one place: `label(due, now, "left")` is "2 days left", "07:38 left", "Overdue by 5 hours"."""
    return countdown(due_at, now, tz).label(suffix)
