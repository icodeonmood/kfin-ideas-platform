"""What an idea is worth, and the reviewer's revision (L-WORTH, C-WORTH, E-ENTITIES `Worth` and `Range`).

Four measures, any mix: hours a month, cost a month, revenue a month, and reliance on outside tools. Figures are
read in any Indian form with the platform's one quantity reader (`gateway.grounding.quantities`: 1,20,000, 2.5
lakh, 5L, 1.2 crore, 25k, ranges) and written back in one normal form. A reviewer's revision never overwrites the
sharer's figures: both are kept, and the reviewer's tiles show what each was (L-WORTH/3).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from desk.decide import FieldError
from gateway.grounding import quantities

Measure = Literal["hours_month", "cost_month", "revenue_month"]
MEASURES: tuple[Measure, ...] = ("hours_month", "cost_month", "revenue_month")
OutsideTools = Literal["none", "partly", "fully"]
OUTSIDE_TOOLS: dict[str, str] = {
    "none": "No change",
    "partly": "Partly less reliance",
    "fully": "Fully less reliance",
}
TILE_LABELS: dict[str, str] = {
    "hours_month": "Time saved",
    "cost_month": "Cost saved",
    "revenue_month": "Revenue",
    "outside_tools": "Outside tools",
}
KIND_LABELS: dict[str, str] = {"problem": "A problem to fix", "business_idea": "A new business idea"}
NOT_GIVEN = "Not given"
INVALID = "Write a figure or a range."
TOO_BIG = "That figure is too large. Check it and write it again."
# Below the columns' limits (idea_worth: hours numeric(12,2), rupees numeric(14,2)), with room for the rounding.
LIMITS: dict[str, float] = {"hours_month": 1e9, "cost_month": 1e11, "revenue_month": 1e11}
_ABOUT = re.compile(r"\b(?:about|around|approx(?:imately)?|roughly|nearly|almost)\b|~", re.I)


@dataclass(frozen=True)
class Range:
    low: float
    high: float | None
    text: str  # "70 to 150 hours a month"

    def as_json(self) -> dict[str, Any]:
        return {"low": self.low, "high": self.high, "text": self.text}


def _number(n: float) -> str:
    return f"{n:g}" if n != int(n) else str(int(n))


def inr(n: float) -> str:
    """Rupees with Indian grouping: '₹25,000', '₹1,20,000', '₹12,50,00,000'."""
    whole = str(round(n))
    if len(whole) <= 3:
        return f"₹{whole}"
    head, tail = whole[:-3], whole[-3:]
    groups: list[str] = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return f"₹{','.join(groups)},{tail}"


def inr_short(n: float) -> str:
    """Rupees in summaries: lakh and crore once they reach them ('₹2.5 lakh', '₹1.2 crore'), else in full."""
    for size, word in ((1e7, "crore"), (1e5, "lakh")):
        if n >= size:
            return f"₹{round(n / size, 2):g} {word}"
    return inr(n)


def _text(measure: Measure, low: float, high: float | None, about: bool) -> str:
    if measure == "hours_month":
        amount = _number(low) if high is None else f"{_number(low)} to {_number(high)}"
        unit = "hour" if high is None and low == 1 else "hours"
        words = f"{amount} {unit} a month"
    else:
        amount = inr(low) if high is None else f"{inr(low)} to {inr(high)}"
        words = f"{amount} a month"
    return f"about {words}" if about and high is None else words


def parse(measure: Measure, raw: Any) -> Range | None:
    """One measure from what was typed. Blank is None (all measures are optional); anything that is not text, not
    one figure or a range of two, or past the measure's limit raises `WorthInvalid`."""
    if raw is not None and not isinstance(raw, str):
        raise WorthInvalid(measure)  # a number, list or object where the typed words belong
    text = (raw or "").strip()
    if not text:
        return None
    found = [q.value for q in quantities(text)]
    if not found or len(found) > 2 or any(v < 0 for v in found):
        raise WorthInvalid(measure)
    if any(not v <= LIMITS[measure] for v in found):  # `not <=` also catches nan
        raise WorthInvalid(measure, TOO_BIG)
    low, high = (found[0], None) if len(found) == 1 or found[0] == found[1] else sorted(found)
    return Range(low, high, _text(measure, low, high, bool(_ABOUT.search(text))))


class WorthInvalid(ValueError):
    def __init__(self, measure: str, message: str = INVALID) -> None:
        super().__init__(measure)
        self.error = FieldError("worth_invalid", measure, message)


@dataclass(frozen=True)
class Worth:
    hours_month: Range | None = None
    cost_month: Range | None = None
    revenue_month: Range | None = None
    outside_tools: OutsideTools | None = None

    def as_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {m: r.as_json() for m in MEASURES if (r := getattr(self, m)) is not None}
        if self.outside_tools is not None:
            out["outside_tools"] = self.outside_tools
        return out

    @classmethod
    def from_json(cls, data: dict[str, Any] | None) -> Worth:
        data = data or {}
        ranges = {
            m: Range(float(r["low"]), None if r.get("high") is None else float(r["high"]), str(r["text"]))
            for m in MEASURES
            if (r := data.get(m))
        }
        tools = data.get("outside_tools")
        return cls(**ranges, outside_tools=tools if tools in OUTSIDE_TOOLS else None)


def read_revision(fields: dict[str, Any], note: str | None, note_max: int) -> tuple[Worth, list[FieldError]]:
    """The reviewer's editor (C-WORTH.edit): three figure fields, outside tools and an optional note.
    Returns the revised worth and any field errors (V-FIELDS.review/7–8)."""
    errors: list[FieldError] = []
    ranges: dict[str, Range | None] = {}
    for m in MEASURES:
        try:
            ranges[m] = parse(m, fields.get(m))
        except WorthInvalid as exc:
            errors.append(exc.error)
    raw_tools = fields.get("outside_tools")
    tools: Any = raw_tools if isinstance(raw_tools, str) and raw_tools in OUTSIDE_TOOLS else None
    if raw_tools is not None and tools is None:  # a list or object is unhashable: checked as text first
        errors.append(FieldError("outside_tools_invalid", "outside_tools", "Choose None, Partly or Fully."))
    if note is not None and len(note.strip()) > note_max:
        errors.append(FieldError("note_too_long", "note", f"Keep the note under {note_max} characters."))
    return Worth(**ranges, outside_tools=tools), errors


@dataclass(frozen=True)
class Tile:
    measure: str
    label: str
    value: str
    was: str | None  # "was 70 to 150 hours a month", on a tile the reviewer changed
    changed: bool


def _shown(w: Worth | None, measure: str) -> str:
    if w is None:
        return OUTSIDE_TOOLS["none"] if measure == "outside_tools" else NOT_GIVEN
    if measure == "outside_tools":
        return OUTSIDE_TOOLS[w.outside_tools or "none"]
    r = getattr(w, measure)
    return NOT_GIVEN if r is None else str(r.text)


def tiles(sharer: Worth, reviewer: Worth | None) -> list[Tile]:
    """The four tiles of C-WORTH.view. With a revision, the reviewer's figures show and a changed tile carries
    the sharer's original (L-WORTH/3); the revised figures are the ones that count (L-WORTH/5)."""
    out: list[Tile] = []
    for measure in (*MEASURES, "outside_tools"):
        mine, theirs = _shown(sharer, measure), _shown(reviewer, measure) if reviewer else None
        changed = theirs is not None and theirs != mine
        out.append(
            Tile(measure, TILE_LABELS[measure], theirs if theirs is not None else mine,
                 f"was {mine}" if changed else None, changed)
        )  # fmt: skip
    return out


def counted(sharer: Worth, reviewer: Worth | None) -> Worth:
    """L-WORTH/5: what the decision, the Wall and impact comparison use."""
    return reviewer if reviewer is not None else sharer
