"""Words the idea pages show, computed on the server (A-API.conventions/6): dates as sentences, countdowns, the
status pill and the five-stage track (C-TRACK, C-PILL, E-ENUMS.idea-status).

Date forms follow the boards' copy and the review side's helpers (lane B, `desk/when.py`), so every screen says a
date the same way: "Friday 20 November", "Today, 10:05 am", "Thursday 19 November, 6 pm", "Shared 14-Nov-26".
A year is added only when the date is not in the current year. Office time is India time.
"""

from __future__ import annotations

import datetime as dt
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal
from zoneinfo import ZoneInfo

from onepc import enums

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
MON = tuple(m[:3] for m in MONTHS)

STATUS_LABEL: dict[str, str] = enums.labels("idea_status")
STAGES: tuple[str, ...] = enums.STAGE
STAGE_LABEL: dict[str, str] = enums.labels("stage")
PART_LABEL: dict[str, str] = enums.labels("part")
DECISION_LABEL: dict[str, str] = enums.labels("decision")
CLOSED: frozenset[str] = frozenset(enums.CLOSED_STATUSES)
PICKED_AND_BUILDING: frozenset[str] = frozenset(enums.PICKED_AND_BUILDING)


def _pill_variants() -> dict[str, str]:
    from onepc.enums import _data

    return dict(_data()["enums"]["idea_status"]["pill"])


PILL_VARIANT: dict[str, str] = _pill_variants()


def local(t: dt.datetime) -> dt.datetime:
    if t.tzinfo is None:
        raise ValueError("times must carry a time zone")
    return t.astimezone(IST)


def clock(t: dt.datetime) -> str:
    """'6 pm', '6:30 pm', '10:05 am'."""
    lt = local(t)
    hour = lt.hour % 12 or 12
    suffix = "am" if lt.hour < 12 else "pm"
    return f"{hour} {suffix}" if lt.minute == 0 else f"{hour}:{lt.minute:02d} {suffix}"


def _year(t: dt.datetime, now: dt.datetime) -> str:
    return "" if local(t).year == local(now).year else f" {local(t).year}"


def day(t: dt.datetime, now: dt.datetime) -> str:
    """'Friday 20 November'; 'Tuesday 16 February 2027' in another year."""
    lt = local(t)
    return f"{DAYS[lt.weekday()]} {lt.day} {MONTHS[lt.month - 1]}{_year(t, now)}"


def day_time(t: dt.datetime, now: dt.datetime) -> str:
    """'Monday 16 November, 11:20 am'."""
    return f"{day(t, now)}, {clock(t)}"


def short_date(t: dt.datetime) -> str:
    """'14-Nov-26', as the idea card's 'Shared 14-Nov-26'."""
    lt = local(t)
    return f"{lt.day:02d}-{MON[lt.month - 1]}-{lt.year % 100:02d}"


def which_day(t: dt.datetime, now: dt.datetime) -> str | None:
    gap = (local(t).date() - local(now).date()).days
    return {0: "today", -1: "yesterday", 1: "tomorrow"}.get(gap)


def when_shared(t: dt.datetime, now: dt.datetime) -> str:
    """The Shared stage's line (C-TRACK.detail): 'Today, 10:05 am', 'Yesterday, 6:10 pm', else the day."""
    w = which_day(t, now)
    if w in ("today", "yesterday"):
        return f"{w.capitalize()}, {clock(t)}"
    return day(t, now)


def weekday_or_day(t: dt.datetime, now: dt.datetime) -> str:
    """'Monday' within the last six days ('asked you 3 questions on Monday'), else the day."""
    gap = (local(now).date() - local(t).date()).days
    if gap == 0:
        return "today"
    if gap == 1:
        return "yesterday"
    if 1 < gap < 7:
        return DAYS[local(t).weekday()]
    return day(t, now)


def saved_when(t: dt.datetime, now: dt.datetime) -> str:
    """A draft's save time, as S-07's rows say it: 'yesterday', '8:42 pm Friday', 'Monday 12 October'."""
    w = which_day(t, now)
    if w == "today":
        return f"today, {clock(t)}"
    if w == "yesterday":
        return "yesterday"
    gap = (local(now).date() - local(t).date()).days
    if 1 < gap < 7:
        return f"{clock(t)} {DAYS[local(t).weekday()]}"
    return day(t, now)


def deadline(t: dt.datetime, now: dt.datetime) -> str:
    """'7 pm today', '6 pm tomorrow', else 'Thursday 19 November, 6 pm'."""
    w = which_day(t, now)
    return f"{clock(t)} {w}" if w in ("today", "tomorrow") else day_time(t, now)


Variant = Literal["neutral", "warn", "bad"]


def countdown(until: dt.datetime, now: dt.datetime) -> dict[str, Any]:
    """'3 days left' (neutral); under a day '07:38 left' in the warn variant (C-PILL.rules/3); then 'Overdue'."""
    seconds = (until - now).total_seconds()
    if seconds <= 0:
        return {"label": "Overdue", "variant": "bad", "until": until.isoformat()}
    if seconds < 86400:
        minutes = int(seconds // 60)
        return {
            "label": f"{minutes // 60:02d}:{minutes % 60:02d} left",
            "variant": "warn",
            "until": until.isoformat(),
        }
    days = math.ceil(seconds / 86400)
    return {"label": f"{days} day{'s' * (days != 1)} left", "variant": "neutral", "until": until.isoformat()}


def count(n: int, one: str, many: str | None = None) -> str:
    return f"{n} {one if n == 1 else (many or one + 's')}"


def number_word(n: int) -> str:
    return {1: "one", 2: "two", 3: "three"}.get(n, str(n))


def rupees(amount: float) -> str:
    """Indian grouping: 25000 -> '₹25,000', 150000 -> '₹1,50,000'."""
    whole = round(amount)
    s = str(whole)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        groups: list[str] = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        s = ",".join(groups) + "," + tail
    return f"₹{s}"


def _num(x: Any) -> str:
    f = float(x)
    return str(int(f)) if f.is_integer() else f"{f:g}"


def hours_range(low: Any, high: Any) -> str | None:
    """'70 to 150 hours a month' (E-ENTITIES Range.text)."""
    if low is None:
        return None
    if high is None or float(high) == float(low):
        return f"About {_num(low)} hours a month"
    return f"{_num(low)} to {_num(high)} hours a month"


def money_range(low: Any, high: Any) -> str | None:
    if low is None:
        return None
    if high is None or float(high) == float(low):
        return f"About {rupees(float(low))} a month"
    return f"{rupees(float(low))} to {rupees(float(high))} a month"


_BRINGS_PARTS = {
    "saves_time": ("Saves", "time"),
    "saves_cost": ("Saves", "cost"),
    "earns_revenue": ("Earns", "revenue"),
}


def brings_words(brings: Sequence[str]) -> str:
    """'Saves time and cost', 'Saves time and earns revenue', 'Not sure yet' (E-ENUMS.sorting brings)."""
    labels = enums.labels("brings")
    if not brings:
        return "Not sure yet"
    phrases: list[str] = []
    verb = None
    for b in brings:
        if b in _BRINGS_PARTS:
            v, obj = _BRINGS_PARTS[b]
            phrases.append(obj if v == verb else f"{v.lower()} {obj}")
            verb = v
        else:
            phrases.append(labels.get(b, b).lower())
            verb = None
    text = phrases[0] if len(phrases) == 1 else ", ".join(phrases[:-1]) + " and " + phrases[-1]
    return text[0].upper() + text[1:]


def join_words(items: Sequence[str]) -> str:
    items = [i for i in items if i]
    if not items:
        return ""
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


# --- The status pill (C-PILL, E-ENUMS.idea-status) -----------------------------------------------------------------


def pill(status: str) -> dict[str, str]:
    """The pill's words and variant are fixed per status (C-PILL.rules/1)."""
    return {"status": status, "label": STATUS_LABEL[status], "variant": PILL_VARIANT[status]}


# --- The five-stage track (C-TRACK, E-ENUMS.stage) -----------------------------------------------------------------

StageState = Literal["done", "now", "to_come", "not_going_ahead"]
SUFFIX = {"done": ", done", "now": ", now", "to_come": ", to come", "not_going_ahead": ", not going ahead"}


@dataclass
class Node:
    state: StageState
    detail: str | None = None
    at: dt.datetime | None = None


def nodes_json(nodes: Sequence[Node]) -> list[dict[str, Any]]:
    """E-ENTITIES StageState, with the label and the screen reader's suffix (C-TRACK.anatomy)."""
    return [
        {
            "stage": stage,
            "label": STAGE_LABEL[stage],
            "state": n.state,
            "suffix": SUFFIX[n.state],
            **({"detail": n.detail} if n.detail else {}),
            **({"at": n.at.isoformat()} if n.at else {}),
        }
        for stage, n in zip(STAGES, nodes, strict=True)
    ]


def stage_index(status: str) -> int | None:
    """Where an idea is on the five stages: the index of the 'now' node, 5 when all are done, None for no track
    (a draft, a merged idea: E-ENUMS.idea-status 'Stage on the track')."""
    return {
        "checking": 1,
        "with_review_desk": 2,
        "needs_you": 2,
        "picked": 3,
        "being_built": 3,
        "shipped": 5,
        "not_now": 3,
        "not_picked": 3,
        "withdrawn": 2,
    }.get(status)


def mini_track(status: str) -> dict[str, Any] | None:
    """S-07's five-segment track under the pill: filled up to the current stage; drafts show the pill only. The
    label is what a screen reader hears ('2 of 5 stages done. Now: reviewed')."""
    at = stage_index(status)
    if at is None:
        return None
    if status in ("not_picked", "withdrawn"):
        done = 3 if status == "not_picked" else 2
        segs = ["done"] * done + ["not_going_ahead"] * (5 - done)
        where = "Reviewed" if status == "not_picked" else "Withdrawn before review"
        return {"segments": segs, "label": f"{where}, not going ahead"}
    if status == "not_now":
        return {
            "segments": ["done", "done", "done", "to_come", "to_come"],
            "label": "3 of 5 stages done. Not now",
        }
    if at >= 5:
        return {"segments": ["done"] * 5, "label": "All 5 stages done"}
    segs = ["done"] * at + ["now"] + ["to_come"] * (4 - at)
    return {"segments": segs, "label": f"{at} of 5 stages done. Now: {STAGE_LABEL[STAGES[at]].lower()}"}
