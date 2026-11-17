"""The Ones Committee's window on a decision or a desk merge (L-COMMITTEE, E-ENTITIES.review `Window`).

Pure rules over stored times: open for 30 days from the decision, extendable 30 days at a time up to 3 months in
all, reversible once (final), and expired when it closes with nothing done. The state is worked out on read, so a
window shows "Expired" the moment it closes, whether or not the expiry timer has run.
"""

from __future__ import annotations

import calendar
import datetime as dt
from dataclasses import dataclass, replace
from typing import Literal

from desk import when
from desk.clock import countdown
from desk.promises import Promises

State = Literal["open", "extended", "reversed", "expired"]


class WindowRefused(Exception):
    """A committee action the window does not allow. `code` is the A-API.committee error code."""

    def __init__(self, code: Literal["at_limit", "window_closed", "already_reversed"]) -> None:
        super().__init__(code)
        self.code = code


def add_months(t: dt.datetime, months: int) -> dt.datetime:
    """The same day and time `months` later; a day the month lacks becomes its last day (31 Jan + 1 month =
    28 or 29 Feb)."""
    index = t.month - 1 + months
    year, month = t.year + index // 12, index % 12 + 1
    return t.replace(year=year, month=month, day=min(t.day, calendar.monthrange(year, month)[1]))


@dataclass(frozen=True)
class Window:
    opens_at: dt.datetime
    closes_at: dt.datetime
    max_closes_at: dt.datetime
    extended_times: int = 0
    reversed_at: dt.datetime | None = None

    def state(self, now: dt.datetime) -> State:
        if self.reversed_at is not None:
            return "reversed"
        if now >= self.closes_at:
            return "expired"
        return "extended" if self.extended_times else "open"

    def is_open(self, now: dt.datetime) -> bool:
        return self.state(now) in ("open", "extended")

    def at_limit(self) -> bool:
        return self.closes_at >= self.max_closes_at

    def next_close(self, p: Promises) -> dt.datetime | None:
        """Where "Extend" would move the end: 30 days on, capped at 3 months from the decision; None at the limit."""
        if self.at_limit():
            return None
        return min(self.closes_at + dt.timedelta(days=p.window_extend_days), self.max_closes_at)

    def progress(self, now: dt.datetime) -> float:
        """How much of the window has passed, 0 to 1, for the progress bar on S-R2's Decided state."""
        total = (self.closes_at - self.opens_at).total_seconds()
        return 1.0 if total <= 0 else min(1.0, max(0.0, (now - self.opens_at).total_seconds() / total))


def open_window(decided_at: dt.datetime, p: Promises) -> Window:
    """L-COMMITTEE.rules/1: 30 days from the decision; at most 3 months from it in all."""
    return Window(
        opens_at=decided_at,
        closes_at=decided_at + dt.timedelta(days=p.window_days),
        max_closes_at=add_months(decided_at, p.window_max_months),
    )


def extend(w: Window, now: dt.datetime, p: Promises) -> Window:
    """L-COMMITTEE.rules/2. Refuses with `already_reversed`, `window_closed` or `at_limit`."""
    _must_be_open(w, now)
    new_close = w.next_close(p)
    if new_close is None:
        raise WindowRefused("at_limit")
    return replace(w, closes_at=new_close, extended_times=w.extended_times + 1)


def reverse(w: Window, now: dt.datetime) -> Window:
    """L-COMMITTEE.rules/4: final; the window closes and nothing further is possible."""
    _must_be_open(w, now)
    return replace(w, reversed_at=now)


def _must_be_open(w: Window, now: dt.datetime) -> None:
    if w.reversed_at is not None:
        raise WindowRefused("already_reversed")
    if now >= w.closes_at:
        raise WindowRefused("window_closed")


def _days_after(w: Window) -> str:
    if w.closes_at >= w.max_closes_at:
        months = round((w.max_closes_at - w.opens_at).days / 30)
        return f"After {months} month{'s' * (months != 1)}."
    return f"After {(w.closes_at - w.opens_at).days} days."


@dataclass(frozen=True)
class WindowWords:
    """What the screens say about a window (S-R4 row, S-R2 Decided, S-R1 Decided this week, the sharer's page)."""

    state: State
    left: str | None  # "22 days left"; None once closed
    until: str  # "Until Wednesday 16 December"
    extended: str | None  # "Extended once"
    extend_to: str | None  # "Extend to Friday 15 January 2027"; None at the limit or once closed
    limit_line: str | None  # "At the 3-month limit", only when open and no extension remains
    max_until: str  # "Tuesday 16 February 2027"
    closed_line: str | None  # "Expired Wednesday 18 November. After 30 days. The decision stands."


def words(w: Window, now: dt.datetime, p: Promises, tz: dt.tzinfo = when.IST) -> WindowWords:
    state = w.state(now)
    open_ = state in ("open", "extended")
    nxt = w.next_close(p) if open_ else None
    closed_line = None
    if state == "expired":
        closed_line = f"Expired {when.day(w.closes_at, now, tz)}. {_days_after(w)} The decision stands."
    return WindowWords(
        state=state,
        left=countdown(w.closes_at, now, tz).label("left") if open_ else None,
        until=f"Until {when.day(w.closes_at, now, tz)}",
        extended=f"Extended {when.times(w.extended_times)}" if w.extended_times else None,
        extend_to=f"Extend to {when.day(nxt, now, tz)}" if nxt else None,
        limit_line=f"At the {p.window_max_months}-month limit" if open_ and nxt is None else None,
        max_until=when.day(w.max_closes_at, now, tz),
        closed_line=closed_line,
    )
