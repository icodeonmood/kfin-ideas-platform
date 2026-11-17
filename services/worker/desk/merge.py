"""The review desk merges two ideas (L-MERGE.desk, C-SHEET-MERGE): the rules that need no database.

Which idea leads by default, when a desk merge is allowed, the note's checks, and the sheet's and banner's words.
Writing the merge and its effects (L-MERGE.effects) is added once the cut-over's tables exist.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Literal

from desk import when
from desk.decide import FieldError
from desk.promises import Promises

Lead = Literal["this", "other"]
# An idea the desk has not decided can be merged into another; the lead can be undecided or already going ahead
# ("joined it with IDEA-… so one team builds one fix", L-MERGE.desk/5).
UNDECIDED = frozenset({"with_review_desk", "needs_you"})
CAN_LEAD = UNDECIDED | {"picked", "being_built"}


@dataclass(frozen=True)
class Side:
    """One idea in the sheet."""

    idea_id: str  # "IDEA-2026-001412"
    status: str
    shared_at: dt.datetime
    sharer_first_name: str
    crew_count: int


def default_lead(this: Side, other: Side) -> Lead:
    """L-MERGE.desk/2: the one shared first; if both were shared at the same moment, the larger crew; then the
    other idea, so the idea under review is the one that joins."""
    if this.shared_at != other.shared_at:
        return "this" if this.shared_at < other.shared_at else "other"
    return "this" if this.crew_count > other.crew_count else "other"


def refusal(this: Side, other: Side, lead: Lead) -> str | None:
    """Why this merge cannot happen, as an error code; None when it can.

    The idea that joins must be undecided; the lead must be undecided or going ahead; an idea is never merged
    with itself."""
    if this.idea_id == other.idea_id:
        return "same_idea"
    leader, joiner = (this, other) if lead == "this" else (other, this)
    if joiner.status not in UNDECIDED:
        return "already_decided" if joiner is this else "other_not_open"
    if leader.status not in CAN_LEAD:
        return "other_not_open" if leader is other else "already_decided"
    return None


def check_note(note: str | None, p: Promises) -> list[FieldError]:
    """V-FIELDS.review/10: a note to both, 20 characters or more."""
    n = len((note or "").strip())
    if n < p.merge_note_min:
        return [FieldError("note_too_short", "note", "Tell both why, in a line or two.")]
    if n > p.merge_note_max:
        return [FieldError("note_too_long", "note", f"Keep the note under {p.merge_note_max} characters.")]
    return []


def _shared(side: Side, now: dt.datetime, tz: dt.tzinfo) -> str:
    """'Shared Saturday' within the last week, else 'Shared 2 November'."""
    days = (now.astimezone(tz).date() - side.shared_at.astimezone(tz).date()).days
    if days == 0:
        return "Shared today"
    if 0 < days < 7:
        return f"Shared {when.DAYS[side.shared_at.astimezone(tz).weekday()]}"
    return f"Shared {when.short(side.shared_at, now, tz)}"


def _crew(side: Side) -> str:
    if side.crew_count <= 1:
        return f"just {side.sharer_first_name} so far"
    return f"{side.crew_count} on its crew"


@dataclass(frozen=True)
class SheetWords:
    title: str  # "Merge with IDEA-2026-001412?"
    line: str  # "Kavya’s idea joins Ravi’s. Both stay credited, …"
    this_option: tuple[str, str]  # ("Kavya’s leads, IDEA-2026-001481", "Shared Saturday, just Kavya so far")
    other_option: tuple[str, str]
    team_up: str  # "Kavya joins Ravi’s crew without a request. Both are told why."
    note_prefill: str
    small_print: str


NOTE_PREFILL = "You both raised the same problem. One team, one fix, with both your names on it."
SMALL_PRINT = "Both get it in their Inbox. The Ones Committee sees the merge for 30 days and can reverse it."


def sheet(this: Side, other: Side, lead: Lead, now: dt.datetime, tz: dt.tzinfo = when.IST) -> SheetWords:
    """C-SHEET-MERGE.anatomy, with the line following the choice of lead."""
    leader, joiner = (this, other) if lead == "this" else (other, this)
    return SheetWords(
        title=f"Merge with {other.idea_id}?",
        line=(
            f"{joiner.sharer_first_name}’s idea joins {leader.sharer_first_name}’s. Both stay credited, "
            "and from now on the review desk decides on one idea."
        ),
        this_option=(
            f"{this.sharer_first_name}’s leads, {this.idea_id}",
            f"{_shared(this, now, tz)}, {_crew(this)}",
        ),
        other_option=(
            f"{other.sharer_first_name}’s leads, {other.idea_id}",
            f"{_shared(other, now, tz)}, {_crew(other)}",
        ),
        team_up=f"{joiner.sharer_first_name} joins {leader.sharer_first_name}’s crew without a request. Both are told why.",
        note_prefill=NOTE_PREFILL,
        small_print=SMALL_PRINT,
    )


def banner(this: Side, other: Side, lead: Lead, team_up: bool) -> str:
    """C-SHEET-MERGE.after: the green banner on the Similar ideas card."""
    leader, joiner = (this, other) if lead == "this" else (other, this)
    crew = f" {joiner.sharer_first_name} is on {leader.sharer_first_name}’s crew." if team_up else ""
    return (
        f"Merged: {joiner.sharer_first_name}’s idea is now part of {leader.idea_id}, and both are credited.{crew} "
        "Both were told in their Inbox. The Ones Committee can reverse it within 30 days."
    )
