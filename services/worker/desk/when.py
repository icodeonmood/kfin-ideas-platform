"""Dates and times as the review side says them (A-API.conventions/6: the server sends the raw time and the words).

Office time is India time. The forms come from the boards' copy (`1pc-handoff/reference/copy/`):
"Friday 20 November", "2 November", "Thursday 19 November, 6 pm", "12:05 pm", "1 hour ago", "yesterday, 6:10 pm".
A year is added only when the date is not in the current year ("Tuesday 16 February 2027").
"""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
# Spelled out, not strftime: day and month names must not follow the server's locale.
DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December")  # fmt: skip


def _local(t: dt.datetime, tz: dt.tzinfo) -> dt.datetime:
    if t.tzinfo is None:
        raise ValueError("times must carry a time zone")
    return t.astimezone(tz)


def clock(t: dt.datetime, tz: dt.tzinfo = IST) -> str:
    """'6 pm', '6:30 pm', '12:05 pm', '9:50 am'. Noon is '12 pm', midnight '12 am'."""
    lt = _local(t, tz)
    hour = lt.hour % 12 or 12
    suffix = "am" if lt.hour < 12 else "pm"
    return f"{hour} {suffix}" if lt.minute == 0 else f"{hour}:{lt.minute:02d} {suffix}"


def _year(lt: dt.datetime, now: dt.datetime, tz: dt.tzinfo) -> str:
    return "" if lt.year == _local(now, tz).year else f" {lt.year}"


def day(t: dt.datetime, now: dt.datetime, tz: dt.tzinfo = IST) -> str:
    """'Friday 20 November'; 'Tuesday 16 February 2027' when the year differs from now's."""
    lt = _local(t, tz)
    return f"{DAYS[lt.weekday()]} {lt.day} {MONTHS[lt.month - 1]}{_year(lt, now, tz)}"


def short(t: dt.datetime, now: dt.datetime, tz: dt.tzinfo = IST) -> str:
    """'2 November' ('Picked, 2 November'); '2 November 2025' in another year."""
    lt = _local(t, tz)
    return f"{lt.day} {MONTHS[lt.month - 1]}{_year(lt, now, tz)}"


def day_time(t: dt.datetime, now: dt.datetime, tz: dt.tzinfo = IST) -> str:
    """'Thursday 19 November, 6 pm'."""
    return f"{day(t, now, tz)}, {clock(t, tz)}"


def which_day(t: dt.datetime, now: dt.datetime, tz: dt.tzinfo = IST) -> str:
    """'today', 'yesterday', 'tomorrow', else the day ('Monday 16 November')."""
    gap = (_local(t, tz).date() - _local(now, tz).date()).days
    return {0: "today", -1: "yesterday", 1: "tomorrow"}.get(gap) or day(t, now, tz)


def deadline(t: dt.datetime, now: dt.datetime, tz: dt.tzinfo = IST) -> str:
    """When something is due: '7 pm today', '6 pm tomorrow', else 'Thursday 19 November, 6 pm'."""
    when = which_day(t, now, tz)
    return f"{clock(t, tz)} {when}" if when in ("today", "tomorrow") else day_time(t, now, tz)


def since(t: dt.datetime, now: dt.datetime, tz: dt.tzinfo = IST) -> str:
    """How long ago, as the desk says it: 'just now', '5 minutes ago', '1 hour ago' (same day);
    'yesterday, 6:10 pm'; then the day ('Monday 16 November')."""
    seconds = (now - t).total_seconds()
    when = which_day(t, now, tz)
    if when == "today" and seconds >= 0:
        minutes = int(seconds // 60)
        if minutes < 1:
            return "just now"
        if minutes < 60:
            return f"{minutes} minute{'s' * (minutes != 1)} ago"
        hours = minutes // 60
        return f"{hours} hour{'s' * (hours != 1)} ago"
    if when == "yesterday":
        return f"yesterday, {clock(t, tz)}"
    return day(t, now, tz)


def times(n: int) -> str:
    """'once', 'twice', '3 times' ('Extended once')."""
    return {1: "once", 2: "twice"}.get(n) or f"{n} times"
