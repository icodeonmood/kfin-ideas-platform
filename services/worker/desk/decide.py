"""Decisions: Pick, Not now, Not picked (L-DECIDE), and the committee's reversal checks (L-COMMITTEE.rules/3).

This part holds the rules that need no database: what a decision must carry, the messages a field shows, the
wording check, and the dates a decision sets. Writing a decision is added once the cut-over's tables exist.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from typing import Literal

from desk import clock, when
from desk.promises import RETURN_IN, Promises
from desk.window import add_months

Choice = Literal["pick", "not_now", "not_picked"]
CHOICES: tuple[Choice, ...] = ("pick", "not_now", "not_picked")
LABELS: dict[str, str] = {"pick": "Picked", "not_now": "Not now", "not_picked": "Not picked"}
STATUS_AFTER: dict[str, str] = {"pick": "picked", "not_now": "not_now", "not_picked": "not_picked"}
# The reason field's question follows the choice (L-DECIDE.rules/1).
REASON_LABELS: dict[str, str] = {
    "pick": "Why are you picking it?",
    "not_now": "Why not now, and what would change it?",
    "not_picked": "Why isn’t it going ahead?",
}


@dataclass(frozen=True)
class FieldError:
    """A-API.conventions/2: `message` is ready to show under the field named by `field`."""

    code: str
    field: str
    message: str


def _length(text: str) -> int:
    return len(text.strip())


def check_decision(
    choice: str | None, reason: str | None, return_in: str | None, sharer_first_name: str, p: Promises
) -> list[FieldError]:
    """V-FIELDS.review/4–6. An empty list means the decision can be sent."""
    errors: list[FieldError] = []
    if choice not in CHOICES:
        errors.append(FieldError("choice_required", "choice", "Choose Pick, Not now or Not picked first."))
    n = _length(reason or "")
    if n < p.reason_min:
        errors.append(
            FieldError(
                "reason_too_short",
                "reason",
                f"Give {sharer_first_name} a reason of at least a line, {p.reason_min} characters or more.",
            )
        )
    elif n > p.reason_max:
        errors.append(
            FieldError("reason_too_long", "reason", f"Keep the reason under {p.reason_max:,} characters.")
        )
    if choice == "not_now" and return_in is not None and return_in not in RETURN_IN:
        errors.append(FieldError("return_in_invalid", "return_in", "Choose when it comes back."))
    return errors


def check_reversal(
    to: str | None, original: str, note: str | None, return_in: str | None, p: Promises
) -> list[FieldError]:
    """V-FIELDS.committee/1–2: one of the two other decisions, and a note of a line or more."""
    errors: list[FieldError] = []
    if to not in CHOICES or to == original:
        errors.append(FieldError("to_required", "to", "Choose what to change it to."))
    n = _length(note or "")
    if n < p.reversal_note_min:
        errors.append(
            FieldError(
                "note_too_short",
                "note",
                f"Write a note of at least a line, {p.reversal_note_min} characters or more.",
            )
        )
    elif n > p.reversal_note_max:
        errors.append(
            FieldError("note_too_long", "note", f"Keep the note under {p.reversal_note_max:,} characters.")
        )
    if to == "not_now" and return_in is not None and return_in not in RETURN_IN:
        errors.append(FieldError("return_in_invalid", "return_in", "Choose when it comes back."))
    return errors


def counter(text: str, sharer_first_name: str, p: Promises) -> str:
    """The line under the reason: '12 of at least 30 characters', then '{sharer} reads this word for word.'"""
    n = _length(text)
    if n < p.reason_min:
        return f"{n} of at least {p.reason_min} characters"
    return f"{sharer_first_name} reads this word for word."


# L-DECIDE.rules/4 and F-COPY: words the product never uses to a sharer, with a plainer way to say it.
_WORDING: tuple[tuple[str, str], ...] = (
    (r"\bduplicates?\b", "say it is the same problem as another idea, and name it"),
    (r"\brejected\b", "say it is not going ahead, and why"),
    (r"\balready solved\b", "say what already fixes it, and where"),
    (r"\bappeals?\b", "say the Ones Committee can review the decision"),
    (r"\binvalid\b", "say what is missing"),
)


@dataclass(frozen=True)
class WordingNote:
    word: str
    suggestion: str


def wording_check(reason: str) -> list[WordingNote]:
    """Warn, never block: the reason is the reviewer's own (`NOT DRAWN:` default of L-DECIDE.rules/4)."""
    notes: list[WordingNote] = []
    for pattern, suggestion in _WORDING:
        m = re.search(pattern, reason, flags=re.IGNORECASE)
        if m:
            notes.append(WordingNote(m.group(0), suggestion))
    return notes


def return_at(decided_at: dt.datetime, return_in: str, p: Promises) -> dt.datetime:
    """L-DECIDE.rules/7: Not now comes back after 1, 3 or 6 months."""
    return add_months(decided_at, p.return_months_for(return_in))


@dataclass(frozen=True)
class DecisionDates:
    return_at: dt.datetime | None
    team_by: dt.datetime | None


def dates_for(choice: Choice, decided_at: dt.datetime, return_in: str | None, p: Promises,
              cal: clock.Calendar) -> DecisionDates:  # fmt: skip
    """What a decision schedules: Not now's return date, Pick's team-by date."""
    if choice == "not_now":
        return DecisionDates(return_at(decided_at, return_in or p.return_default, p), None)
    if choice == "pick":
        return DecisionDates(None, clock.team_by(decided_at, p, cal))
    return DecisionDates(None, None)


def return_words(t: dt.datetime, sharer_first_name: str, now: dt.datetime, tz: dt.tzinfo = when.IST) -> str:
    """'Comes back to you and Kavya on Tuesday 16 February 2027' (the reviewer's line)."""
    return f"Comes back to you and {sharer_first_name} on {when.day(t, now, tz)}"
