"""Words lane C's sorting and sending return, computed on the server (A-API.conventions/6) in India time.

Date forms are the boards' and match the idea page's (lane E, `ideapage/words.py`) and the review side's (lane B,
`desk/when.py`), so every screen says a date the same way: "Friday 20 November", "Today, 10:05 am", "3 days left".
A year is added only when the date is not in the current year. A test pins these forms.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from typing import Any
from zoneinfo import ZoneInfo

from onepc import enums
from onepc.countdown import countdown as shared_countdown

IST = ZoneInfo("Asia/Kolkata")
DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def local(t: dt.datetime) -> dt.datetime:
    if t.tzinfo is None:
        raise ValueError("times must carry a time zone")
    return t.astimezone(IST)


def clock(t: dt.datetime) -> str:
    """'6 pm', '1:39 pm', '10:05 am'."""
    lt = local(t)
    hour = lt.hour % 12 or 12
    suffix = "am" if lt.hour < 12 else "pm"
    return f"{hour} {suffix}" if lt.minute == 0 else f"{hour}:{lt.minute:02d} {suffix}"


def day(t: dt.datetime, now: dt.datetime) -> str:
    """'Friday 20 November'; 'Tuesday 16 February 2027' in another year."""
    lt = local(t)
    year = "" if lt.year == local(now).year else f" {lt.year}"
    return f"{DAYS[lt.weekday()]} {lt.day} {MONTHS[lt.month - 1]}{year}"


def short_date(t: dt.datetime) -> str:
    """'14-Nov-26', as in 'Shared 14-Nov-26'."""
    lt = local(t)
    return f"{lt.day:02d}-{MONTHS[lt.month - 1][:3]}-{lt.year % 100:02d}"


def when_shared(t: dt.datetime, now: dt.datetime) -> str:
    """The Shared stage's line: 'Today, 10:05 am', 'Yesterday, 6:10 pm', else the day."""
    gap = (local(t).date() - local(now).date()).days
    if gap == 0:
        return f"Today, {clock(t)}"
    if gap == -1:
        return f"Yesterday, {clock(t)}"
    return day(t, now)


def countdown(until: dt.datetime, now: dt.datetime) -> dict[str, Any]:
    """'3 days left' (neutral); under a day '07:38 left' (warn); then 'Overdue by 5 hours' (bad) (C-PILL.rules/3).
    The count is the one rule every place uses (F-COPY.plurals/3, `onepc.countdown`, BLD-A225): office calendar days
    a day or more ahead. The pill says "neutral" where the countdown says "normal"."""
    c = shared_countdown(until, now)
    variant = "neutral" if c.variant == "normal" else c.variant
    return {"label": c.label("left"), "variant": variant, "until": until.isoformat()}


def join(items: Sequence[str]) -> str:
    items = [i for i in items if i]
    if not items:
        return ""
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def in_sentence(label: str) -> str:
    """A list label inside a sentence: 'Investors' -> 'investors', but 'KFin teams' and 'AMC clients' keep their
    capitals (a second capital letter marks a name or an acronym)."""
    if len(label) > 1 and label[1].isupper():
        return label
    return label[:1].lower() + label[1:]


def pill(status: str) -> dict[str, str]:
    data = enums._data()["enums"]["idea_status"]
    return {"status": status, "label": data["labels"][status], "variant": data["pill"][status]}


SUFFIX = {"done": ", done", "now": ", now", "to_come": ", to come", "not_going_ahead": ", not going ahead"}


def stage_nodes(nodes: Sequence[tuple[str, str | None, dt.datetime | None]]) -> list[dict[str, Any]]:
    """E-ENTITIES StageState for the five stages, with the label and the screen reader's suffix (C-TRACK)."""
    labels = enums.labels("stage")
    return [
        {
            "stage": stage,
            "label": labels[stage],
            "state": state,
            "suffix": SUFFIX[state],
            **({"detail": detail} if detail else {}),
            **({"at": at.isoformat()} if at else {}),
        }
        for stage, (state, detail, at) in zip(enums.STAGE, nodes, strict=True)
    ]
