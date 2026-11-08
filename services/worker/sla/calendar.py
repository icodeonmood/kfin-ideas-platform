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
    added = 0
    while added < n:
        day += dt.timedelta(days=1)
        if day.weekday() not in weekend and day not in holidays:
            added += 1
    return dt.datetime.combine(day, local.timetz())


def limit_wd(stage: str) -> int:
    data = load_rule(get_settings().company_repo_path, "sla").data
    return int(data[stage]["limit_wd"])
