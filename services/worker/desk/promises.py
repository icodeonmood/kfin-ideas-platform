"""The numbers the product promises (`P-PRODUCT.promises`) that the review side uses.

The pack requires these to change without a release (README §8). Every lane B module reads them through `get()`,
so the store behind it can change in one place. The store is the company repo's `rules/promises.md` (lane A,
BLD-A181). The built-in defaults below are the pack's values, used only when that rule is not there (unit tests,
and `main` until BLD-A181 lands). Validation limits that are not business promises (the longest reason, question
or note, from V-FIELDS) stay here.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

ANSWER_TIMES = ("1d", "3d", "1w")
RETURN_IN = ("1m", "3m", "6m")


@dataclass(frozen=True)
class Promises:
    review_working_days: int = 5  # L-REVIEW.clock/1: decide within 5 working days of sharing
    deadline_hour: int = 18  # L-QUESTIONS.clock/5: deadlines fall at 6 pm office time on the due day
    answer_days: tuple[tuple[str, int], ...] = (("1d", 1), ("3d", 3), ("1w", 7))
    answer_default: str = "3d"
    reminders_before_hours: tuple[int, ...] = (24, 2)  # L-QUESTIONS.clock/2
    give_more_days: int = 2  # "Give 2 more days"
    reason_min: int = 30  # L-DECIDE.rules/1
    reason_max: int = 1000  # V-FIELDS.review/5
    question_max: int = 300  # V-FIELDS.review/1
    answer_max: int = 2000  # V-FIELDS.answer/1
    reversal_note_min: int = 30  # L-COMMITTEE.rules/3
    reversal_note_max: int = 1000  # V-FIELDS.committee/2
    merge_note_min: int = 20  # L-MERGE.desk/2
    merge_note_max: int = 600  # V-FIELDS.review/10
    worth_note_max: int = 280  # V-FIELDS.review/8
    window_days: int = 30  # L-COMMITTEE.rules/1
    window_extend_days: int = 30  # L-COMMITTEE.rules/2
    window_max_months: int = 3  # L-COMMITTEE.rules/2
    return_months: tuple[tuple[str, int], ...] = (("1m", 1), ("3m", 3), ("6m", 6))
    return_default: str = "3m"
    team_by_working_days: int = 10  # L-DECIDE.rules/6
    decided_this_week_days: int = 7  # L-REVIEW.queue: "Decided this week"

    def answer_days_for(self, time_to_answer: str) -> int:
        return dict(self.answer_days)[time_to_answer]

    def return_months_for(self, return_in: str) -> int:
        return dict(self.return_months)[return_in]


DEFAULTS = Promises()


def _from_rule(base: Promises, data: dict[str, Any]) -> Promises:
    """Lane A's `rules/promises.md` (BLD-A181) mapped onto the fields lane B uses. The three answer times and
    the three return periods keep their contract codes ('1d', '3d', '1w'; '1m', '3m', '6m') in order; their
    lengths come from the rule."""
    q, notes, window = data.get("questions", {}), data.get("notes", {}), data.get("committee_window", {})
    not_now = data.get("not_now", {})
    changes: dict[str, Any] = {}
    if "decide_by_working_days" in data.get("review", {}):
        changes["review_working_days"] = int(data["review"]["decide_by_working_days"])
    if "answer_options_days" in q:
        changes["answer_days"] = tuple(
            zip(ANSWER_TIMES, (int(d) for d in q["answer_options_days"]), strict=True)
        )
    if "answer_default_days" in q:
        days = dict((d, code) for code, d in changes.get("answer_days", base.answer_days))
        changes["answer_default"] = days[int(q["answer_default_days"])]
    if "deadline_hour" in q:
        changes["deadline_hour"] = int(q["deadline_hour"])
    if "reminder_hours_before" in q:
        changes["reminders_before_hours"] = tuple(int(h) for h in q["reminder_hours_before"])
    for key, name in (
        ("decision_reason_min_chars", "reason_min"),
        ("reversal_note_min_chars", "reversal_note_min"),
        ("merge_note_min_chars", "merge_note_min"),
    ):
        if key in notes:
            changes[name] = int(notes[key])
    for key, name in (
        ("days", "window_days"),
        ("extend_by_days", "window_extend_days"),
        ("max_months", "window_max_months"),
    ):
        if key in window:
            changes[name] = int(window[key])
    if "return_options_months" in not_now:
        changes["return_months"] = tuple(
            zip(RETURN_IN, (int(m) for m in not_now["return_options_months"]), strict=True)
        )
    if "return_default_months" in not_now:
        months = dict((m, code) for code, m in changes.get("return_months", base.return_months))
        changes["return_default"] = months[int(not_now["return_default_months"])]
    if "working_days" in data.get("team_by", {}):
        changes["team_by_working_days"] = int(data["team_by"]["working_days"])
    return replace(base, **changes)


def get() -> Promises:
    """The promises in force: the pack's defaults, overridden by the company repo's `promises` rule if it exists."""
    from core.config import get_settings
    from rules.loader import RULE_PATHS, load_rule

    if "promises" not in RULE_PATHS:  # no store yet: the pack's values stand
        return DEFAULTS
    try:
        data = load_rule(get_settings().company_repo_path, "promises").data
    except Exception as exc:  # a missing file falls back; a broken one must not pass silently
        if "missing" in str(exc):
            return DEFAULTS
        raise
    return _from_rule(DEFAULTS, dict(data or {}))
