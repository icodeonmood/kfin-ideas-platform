"""The six parts of a draft (L-DRAFT.parts), as plain rules: which parts a new message could change, how a
person's own value is checked, the "why" line under a suggestion, the receipt after a run and the next prompts.
No database and no model here, so all of it is unit-tested without the stack.

Stored per part (`idea_parts.value`, masked text only):
- `title`: {"title": str | None, "summary": str | None, "pinned": ["title" | "summary", …]} (the summary rides with
  the title, E-ENUMS.draft; each can be pinned on its own);
- `often`: str | None; `who`: [str]; `value`: [Brings]; `area`: str | None;
- `similar`: [SimilarMatch] | None (from L-SIMILAR).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from typing import Any

from draft.config import Option
from gateway import grounding
from onepc import enums

ROW_KEYS = ("title", "often", "who", "value", "area", "similar")  # idea_parts.key (E-ENUMS.draft)
WIRE_KEYS = ("title", "summary", "often", "who", "value", "area", "similar")  # Draft.parts on the wire
EDITABLE = ("title", "summary", "often", "who", "value", "area")
AGENT_PARTS = ("title", "often", "who", "value", "area")  # `similar` is L-SIMILAR's
LIMITS = {"title": 70, "summary": 600, "often": 120, "label": 60}
MAX_PICKS = 8

BRINGS = enums.BRINGS
BRINGS_LABELS = enums.labels("brings")
NOT_SURE = "not_sure"

# What makes a message touch "how often" or "what it's worth" (L-DRAFT.parts/4). A number alone does not: a masked
# detail ("Folio ••••89") or a branch code would re-run both on every message (BLD-C033). A number counts only with
# its unit ("3x", "50k", "2 lakh"); the words around it do the rest.
_FREQUENCY = re.compile(
    r"(?<![•\w])\d+\s*x\b|\b(?:daily|weekly|monthly|yearly|hourly|quarterly|annually|fortnightly|every|each|times?|"
    r"once|twice|often|always|usually|regularly|repeatedly|sometimes|per|day|days|week|weeks|month|months|quarter|"
    r"quarters|year|years|hour|hours|minutes?|roz|har|hafte|mahine)\b",
    re.I,
)
_WORTH = re.compile(
    r"(?<![•\w])\d+(?:\.\d+)?\s*(?:k|l|cr|lacs?)\b|₹|\b(?:rs|inr|rupees?|lakhs?|crores?|cost|costs|costly|money|"
    r"save|saves|saving|savings|time|hours?|minutes?|manual|manually|hand|re-?key|revenue|fee|fees|sell|paid|pay|"
    r"vendor|tool|tools|outside|third[- ]party|excel|effort)\b",
    re.I,
)
ORDINALS = ("first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth")


class PartValueError(ValueError):
    """A person's own value for a part is not usable. `code` and `field` go to the screen; never the value."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


# ---- which parts a message could change (L-DRAFT.parts/4) --------------------------------------------------------


def _mentions(text: str, cues: Iterable[str]) -> bool:
    folded = text.casefold()
    return any(re.search(r"(?<!\w)" + re.escape(c) + r"(?!\w)", folded) for c in cues if c)


def is_empty(row_key: str, value: Any) -> bool:
    if row_key == "title":
        v = value if isinstance(value, dict) else {}
        return not v.get("title") or not v.get("summary")
    return value in (None, "", [], {})


def pinned_fields(value: Any) -> set[str]:
    return set(value.get("pinned") or []) if isinstance(value, dict) else set()


def runnable(row_key: str, state: str, value: Any) -> bool:
    """A part the assistant may fill again: never one the person pinned (`L-DRAFT.pins`). The title row stays
    runnable while either the title or the summary is still the assistant's."""
    if row_key == "title":
        return not {"title", "summary"} <= pinned_fields(value)
    return state != "pinned"


def affected(
    text: str,
    current: dict[str, tuple[str, Any]],
    affects: Sequence[Option],
    areas: Sequence[Option],
) -> list[str]:
    """The parts a new message could change, in E-ENUMS.draft order. `current` is row key -> (state, value).
    A part that is still empty is always tried again (the new words may now support it); the title and summary
    always take in what the person added; the others only when the message touches what they are about."""
    touched = {
        "title": True,
        "often": bool(_FREQUENCY.search(text)),
        "who": _mentions(text, (c for o in affects for c in (*o.cues, o.label.casefold()))),
        "value": bool(_WORTH.search(text)),
        "area": _mentions(text, (c for o in areas for c in (*o.cues, o.label.casefold()))),
    }
    out = []
    for key in AGENT_PARTS:
        state, value = current.get(key, ("waiting", None))
        if not runnable(key, state, value):
            continue
        if touched[key] or is_empty(key, value) or state == "failed":
            out.append(key)
    return out


# ---- a person's own value ("Your call", L-DRAFT.pins) -------------------------------------------------------------


def _text(value: Any, limit: int, *, optional: bool = False) -> str | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        if optional:
            return None
        raise PartValueError("value_required")
    if not isinstance(value, str):
        raise PartValueError("value_invalid")
    cleaned = " ".join(value.split())
    if len(cleaned) > limit:
        raise PartValueError("too_long")
    return cleaned


def _labels(value: Any) -> list[str]:
    if not isinstance(value, list) or not value or len(value) > MAX_PICKS:
        raise PartValueError("value_required" if value in (None, []) else "value_invalid")
    out: list[str] = []
    for item in value:
        label = _text(item, LIMITS["label"])
        assert label is not None
        if label.casefold() not in {x.casefold() for x in out}:
            out.append(label)
    return out


def clean_value(wire_key: str, value: Any) -> Any:
    """The person's value for one part, checked and tidied (whitespace), or PartValueError. Text is masked by the
    caller before it is stored (DEC-103)."""
    if wire_key in ("title", "summary"):
        return _text(value, LIMITS[wire_key])
    if wire_key == "often":
        return _text(value, LIMITS["often"], optional=True)
    if wire_key == "who":
        return _labels(value)
    if wire_key == "area":
        return _text(value, LIMITS["label"])
    if wire_key == "value":
        if not isinstance(value, list) or not value:
            raise PartValueError("value_required")
        picked = [v for v in BRINGS if v in value]  # the enum's order, no repeats
        if len(picked) != len(set(value)) or any(not isinstance(v, str) for v in value):
            raise PartValueError("value_invalid")
        if NOT_SURE in picked and len(picked) > 1:
            picked = [NOT_SURE]  # "not sure yet" clears the others (V-FIELDS.checkit/3)
        return picked
    raise PartValueError("not_editable")


# ---- the "why" under a suggestion (L-DRAFT.parts rule 2) ----------------------------------------------------------


def sentences(texts: Sequence[str]) -> list[str]:
    """Every sentence of the person's words, in order. "Rs." or "e.g." does not end one (`grounding`'s rule)."""
    return [piece for text in texts for piece in grounding.split_sentences(text)]


def still_said(quote: str | None, texts: Sequence[str]) -> bool:
    """Whether a part's source quote still stands word for word in the person's words (an edit may have taken it
    out). A part with no quote has nothing to re-check."""
    if not quote:
        return True
    needle = f" {grounding.normalise(quote)} "
    return needle.strip() != "" and any(needle in f" {grounding.normalise(t)} " for t in texts)


def blank(row_key: str, value: Any) -> bool:
    """An answer that says nothing new: empty, or only "not sure yet" for what it's worth."""
    return is_empty(row_key, value) or (row_key == "value" and value == [NOT_SURE])


def landing(
    row_key: str, value: Any, prior: Any, prior_quote: str | None, texts: Sequence[str], *, dropped: bool
) -> str:
    """How one answer lands on its part (L-DRAFT.parts/4, "unchanged parts keep their value"; BLD-C033):
    - `keep`: the part goes back to what it showed (or `failed`, "Add it yourself", when it showed nothing): the
      gateway dropped an answer the words did not back, or the answer is empty while the part's own value still
      stands in the words;
    - `failed`: dropped, and what the part showed is no longer in the words (an edit took it out): emptied;
    - `waiting`: nothing in the words backs the part, and nothing it showed still stands ("Waiting for your words");
    - `filled`: the new answer."""
    stands = not blank(row_key, prior) and still_said(prior_quote, texts)
    if dropped:
        return "keep" if stands or blank(row_key, prior) else "failed"
    if blank(row_key, value):
        if stands:
            return "keep"
        return "filled" if row_key == "value" and value == [NOT_SURE] else "waiting"
    return "filled"


def from_sentence(quote: str, texts: Sequence[str]) -> str:
    """ "From your first sentence." for the sentence of the person's words the quote sits in."""
    needle = f" {grounding.normalise(quote)} "
    for i, s in enumerate(sentences(texts)):
        if needle.strip() and needle in f" {grounding.normalise(s)} ":
            return f"From your {ORDINALS[i]} sentence." if i < len(ORDINALS) else "From your words."
    return "From your words."


def said(quotes: Sequence[str]) -> str:
    """ "“about 40 calls a day” and “5 to 10 minutes each”": the first two quotes, as the boards join them."""
    return " and ".join(f"“{q}”" for q in quotes[:2])


def quoted(quotes: Sequence[str]) -> str:
    return "From your words: " + said(quotes)


_QUOTE = re.compile(r"“([^”]+)”")


def quotes_in(line: str) -> list[str]:
    """The quotes in a line `quoted` made ("From your words: “a” and “b”" gives ["a", "b"]), as they stand: the
    masked copy, never unmasked."""
    return _QUOTE.findall(line)


def because(reason: str | None, quotes: Sequence[str]) -> str:
    """ "Suggested because you mentioned investors and the branch." (Compose.md); with no reason, the quotes:
    "Suggested because you said “about 40 calls a day” and “5 to 10 minutes each”." (Review.md, BLD-C194)."""
    r = (reason or "").strip().rstrip(".")
    r = re.sub(r"^(?:suggested\s+)?because\s+", "", r, flags=re.I)
    if not r:
        r = f"you said {said(quotes)}" if quotes else "of your words"
    return f"Suggested because {lower_first(r)}."


def why_for(
    row_key: str, value: Any, quotes: Sequence[str], reason: str | None, texts: Sequence[str]
) -> str | None:
    if is_empty(row_key, value) and row_key != "title":
        return None
    if row_key == "title":
        return from_sentence(quotes[0], texts) if quotes else None
    if row_key == "often":
        return quoted(quotes) if quotes else None
    if row_key in ("who", "area"):
        return because(reason, quotes)
    if row_key == "value":
        return None if value == [NOT_SURE] or not quotes else quoted(quotes)
    return None


# ---- the receipt after a run (L-DRAFT.parts rule 8, C-DRAFT-PANEL.behaviour/5) --------------------------------------


def lower_first(label: str) -> str:
    """ "Investors" -> "investors", but "KFin teams" and "AMCs" keep their capitals."""
    return label[:1].lower() + label[1:] if label[1:2].islower() else label


def joined(items: Sequence[str]) -> str:
    items = list(items)
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def hidden_line(masked: Sequence[str]) -> str | None:
    n = len(masked)
    if n == 0:
        return None
    noun = "personal detail" if n == 1 else "personal details"
    return f"Hid {n} {noun} from everyone but you: {', '.join(masked)}."


def receipt(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    hidden_masked: Sequence[str] = (),
    similar_found: int = 0,
    ready: bool = False,
    all_failed: bool = False,
    email: bool = False,
) -> list[str]:
    """What changed, in plain sentences, in the board's words. `before` and `after` are row key -> stored value."""
    lines: list[str] = []
    if email:
        lines.append("Turned your email into a draft. Nothing has been sent.")
    if all_failed:
        lines.append("We couldn't build the draft just now. Your words are saved. Try again.")
    t_before = (before.get("title") or {}).get("title") if isinstance(before.get("title"), dict) else None
    t_after = (after.get("title") or {}).get("title") if isinstance(after.get("title"), dict) else None
    if t_after and t_after != t_before:
        lines.append(f"Drafted a title: “{t_after}”.")
    area, who = after.get("area"), after.get("who") or []
    if (area, who) != (before.get("area"), before.get("who") or []) and (area or who):
        if area and who:
            lines.append(f"Sorted it under {area}, affecting {joined([lower_first(w) for w in who])}.")
        elif area:
            lines.append(f"Sorted it under {area}.")
        else:
            lines.append(f"Noted who it affects: {joined([lower_first(w) for w in who])}.")
    often = after.get("often")
    if often and often != before.get("often"):
        lines.append(f"Noted how often: {lower_first(often)}.")
    worth = after.get("value") or []
    if worth and worth != (before.get("value") or []):
        lines.append(f"Marked it as {joined([lower_first(BRINGS_LABELS.get(b, b)) for b in worth])}.")
    line = hidden_line(hidden_masked)
    if line:
        lines.append(line)
    if similar_found:
        noun = "similar idea" if similar_found == 1 else "similar ideas"
        lines.append(f"Found {similar_found} {noun} from colleagues. You can team up on the next step.")
    if ready:
        lines.append("Your draft is ready. Add a detail, or check it.")
    return lines


def suggestions(after: dict[str, Any]) -> list[str]:
    """Up to two next prompts (L-DRAFT.parts rule 8)."""
    out = []
    if not after.get("often"):
        out.append("Say how often it happens")
    if not after.get("who"):
        out.append("Say who feels it most")
    out.append("Add what you already tried")
    got = after.get("title")
    title: dict[str, Any] = got if isinstance(got, dict) else {}
    if title.get("title") and "title" not in pinned_fields(title):
        out.append("Change the title")
    return out[:2]


INTERVIEW = (
    "How often does it happen?",
    "Who feels it most?",
    "Any rough size?",
)  # L-DRAFT.parts rule 10 (S1)
