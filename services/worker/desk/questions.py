"""Questions from the review desk, and answers (L-QUESTIONS, C-QCARD, E-ENTITIES.review `QuestionSet`).

This part holds the rules that need no database: the six parts a question is pinned to, guessing the part from
the wording, the suggestions drawn from the idea's gaps, the checks on a set and on the answers, the set's state,
and the words the desk, the panel and the card show. Storing and sending a set is added once the cut-over's
tables exist.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from desk import when
from desk.clock import countdown
from desk.decide import FieldError
from desk.promises import ANSWER_TIMES, Promises

Part = Literal["summary", "often", "who", "cost", "evidence", "fix"]
PARTS: tuple[Part, ...] = (
    "summary",
    "often",
    "who",
    "cost",
    "evidence",
    "fix",
)  # E-ENUMS.part, in the idea's order
PART_NAMES: dict[str, str] = {
    "summary": "The problem",
    "often": "How often",
    "who": "Who it affects",
    "cost": "What it's worth",
    "evidence": "Attached",
    "fix": "Fix",
}
SetState = Literal["queued", "sent", "seen", "partly_answered", "answered", "closed"]

# L-QUESTIONS.ask/2: the part is guessed from the wording and can be changed before adding. Each list holds the
# words that point to a part; the part with the most hits wins, The problem when nothing points anywhere.
_CUES: dict[str, tuple[str, ...]] = {
    "often": (r"how often", r"how many times", r"\bevery (?:day|week|month)\b", r"\b(?:a|per) (?:day|week|month)\b",
              r"\bdaily\b", r"\bweekly\b", r"\bmonthly\b", r"\bfrequen", r"\bworse\b", r"\bmonth end\b"),
    "who": (r"\bwho\b", r"\bwhich (?:customers|investors|distributors|teams?|branch(?:es)?)\b", r"\binvestors\b",
            r"\bdistributors\b", r"\bhit hardest\b", r"\baffect"),
    "cost": (r"\bworth\b", r"\bcost", r"\bsav(?:e|es|ing|ings)\b", r"\bhow long\b", r"\bhours?\b", r"₹",
             r"\brupees\b", r"\brevenue\b", r"\blakh\b", r"\bcrore\b", r"\bmoney\b"),
    "evidence": (r"\bscreenshots?\b", r"\battach", r"\bfiles?\b", r"\bupload", r"\bphotos?\b", r"\bsample\b",
                 r"\blogs?\b", r"\bcopy of\b", r"\bdocument"),
    "fix": (r"\bfix", r"\bsolv", r"\bsolution\b", r"\bwhat would help\b", r"\binstead\b", r"\bchange\b"),
}  # fmt: skip


def guess_part(text: str) -> Part:
    """The part a reviewer's question most likely belongs to ('Pinned to The problem' when unsure)."""
    low = text.lower()
    best: tuple[int, Part] = (0, "summary")
    for part in PARTS[1:]:
        hits = sum(1 for cue in _CUES[part] if re.search(cue, low))
        if hits > best[0]:
            best = (hits, part)
    return best[1]


# L-QUESTIONS.ask/3, with AI drafting off (D1): one question per part from the boards, and a sharper one where the
# idea leaves the part empty. A model-written suggestion replaces these once `ai.all` is on.
_GENERIC: dict[str, str] = {
    "summary": "Can you give one recent example, with the date?",
    "often": "Is it getting worse, better or about the same?",
    "who": "Which customers or teams are hit hardest?",
    "cost": "Roughly how long does one case take your team?",
    "evidence": "Can you add a screenshot or a file that shows it, with customer details hidden?",
    "fix": "Have you seen this solved anywhere, in KFin or outside?",
}
_GAP: dict[str, str] = {
    "often": "How often does this happen: a few times a day, a week or a month?",
    "who": "Who does this affect most: investors, distributors or a KFin team?",
    "cost": "Roughly how long does one case take your team?",
    "evidence": "Can you add a screenshot or a file that shows it, with customer details hidden?",
}


@dataclass(frozen=True)
class Suggestion:
    part: Part
    text: str
    gap: bool  # the idea leaves this part empty


def suggestions(filled: dict[str, bool], asked: Sequence[str] = ()) -> list[Suggestion]:
    """Suggested questions, one per part: the idea's gaps first, then the rest in the idea's order. A question
    already queued or asked is not suggested again. `filled` says which parts the idea has something in."""
    taken = {a.strip().lower() for a in asked}
    gaps = [Suggestion(p, _GAP[p], True) for p in PARTS if p in _GAP and not filled.get(p, False)]
    rest = [Suggestion(p, _GENERIC[p], False) for p in PARTS if p not in {g.part for g in gaps}]
    return [s for s in gaps + rest if s.text.lower() not in taken]


def first_for(part: Part, filled: dict[str, bool], asked: Sequence[str] = ()) -> Suggestion | None:
    """S-R2.rules/2: 'Ask about this' on a part queues that part's first suggestion."""
    return next((s for s in suggestions(filled, asked) if s.part == part), None)


def check_set(
    questions: Sequence[dict[str, Any]], time_to_answer: str | None, p: Promises
) -> list[FieldError]:
    """V-FIELDS.review/1–2: at least one question, each with text up to the limit and pinned to a part."""
    errors: list[FieldError] = []
    if not questions:
        errors.append(FieldError("no_questions", "questions", "Add a question first."))
    for i, q in enumerate(questions):
        text = str(q.get("text") or "").strip()
        if not text:
            errors.append(FieldError("question_empty", f"questions.{i}.text", "Write the question first."))
        elif len(text) > p.question_max:
            errors.append(
                FieldError(
                    "question_too_long", f"questions.{i}.text", f"Keep it under {p.question_max} characters."
                )
            )
        if q.get("part") not in PARTS:
            errors.append(FieldError("part_required", f"questions.{i}.part", "Choose the part it is about."))
    if time_to_answer is not None and time_to_answer not in ANSWER_TIMES:
        errors.append(
            FieldError("time_to_answer_invalid", "time_to_answer", "Choose 1 day, 3 days or 1 week.")
        )
    return errors


def check_answer(text: str | None, p: Promises) -> list[FieldError]:
    """V-FIELDS.answer/1: optional per question, up to 2,000 characters."""
    if text is not None and len(text.strip()) > p.answer_max:
        return [FieldError("answer_too_long", "text", f"Keep your answer under {p.answer_max:,} characters.")]
    return []


@dataclass(frozen=True)
class SetFacts:
    """What the words are made from: one question set as stored."""

    count: int
    answered: int
    sent_at: dt.datetime | None
    seen_at: dt.datetime | None
    due_at: dt.datetime | None
    answered_at: dt.datetime | None  # when the last answer was sent
    closed: bool = False


def state(f: SetFacts) -> SetState:
    """L-QUESTIONS.states. `overdue` is a flag beside the state (`overdue()`), not a state of its own."""
    if f.closed:
        return "closed"
    if f.sent_at is None:
        return "queued"
    if f.answered >= f.count:
        return "answered"
    if f.answered:
        return "partly_answered"
    return "seen" if f.seen_at else "sent"


def overdue(f: SetFacts, now: dt.datetime) -> bool:
    return state(f) in ("sent", "seen", "partly_answered") and f.due_at is not None and now >= f.due_at


def _answered_all(n: int) -> str:
    return {1: "Answered", 2: "Both answered"}.get(n) or f"All {n} answered"


def desk_line(
    f: SetFacts | None, now: dt.datetime, *, decided: bool = False, tz: dt.tzinfo = when.IST
) -> str:
    """The desk's Questions column (S-R1): 'No questions asked', 'Not seen yet', '0 of 3 answered, seen 12:05 pm',
    '1 of 2 answered', 'Both answered, 1 hour ago', 'Answered yesterday, 6:10 pm'; on Decided this week without
    the time: '1 question, answered', 'Both answered'."""
    if f is None or f.sent_at is None:
        return "No questions asked"
    s = state(f)
    if s == "answered" or (s == "closed" and f.answered >= f.count):
        if decided:
            return "1 question, answered" if f.count == 1 else _answered_all(f.count)
        when_ = when.since(f.answered_at, now, tz) if f.answered_at else None
        if when_ is None:
            return _answered_all(f.count)
        joiner = " " if f.count == 1 else ", "
        return f"{_answered_all(f.count)}{joiner}{when_}"
    if f.answered:
        return f"{f.answered} of {f.count} answered"
    if f.seen_at is None:
        return "Not seen yet"
    if decided:
        return f"0 of {f.count} answered"
    seen = (
        when.clock(f.seen_at, tz)
        if when.which_day(f.seen_at, now, tz) == "today"
        else when.since(f.seen_at, now, tz)
    )
    return f"0 of {f.count} answered, seen {seen}"


def plural(n: int, word: str) -> str:
    return f"{n} {word}{'s' * (n != 1)}"


def ready_line(n: int) -> str:
    """The Ask section's header once questions are queued: '2 questions ready'."""
    return f"{plural(n, 'question')} ready"


def send_label(n: int, sharer_first_name: str) -> str:
    """'Send 3 questions to Kavya'."""
    return f"Send {plural(n, 'question')} to {sharer_first_name}"


def deadline_line(
    sharer_first_name: str, due_at: dt.datetime, now: dt.datetime, tz: dt.tzinfo = when.IST
) -> str:
    """'Kavya has until Thursday 19 November, 6 pm.' (shown before sending)."""
    return f"{sharer_first_name} has until {when.deadline(due_at, now, tz)}."


AFTER_DECIDE_BY = "That's after you decide, so you'd need to move your date."


def spare_line(answered_at: dt.datetime, due_at: dt.datetime, tz: dt.tzinfo = when.IST) -> str:
    """'Answered with 3 days to spare'; under a day in hours; after the deadline, how late."""
    c = countdown(due_at, answered_at, tz)
    if c.overdue:
        return f"Answered {c.count} after the deadline"
    if c.variant == "warn":
        hours = c.seconds // 3600
        amount = plural(hours, "hour") if hours else plural(max(1, c.seconds // 60), "minute")
        return f"Answered with {amount} to spare"
    return f"Answered with {c.count} to spare"


def send_answers_label(n_answered: int, reviewer_first_name: str) -> str:
    """S-R3 Checking: 'Send 1 answer to Meera'; with none answered the button is disabled and says so."""
    if n_answered < 1:
        return "Answer at least one question"
    return f"Send {plural(n_answered, 'answer')} to {reviewer_first_name}"
