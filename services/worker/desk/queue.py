"""The review desk's queue (L-REVIEW.queue, S-R1): which tab an idea is on, the row's words, the sort and the
summary sentence. Rows are worked out on read from stored facts, so every clock is current when the page loads.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from desk import when
from desk.clock import Countdown, countdown
from desk.decide import LABELS
from desk.questions import SetFacts, desk_line, overdue, state
from desk.window import Window

Tab = Literal["to_review", "waiting", "answered", "decided"]
TABS: tuple[Tab, ...] = ("to_review", "waiting", "answered", "decided")
TAB_LABELS: dict[str, str] = {
    "to_review": "To review",
    "waiting": "Waiting on the sharer",
    "answered": "Answered, back to you",
    "decided": "Decided this week",
}
Sort = Literal["time_left", "decide_by", "area"]
SORTS: tuple[Sort, ...] = ("time_left", "decide_by", "area")


@dataclass(frozen=True)
class Reversal:
    to: str
    at: dt.datetime


@dataclass(frozen=True)
class DeskIdea:
    """What the queue needs to know about one idea routed to the desk."""

    idea_id: str
    title: str
    sharer_name: str  # "Kavya Menon"
    sharer_first_name: str
    area: str
    city: str
    status: str
    decide_by: dt.datetime
    questions: SetFacts | None = None  # the latest set, if any
    decision: str | None = None  # pick | not_now | not_picked
    decided_at: dt.datetime | None = None
    window: Window | None = None
    reversal: Reversal | None = None


def tab_of(i: DeskIdea, now: dt.datetime, decided_days: int) -> Tab | None:
    """L-REVIEW.queue: the one tab an idea is on, or None when it is off the desk (decided earlier than this
    week, withdrawn, merged, or a Not now still waiting for its return date)."""
    if i.decided_at is not None:
        return "decided" if now - i.decided_at < dt.timedelta(days=decided_days) else None
    if i.status not in ("with_review_desk", "needs_you"):
        return None
    s = state(i.questions) if i.questions else None
    if s in ("sent", "seen"):
        return "waiting"
    if s == "partly_answered":  # some answers arrived: back with the reviewer (L-QUESTIONS.answer/5)
        return "answered" if i.questions and i.questions.answered_at else "waiting"
    if s == "answered":
        return "answered"
    return "to_review"


def clock_of(i: DeskIdea, tab: Tab, now: dt.datetime) -> tuple[dt.datetime, Countdown, str]:
    """The Time left column: the answer clock while waiting, else the decision clock."""
    if tab == "waiting" and i.questions and i.questions.due_at:
        return i.questions.due_at, countdown(i.questions.due_at, now), "to answer"
    return i.decide_by, countdown(i.decide_by, now), "to decide"


@dataclass(frozen=True)
class Row:
    idea_id: str
    title: str
    who: str  # "Kavya Menon, Investor service, Hyderabad"
    questions: str
    time_left: str | None
    variant: str | None
    due_at: dt.datetime | None
    decide_by: str  # "Friday 20 November"
    action: str  # "Open", "Read answers", "Remind Divya"
    action_kind: Literal["open", "read_answers", "remind"]
    decision: str | None = None  # "Picked, 2 November" / "Reversed: picked"
    committee: str | None = None  # "Ones Committee can review it until Wednesday 2 December"
    area: str = ""
    decide_by_at: dt.datetime | None = None
    decided_at: dt.datetime | None = None


def _committee_line(i: DeskIdea, now: dt.datetime, tz: dt.tzinfo) -> str | None:
    if i.reversal is not None:
        verb = "picked it" if i.reversal.to == "pick" else f"changed it to {LABELS[i.reversal.to].lower()}"
        return (
            f"The Ones Committee {verb} on {when.short(i.reversal.at, now, tz)}, "
            f"with a note to {i.sharer_first_name}"
        )
    if i.window is None:
        return None
    if i.window.is_open(now):
        return f"Ones Committee can review it until {when.day(i.window.closes_at, now, tz)}"
    return "The Ones Committee’s window has closed. The decision stands."


def row(i: DeskIdea, tab: Tab, now: dt.datetime, tz: dt.tzinfo = when.IST) -> Row:
    who = f"{i.sharer_name}, {i.area}, {i.city}"
    if tab == "decided":
        assert i.decision is not None and i.decided_at is not None
        decision = (
            f"Reversed: {LABELS[i.reversal.to].lower()}"
            if i.reversal
            else f"{LABELS[i.decision]}, {when.short(i.decided_at, now, tz)}"
        )
        return Row(
            i.idea_id, i.title, who, desk_line(i.questions, now, decided=True, tz=tz), None, None, None,
            when.day(i.decide_by, now, tz), "Open", "open", decision, _committee_line(i, now, tz), i.area,
            i.decide_by, i.decided_at,
        )  # fmt: skip
    due, c, suffix = clock_of(i, tab, now)
    if tab == "waiting" and i.questions and overdue(i.questions, now):
        action, kind = f"Remind {i.sharer_first_name}", "remind"
    elif tab == "answered":
        action, kind = "Read answers", "read_answers"
    else:
        action, kind = "Open", "open"
    return Row(
        i.idea_id, i.title, who, desk_line(i.questions, now, tz=tz), c.label(suffix), c.variant, due,
        when.day(i.decide_by, now, tz), action, kind, area=i.area, decide_by_at=i.decide_by,  # type: ignore[arg-type]
    )  # fmt: skip


def sort_rows(rows: Sequence[Row], tab: Tab, sort: Sort) -> list[Row]:
    """Time left (default): soonest clock first, so overdue rows lead. Decide by: earliest date first. Area: by
    area, then time left. Decided this week keeps the newest decision first, whatever the sort."""
    far = dt.datetime.max.replace(tzinfo=dt.UTC)
    if tab == "decided":
        return sorted(rows, key=lambda r: r.decided_at or far, reverse=True)
    if sort == "area":
        return sorted(rows, key=lambda r: (r.area.lower(), r.due_at or far))
    if sort == "decide_by":
        return sorted(rows, key=lambda r: (r.decide_by_at or far, r.due_at or far))
    return sorted(rows, key=lambda r: r.due_at or far)


_WORDS = ("No", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten")


def _word(n: int) -> str:
    return _WORDS[n] if n < len(_WORDS) else str(n)


def summary(ideas: Sequence[DeskIdea], now: dt.datetime, decided_days: int) -> str:
    """S-R1.layout/1: '3 waiting on colleagues. One is overdue and one has under a day left. 2 answered and back
    with you.' With nothing waiting or answered it says how many are to review."""
    tabs = [(i, tab_of(i, now, decided_days)) for i in ideas]
    waiting = [i for i, t in tabs if t == "waiting"]
    answered = sum(1 for _, t in tabs if t == "answered")
    to_review = sum(1 for _, t in tabs if t == "to_review")
    parts: list[str] = []
    if waiting:
        parts.append(f"{len(waiting)} waiting on {'a colleague' if len(waiting) == 1 else 'colleagues'}.")
        late = sum(1 for i in waiting if i.questions and overdue(i.questions, now))
        close = sum(
            1
            for i in waiting
            if i.questions and i.questions.due_at and not overdue(i.questions, now)
            and countdown(i.questions.due_at, now).variant == "warn"
        )  # fmt: skip
        clauses = []
        if late:
            clauses.append(f"{_word(late)} {'is' if late == 1 else 'are'} overdue")
        if close:
            first = not clauses
            w = _word(close) if first else _word(close).lower()
            clauses.append(f"{w} {'has' if close == 1 else 'have'} under a day left")
        if clauses:
            parts.append(" and ".join(clauses) + ".")
    if answered:
        parts.append(f"{answered} answered and back with you.")
    if not parts:
        return (
            f"{to_review} {'idea' if to_review == 1 else 'ideas'} to review."
            if to_review
            else "Nothing to review."
        )
    return " ".join(parts)


def counts(ideas: Sequence[DeskIdea], now: dt.datetime, decided_days: int) -> dict[str, int]:
    out: dict[str, int] = dict.fromkeys(TABS, 0)
    for i in ideas:
        t = tab_of(i, now, decided_days)
        if t:
            out[t] += 1
    return out
