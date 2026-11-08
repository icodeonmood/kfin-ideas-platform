"""Working days from `rules/calendar.md` (IST, weekends, KFin holidays). Reminders and breaches arrive in B6."""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from core.config import get_settings
from rules import load_rule

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def add_working_days(start: dt.datetime, n: int) -> dt.datetime:
    """The same time of day, `n` working days later (a start on a non-working day counts from the next one)."""
    cal = load_rule(get_settings().company_repo_path, "calendar").data
    tz = ZoneInfo(str(cal.get("timezone", "Asia/Kolkata")))
    weekend = {DAYS.index(d) for d in cal.get("weekend", ["sat", "sun"])}
    holidays = {dt.date.fromisoformat(str(h["date"])) for h in cal.get("holidays") or []}
    local = start.astimezone(tz)
    day = local.date()

    def working(d: dt.date) -> bool:
        return d.weekday() not in weekend and d not in holidays

    while not working(day):  # a start on a weekend or holiday counts from the next working day
        day += dt.timedelta(days=1)
    added = 0
    while added < n:
        day += dt.timedelta(days=1)
        if working(day):
            added += 1
    return dt.datetime.combine(day, local.timetz())


def limit_wd(stage: str) -> int:
    data = load_rule(get_settings().company_repo_path, "sla").data
    return int(data[stage]["limit_wd"])


def working_seconds(a: dt.datetime, b: dt.datetime) -> float:
    """Seconds between two moments that fall on working days (whole days; weekends and holidays count zero)."""
    if b <= a:
        return 0.0
    cal = load_rule(get_settings().company_repo_path, "calendar").data
    tz = ZoneInfo(str(cal.get("timezone", "Asia/Kolkata")))
    weekend = {DAYS.index(d) for d in cal.get("weekend", ["sat", "sun"])}
    holidays = {dt.date.fromisoformat(str(h["date"])) for h in cal.get("holidays") or []}
    a, b = a.astimezone(tz), b.astimezone(tz)
    total = 0.0
    day = a.date()
    while day <= b.date():
        if day.weekday() not in weekend and day not in holidays:
            start = max(a, dt.datetime.combine(day, dt.time.min, tzinfo=tz))
            end = min(b, dt.datetime.combine(day + dt.timedelta(days=1), dt.time.min, tzinfo=tz))
            total += max(0.0, (end - start).total_seconds())
        day += dt.timedelta(days=1)
    return total


def add_working_seconds(start: dt.datetime, seconds: float) -> dt.datetime:
    """The moment `seconds` of working time after `start` (weekends and holidays are skipped whole)."""
    cal = load_rule(get_settings().company_repo_path, "calendar").data
    tz = ZoneInfo(str(cal.get("timezone", "Asia/Kolkata")))
    weekend = {DAYS.index(d) for d in cal.get("weekend", ["sat", "sun"])}
    holidays = {dt.date.fromisoformat(str(h["date"])) for h in cal.get("holidays") or []}
    t = start.astimezone(tz)
    left = max(0.0, seconds)
    while True:
        day_end = dt.datetime.combine(t.date() + dt.timedelta(days=1), dt.time.min, tzinfo=tz)
        if t.date().weekday() not in weekend and t.date() not in holidays:
            room = (day_end - t).total_seconds()
            if left <= room:
                return t + dt.timedelta(seconds=left)
            left -= room
        t = day_end
