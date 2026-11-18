"""Only the person's own words (DEC-095), plus a fixed list of basic assumptions (DEC-097).

Every answer `canvas-assist` suggests carries, in `evidence`, the exact words from the person's input it came from,
and the gateway checks each quote against what was sent. A suggested figure must be one of the person's own numbers,
or follow from their numbers by multiplying and dividing with the basic assumptions the output lists in
`assumptions` (only those in the company repo's rules, `thresholds.md` key `assumptions`, sent to the agent as its
`assumptions` block) and plain unit factors (60 minutes in an hour).

`ungrounded` names what fails, by field path and a reason code (never the text). The gateway sends those problems
back on its one re-ask (BLD-158); if the second answer still fails only here, `repair` drops just those suggestions
and the scan carries on. A dropped field stays empty, except:

- `one_line` becomes the person's own first sentence (or first words), trimmed to 20 words, offered as a
  suggestion backed by itself; with no usable words it is left empty;
- `kind` becomes "problem" ("A problem I face", DEC-097) with no provenance: the platform's default, not a guess;
- `neutral_summary` becomes "", and every reader shows a neutral placeholder instead (BLD-C022, BLD-C027);
- a listed assumption that is not on the list, or that no figure uses, is removed;
- the no-answer values ("not sure yet", "don't know") need no quote, because they say nothing.

Quotes may come only from the person's own text: the free-text answers in `canvas_answers`, the references they
gave, and digests of their clean files, each piece on its own (a quote never joins two answers). Never from past
corrections (other people's words), the taxonomy or the gatekeeper block.
"""

from __future__ import annotations

import copy
import math
import re
import unicodedata
from dataclasses import dataclass
from itertools import combinations, product
from typing import Any

from pii.tagger import TAG_RE

ESTIMATES = (
    "hours_saved_per_month",
    "inr_saved_per_year",
    "inr_revenue_one_time",
    "inr_revenue_per_year",
    "clients_who_would_pay",
)
NUMERIC_ESTIMATES = tuple(f"value.estimate.{k}" for k in ESTIMATES)
# Answers the assistant may suggest when the person left them empty. Each needs a quote.
SUGGESTIBLE = (
    "kind",
    "one_line",
    "who.segments",
    "who.frequency_or_reach",
    "who.today_alternative",
    "value.category",
    "value.play",
    *NUMERIC_ESTIMATES,
    "value.estimate.note",
    "value.basis",
    "ecosystem.solved_elsewhere",
    "ecosystem.our_advantage",
    "solution.approach",
    "solution.needs",
    "solution.risks",
)
# Values that mean "the person did not say": the schema needs a value, and they claim nothing.
NO_ANSWER = {"value.category": "not_sure", "ecosystem.solved_elsewhere": "dont_know"}
DEFAULT_KIND = (
    "problem"  # with no provenance: the platform's default when the kind cannot be backed (DEC-097)
)
# The person's own free text, in canvas_answers. Enum answers are not quotable.
SOURCE_FIELDS = (
    "one_line",
    "details",
    "who.frequency_or_reach",
    "who.today_alternative",
    "value.estimate.note",
    "ecosystem.our_advantage",
    "solution.approach",
    "solution.needs",
    "solution.risks",
)
# Sentences whose numbers must all appear in their quotes (a figure in prose is a claim).
PROSE = (
    "one_line",
    "neutral_summary",
    "who.frequency_or_reach",
    "who.today_alternative",
    "ecosystem.our_advantage",
    "solution.approach",
    "solution.needs",
    "solution.risks",
)
MAX_QUOTES = 3
FIRST_SENTENCE_WORDS = 20
MINUTES_PER_HOUR = 60.0  # a unit, not an assumption: never listed, and only minutes into hours
MAX_QUOTED = 10  # the person's quantities considered for one figure, in the order they wrote them
MINUTE_UNITS = frozenset({"minute", "minutes", "min", "mins"})
# Number words that never count as a quantity the person stated: "one analyst", "a team", "half the day" say how
# the work is done, not how much (BLD-C042).
NOT_OPERANDS = frozenset({"zero", "one", "a", "an", "half", "single"})
# How each figure may be worked (BLD-C043). The person's quantities always multiply; an assumption only in the
# direction its unit allows; at most `max` numbers in all. Division by the person's own numbers only for a count, and
# only when the note shows it.
FIELD_RULES: dict[str, dict[str, Any]] = {
    "value.estimate.hours_saved_per_month": {
        "max": 4, "minutes": True, "count": False, "default": (1,),
        "signs": {"working_days_per_month": (1,), "working_hours_per_day": (1,), "months_per_year": (-1,)},
    },
    "value.estimate.inr_saved_per_year": {
        "max": 4, "minutes": False, "count": False, "default": (1,),
        "signs": {"working_days_per_month": (1,), "working_hours_per_day": (1,), "months_per_year": (1,)},
    },
    "value.estimate.inr_revenue_per_year": {
        "max": 4, "minutes": False, "count": False, "default": (1,),
        "signs": {"working_days_per_month": (1,), "working_hours_per_day": (1,), "months_per_year": (1,)},
    },
    "value.estimate.inr_revenue_one_time": {"max": 4, "minutes": False, "count": False, "default": (), "signs": {}},
    "value.estimate.clients_who_would_pay": {
        "max": 3, "minutes": False, "count": True, "default": (), "signs": {"months_per_year": (1,)},
    },
}  # fmt: skip
ASSUMPTION_ID = re.compile(r"^[a-z][a-z0-9_]{0,40}$")
STOPWORDS = frozenset(
    re.findall(
        r"\S+",
        "a an and are as at be been being by can could did do does for from get gets got has have how i in is it its "
        "just my no not of on or our so some such that the their them then there they this those to too us very was "
        "we were what when which who will with would you your all also any each every many more much same "
        "hai hain ka ke ki ko se mein me aur bhi to ye yeh wo woh nahi na",
    )
)
# Words too general to say anything on their own: "the team", "our process" back nothing (BLD-C047).
GENERIC_NOUNS = frozenset(
    re.findall(
        r"\S+",
        "team teams people person persons work works process processes issue issues problem problems thing things "
        "time staff data system systems stuff task tasks job jobs way ways everyone someone everything something",
    )
)

# Sent back to the model on the re-ask: field paths and rules only, never text (checks.py convention).
MESSAGES = {
    "no_quote": "needs `evidence`: 1 to 3 exact quotes from the person's own text that support it, or leave it null",
    "not_found": "a quote in `evidence` is not word for word in one of the person's answers; copy one continuous "
    "phrase from a single answer exactly (no ellipses, no joining), or leave the field null",
    "too_short": "each quote in `evidence` must be at least two words and say something (not just 'of the')",
    "no_figure": "an estimate needs a quote that holds a quantity the person stated (not 'one' or 'a'), or leave "
    "it null",
    "new_number": "holds a number that is neither the person's own nor worked from their numbers and the "
    "assumptions you list (multiply their quantities; use each assumption only to turn their unit into the field's "
    "unit); use only their figures and the allowed assumptions, or leave it null",
    "not_marked": "you added this answer, so mark its provenance `suggested` and give `evidence`, or leave it empty",
    "not_given": "may only hold references the person gave; return the person's list unchanged",
    "stray_evidence": "`evidence` is only for answers you suggested and for neutral_summary; remove this key",
    "unknown_assumption": "is not one of the allowed assumptions in <assumptions>; remove it and any figure that needs it",
    "assumption_words": "copy the assumption's `says` exactly as given in <assumptions>",
    "unused_assumption": "no suggested figure uses this assumption; list only the assumptions your figures use",
}

_INVISIBLE = dict.fromkeys(map(ord, "​‌‍⁠﻿­"), None)  # ZWSP, ZWNJ, ZWJ, …
_PUNCT = str.maketrans({"–": "-", "—": "-", "‑": "-", "‘": "'", "’": "'", "“": '"', "”": '"'})
_EDGE_MARKS = "\"'.,;:!?…()[]{}<>*/\\|`~-"
_CURRENCY = re.compile(r"(?:\b(?:rs|inr)\b\.?|₹)\s*", re.I)
_MONTHS = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*"
# Numbers that are never quantities: dates, times, ordinals, financial years, years after a cue, references.
_NOT_QUANTITIES = (
    re.compile(r"\b\d{1,4}[/-]\d{1,2}[/-]\d{1,4}\b"),
    re.compile(r"\b\d{1,2}[:.]\d{2}\s*(?:am|pm)\b|\b\d{1,2}:\d{2}\b|\b\d{1,2}\s*(?:am|pm)\b", re.I),
    re.compile(
        rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+{_MONTHS}\b(?:,?\s*\d{{4}})?|\b{_MONTHS}\s+\d{{1,4}}(?:st|nd|rd|th)?\b"
        r"(?:,?\s*\d{4})?",
        re.I,
    ),
    re.compile(r"\b\d+(?:st|nd|rd|th)\b", re.I),
    re.compile(r"\bfy\s*'?\d{2,4}(?:\s*-\s*\d{2,4})?\b|\b(?:19|20)\d{2}\s*-\s*\d{2,4}\b", re.I),
    re.compile(r"\b(?:in|since|from|till|until|by|year|during|before|after)\s+(?:19|20)\d{2}\b", re.I),
    re.compile(
        r"(?:\bno\.|\bnos\.|#|\bref\.?|\bid\b|\bticket\b|\bsr\.?|\bfolio\b|\barn\b|\beuin\b)\s*[:#-]?\s*"
        r"[\w/-]*\d[\w/-]*",
        re.I,
    ),
)
_QTY_EDGES = "\"'.,;:!?…()[]{}<>*`~"
_DIGITS = re.compile(r"^(?:\d{1,3}(?:,\d{2,3})+|\d+)(?:\.\d+)?$")  # "2,3" is not a number (BLD-C046)
_SUFFIXED = re.compile(r"^(\d+(?:\.\d+)?)(k|l|lakhs?|lacs?|cr|crores?)$", re.I)  # 5L, 1.5k, 2cr
_RANGE = re.compile(r"^(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)$")  # 1-2 (days)
_MULTIPLIER = {
    "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5, "l": 1e5, "crore": 1e7, "crores": 1e7, "cr": 1e7,
    "k": 1e3, "thousand": 1e3, "million": 1e6, "hundred": 100.0,
}  # fmt: skip
_SMALL = re.findall(
    r"\S+",
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
    "seventeen eighteen nineteen twenty",
)
_WORD_NUMBERS = {
    **{w: float(i) for i, w in enumerate(_SMALL)},
    "thirty": 30.0, "forty": 40.0, "fifty": 50.0, "sixty": 60.0, "seventy": 70.0, "eighty": 80.0,
    "ninety": 90.0, "hundred": 100.0, "thousand": 1000.0, "dozen": 12.0, "half": 0.5,
}  # fmt: skip
_END = re.compile(r"[.!?।](?=\s|$)")  # a sentence end, the Devanagari danda included
_ABBREVIATIONS = frozenset(
    re.findall(
        r"\S+", "rs e.g eg i.e ie no nos mr mrs ms dr st sr jr vs etc approx dept govt co ltd pvt inc fig ref"
    )
)


def _get(node: Any, path: str) -> Any:
    for key in path.split("."):
        node = node.get(key) if isinstance(node, dict) else None
    return node


def _set(node: dict[str, Any], path: str, value: Any) -> None:
    keys = path.split(".")
    for key in keys[:-1]:
        nxt = node.get(key)
        if not isinstance(nxt, dict):
            nxt = {}
            node[key] = nxt
        node = nxt
    node[keys[-1]] = value


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


# ---- text ------------------------------------------------------------------------------------------------------


def _prepare(text: str) -> str:
    """NFC, no zero-width joiners or soft hyphens (Hindi typing varies there), plain dashes and quote marks."""
    return unicodedata.normalize("NFC", text).translate(_INVISIBLE).translate(_PUNCT).replace(" ", " ")


def tokens(text: str) -> list[str]:
    """Words for comparison: case folded and stripped of edge punctuation; tags kept whole and exact."""
    spaced = TAG_RE.sub(lambda m: f" {m.group(0)} ", _prepare(text))
    out = []
    for raw in spaced.split():
        if TAG_RE.fullmatch(raw):
            out.append(raw)
            continue
        word = raw.strip(_EDGE_MARKS).casefold()
        if word:
            out.append(word)
    return out


def normalise(text: str) -> str:
    return " ".join(tokens(text))


def source_pieces(sent: dict[str, Any]) -> list[str]:
    """The person's own words, one piece per answer, reference or digest, as the model saw them (tagged)."""
    answers = sent.get("canvas_answers") or {}
    pieces = [str(_get(answers, p)) for p in SOURCE_FIELDS if isinstance(_get(answers, p), str)]
    eco = answers.get("ecosystem") or {}
    pieces += [
        str(r.get("value")) for r in eco.get("references") or [] if isinstance(r, dict) and r.get("value")
    ]
    pieces += [
        str(a.get("digest"))
        for a in answers.get("attachments") or []
        if isinstance(a, dict) and isinstance(a.get("digest"), str)
    ]
    for block in ("details_text", "attachment_digests"):  # optional blocks in config; plain text or digests
        value = sent.get(block)
        if isinstance(value, str):
            pieces.append(value)
        elif isinstance(value, list):
            pieces += [
                str(v.get("digest") if isinstance(v, dict) else v)
                for v in value
                if isinstance(v, str) or (isinstance(v, dict) and isinstance(v.get("digest"), str))
            ]
    return [p for p in pieces if p.strip()]


def source_text(sent: dict[str, Any]) -> str:
    return "\n".join(source_pieces(sent))


def _padded(pieces: list[str]) -> list[str]:
    return [f" {normalise(p)} " for p in pieces]


def _found(quote: str, padded: list[str]) -> bool:
    """Word for word inside one piece, on word boundaries."""
    needle = f" {normalise(quote)} "
    return needle.strip() != "" and any(needle in piece for piece in padded)


def trivial(quote: str) -> bool:
    """Under two words, or nothing in it but stopwords and general nouns ("the team", "our process"), BLD-C047."""
    words = tokens(quote)
    if len(words) < 2:
        return True
    return all(w in STOPWORDS or w in GENERIC_NOUNS for w in words)


# ---- numbers -----------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Quantity:
    """A quantity the person stated: its value, the word after it (its unit, case folded) and how it was written."""

    value: float
    unit: str
    in_words: bool


def quantities(text: str) -> list[Quantity]:
    """The quantities a text states, in order. Digits in Indian forms (₹ and Rs. dropped; 1,20,000, 5 lakh, 5L, 2
    crore, 1.5k read; 1-2 read as both). Number words only in a quantity phrase ("ten people", "two hours", "five
    lakh"), and never "one", "a", "half" and the like. Never a date, time, ordinal, financial year, a year after
    "in" or "since", a reference after "No." or "ticket", a number with a leading zero or eight digits or more."""
    clean = _CURRENCY.sub(" ", TAG_RE.sub(" ", _prepare(text)))
    for pattern in _NOT_QUANTITIES:
        clean = pattern.sub(" ", clean)
    words: list[str] = []
    for raw in clean.split():
        word = raw.strip(_QTY_EDGES)
        parts = word.casefold().split("-")
        if len(parts) == 2 and all(x in _WORD_NUMBERS for x in parts):
            words += parts  # "twenty-five" reads as "twenty five"
        elif word:
            words.append(word)
    out: list[Quantity] = []
    i = 0
    while i < len(words):
        word, low = words[i], words[i].casefold()
        nxt = words[i + 1].casefold() if i + 1 < len(words) else ""
        values: list[float] = []
        used = 1
        in_words = False
        if _DIGITS.match(word):
            digits = word.replace(",", "")
            if not (re.match(r"^0\d", digits) or ("," not in word and len(digits.split(".")[0]) >= 8)):
                values = [float(digits)]
                if nxt in _MULTIPLIER and nxt != "l":
                    values, used = [values[0] * _MULTIPLIER[nxt]], 2
        elif m := _SUFFIXED.match(word):
            values = [float(m.group(1)) * _MULTIPLIER[m.group(2).casefold()]]
        elif m := _RANGE.match(word):
            values = [float(m.group(1)), float(m.group(2))]
        elif low in _WORD_NUMBERS:
            in_words = True
            values, used = _word_quantity(words, i)
        if values:
            unit = words[i + used].casefold() if i + used < len(words) else ""
            out += [Quantity(v, unit, in_words) for v in values]
        i += used
    return out


_TENS = frozenset({"twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"})
_UNITS = frozenset({"one", "two", "three", "four", "five", "six", "seven", "eight", "nine"})


def _word_quantity(words: list[str], i: int) -> tuple[list[float], int]:
    """A number in words starting at `i`, and how many words it takes. "twenty five" is 25, "two hundred" is 200,
    "five lakh" is 500,000; each word is read once. It counts only before a multiplier or a noun (a quantity
    phrase), and "one", "a", "half" and the like on their own never do (BLD-C042, BLD-C058)."""
    low = [w.casefold() for w in words]
    value, j = _WORD_NUMBERS[low[i]], i + 1
    if low[i] in _TENS and j < len(low) and low[j] in _UNITS:
        value, j = value + _WORD_NUMBERS[low[j]], j + 1
    multiplied = False
    while j < len(low) and low[j] in _MULTIPLIER and low[j] != "l":
        value, j, multiplied = value * _MULTIPLIER[low[j]], j + 1, True
    nxt = low[j] if j < len(low) else ""
    if not multiplied and (j == i + 1 and low[i] in NOT_OPERANDS):
        return [], j - i
    if multiplied or (nxt and nxt not in STOPWORDS and nxt not in _WORD_NUMBERS):
        return [value], j - i
    return [], j - i


def numbers(text: str) -> set[float]:
    return {q.value for q in quantities(text)}


def _close(value: float, result: float) -> bool:
    """Rounding to the field's natural precision (whole hours, rupees, clients), else within 0.5%."""
    if float(value).is_integer():
        return abs(value - result) <= 0.5
    return abs(value - result) <= 0.005 * abs(result)


def _division_shown(note: Any) -> bool:
    return isinstance(note, str) and bool(re.search(r"÷|\s/\s|\bdivided\b|\bper\s+(?:client|person)\b", note))


def _solve(
    value: Any,
    quoted: list[Quantity],
    assumed: dict[str, float],
    field: str = "value.estimate.hours_saved_per_month",
    division_shown: bool = False,
) -> tuple[set[str], list[float]] | None:
    """The assumption IDs a figure needs, and the factors it multiplies (BLD-C058), if it follows from what the person stated (BLD-C042, C043); None if not.

    It must be one of their quantities as it stands, or their quantities multiplied together (each once, at least
    one that is not 1), times or divided by allowed assumptions only in the direction the field's unit allows, and
    divided by 60 only from minutes into hours. Never below 1, never from assumptions alone or assumptions times 1.
    A count (clients) takes at most three numbers and divides by one of theirs only if the note shows it."""
    rules = FIELD_RULES.get(field)
    if rules is None or not isinstance(value, int | float) or isinstance(value, bool) or value < 1:
        return None
    if rules["count"] and not float(value).is_integer():
        return None
    theirs = [q for q in quoted if q.value > 0][:MAX_QUOTED]
    if not any(q.value != 1 for q in theirs):
        return None
    for q in theirs:
        if q.value != 1 and _close(float(value), q.value):
            return set(), [q.value]
    extras: list[tuple[str | None, float, tuple[int, ...]]] = []
    for aid, v in sorted(assumed.items()):
        signs = rules["signs"].get(aid, rules["default"])
        if v > 0 and signs:
            extras.append((aid, v, signs))
    if rules["minutes"] and any(q.unit in MINUTE_UNITS for q in theirs):
        extras.append((None, MINUTES_PER_HOUR, (-1,)))
    quoted_signs = (1, -1) if rules["count"] and division_shown else (1,)
    for n_extra in range(len(extras) + 1):
        for chosen in combinations(extras, n_extra):
            for n_theirs in range(1, rules["max"] - n_extra + 1):
                for picked in combinations(theirs, n_theirs):
                    if not any(q.value != 1 for q in picked):
                        continue
                    for qs in product(quoted_signs, repeat=n_theirs):
                        if qs[0] < 0:
                            continue  # the first of their numbers leads; a count divides by a later one
                        for es in product(*(signs for _, _, signs in chosen)):
                            operands = [(q.value, s) for q, s in zip(picked, qs, strict=True)]
                            operands += [(v, s) for (_, v, _), s in zip(chosen, es, strict=True)]
                            factors = [x if s > 0 else 1 / x for x, s in operands]
                            result = math.prod(factors)
                            if result >= 1 and _close(float(value), result):
                                return {aid for aid, _, _ in chosen if aid is not None}, factors
    return None


def reproduces(
    value: Any,
    quoted: list[Quantity],
    assumed: dict[str, float],
    field: str = "value.estimate.hours_saved_per_month",
    division_shown: bool = False,
) -> set[str] | None:
    """The assumption IDs a figure needs, if it follows from what the person stated (see `_solve`); None if not."""
    solved = _solve(value, quoted, assumed, field, division_shown)
    return solved[0] if solved else None


def working_steps(factors: list[float]) -> set[float]:
    """Every product of some of a figure's factors: the intermediate results a note may show, in any order
    ("5 × 22 = 110, × 8 = 880"), BLD-C058."""
    return {math.prod(c) for n in range(1, len(factors) + 1) for c in combinations(factors, n)}


# ---- assumptions -------------------------------------------------------------------------------------------------


def allowed_assumptions(sent: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """The fixed list from the rules, as sent to the agent: {id: {value, says}}."""
    out: dict[str, dict[str, Any]] = {}
    for a in sent.get("assumptions") or []:
        if isinstance(a, dict) and isinstance(a.get("id"), str) and isinstance(a.get("value"), int | float):
            out[a["id"]] = {"value": float(a["value"]), "says": str(a.get("says") or "")}
    return out


def _listed(out: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """(problem key, item) for each listed assumption; the key is its ID when well formed, else its position."""
    items: list[Any] = out["assumptions"] if isinstance(out.get("assumptions"), list) else []
    keyed = []
    seen: set[str] = set()
    for i, a in enumerate(items):
        aid = a.get("id") if isinstance(a, dict) else None
        named = (
            isinstance(aid, str) and ASSUMPTION_ID.match(aid) and aid not in seen
        )  # a repeat goes by position
        key = f"assumptions.{aid}" if named else f"assumptions.{i}"
        if isinstance(aid, str):
            seen.add(aid)
        keyed.append((key, a if isinstance(a, dict) else {}))
    return keyed


# ---- the check ----------------------------------------------------------------------------------------------------


def _quote_problem(quotes: Any, padded: list[str]) -> str | None:
    if not isinstance(quotes, list) or not quotes or len(quotes) > MAX_QUOTES:
        return "no_quote"
    if not all(isinstance(q, str) and q.strip() for q in quotes):
        return "no_quote"
    if any(trivial(q) for q in quotes):
        return "too_short"
    if not all(_found(q, padded) for q in quotes):
        return "not_found"
    return None


def suggested_paths(sent: dict[str, Any], out: dict[str, Any]) -> list[str]:
    """Answers the assistant added (the person left them empty), plus neutral_summary when it has one."""
    answers = sent.get("canvas_answers") or {}
    provenance = _dict(out.get("provenance"))
    paths = []
    for path in SUGGESTIBLE:
        if not _empty(_get(answers, path)):
            continue  # the person's own answer: checks.canvas_assist makes sure it is copied unchanged
        got = _get(out, path)
        if _empty(got) or NO_ANSWER.get(path) == got:
            continue
        if path == "kind" and (
            sent.get("mode") == "attachment" or (got == DEFAULT_KIND and "kind" not in provenance)
        ):
            continue  # the platform's default kind, or a mode with no kind to suggest
        paths.append(path)
    if isinstance(out.get("neutral_summary"), str) and out["neutral_summary"].strip():
        paths.append("neutral_summary")
    return paths


def ungrounded(sent: dict[str, Any], out: dict[str, Any]) -> dict[str, str]:
    """Field path (or `assumptions.<id>`) -> reason code, for everything not backed by the person's own words."""
    padded = _padded(source_pieces(sent))
    evidence = _dict(out.get("evidence"))
    provenance = _dict(out.get("provenance"))
    answers = sent.get("canvas_answers") or {}
    allowed = allowed_assumptions(sent)
    listed = _listed(out)
    assumed = {
        a["id"]: allowed[a["id"]]["value"]
        for _, a in listed
        if isinstance(a.get("id"), str) and a["id"] in allowed
    }
    bad: dict[str, str] = {}
    used: set[str] = set()
    paths = suggested_paths(sent, out)
    figures: set[float] = (
        set()
    )  # the person's figures behind every suggested estimate, for the note's working
    minutes = False  # whether any of them is in minutes (then the note may show the 60)
    steps: set[float] = set()  # intermediate results of every figure's working
    note = _get(out, "value.estimate.note")
    for path in paths:
        if path != "neutral_summary" and provenance.get(path) != "suggested":
            bad[path] = "not_marked"
            continue
        quotes = evidence.get(path)
        code = _quote_problem(quotes, padded)
        if code:
            bad[path] = code
            continue
        joined = " ".join(str(q) for q in quotes or [])
        value = _get(out, path)
        if path in NUMERIC_ESTIMATES:
            theirs = quantities(joined)
            if not any(q.value != 1 for q in theirs):
                bad[path] = "no_figure"
                continue
            solved = _solve(value, theirs, assumed, path, _division_shown(note))
            if solved is None:
                bad[path] = "new_number"
                continue
            used |= solved[0]
            steps |= working_steps(solved[1])
            figures |= {q.value for q in theirs}
            minutes = minutes or any(q.unit in MINUTE_UNITS for q in theirs)
        elif path in PROSE and isinstance(value, str) and not numbers(value) <= numbers(joined):
            bad[path] = "new_number"
    if "value.estimate.note" in paths and "value.estimate.note" not in bad and isinstance(note, str):
        own = numbers(" ".join(evidence.get("value.estimate.note") or []))
        results = {
            float(v) for p in NUMERIC_ESTIMATES if p not in bad and isinstance(v := _get(out, p), int | float)
        }
        units = {MINUTES_PER_HOUR} if minutes else set()
        allowed_numbers = own | figures | results | set(assumed.values()) | units
        if any(n not in allowed_numbers and not any(_close(n, x) for x in steps) for n in numbers(note)):
            bad["value.estimate.note"] = "new_number"
    if _empty(_get(answers, "ecosystem.references")) and not _empty(_get(out, "ecosystem.references")):
        bad["ecosystem.references"] = "not_given"
    for key in evidence:
        if key not in paths:
            bad.setdefault(key, "stray_evidence")
    for key, a in listed:
        aid = a.get("id")
        if not isinstance(aid, str) or aid not in allowed:
            bad[key] = "unknown_assumption"
        elif key != f"assumptions.{aid}" or aid not in used:
            bad[key] = "unused_assumption"  # a repeat (keyed by position) or one no figure needs
        elif a.get("says") != allowed[aid]["says"]:
            bad[key] = "assumption_words"
    return bad


def problems(sent: dict[str, Any], out: dict[str, Any]) -> list[str]:
    return [f"{path}: {MESSAGES[code]}" for path, code in sorted(ungrounded(sent, out).items())]


# ---- the repair ----------------------------------------------------------------------------------------------------


def sentence_ends(text: str) -> list[int]:
    """Where each sentence of `text` ends (just after its mark). A period after an abbreviation ("Rs.", "No.",
    "e.g.") does not end a sentence."""
    ends = []
    for m in _END.finditer(text):
        if text[m.start()] == ".":
            before = re.search(r"(\S+)$", text[: m.start()])
            word = before.group(1).casefold().lstrip("(\"'") if before else ""
            if word in _ABBREVIATIONS:
                continue
        ends.append(m.end())
    return ends


def split_sentences(text: str) -> list[str]:
    """The sentences of `text`, the words after the last mark included, by `sentence_ends`' rule (BLD-C033)."""
    out, start = [], 0
    for end in [*sentence_ends(text), len(text)]:
        piece = text[start:end].strip()
        if piece:
            out.append(piece)
        start = end
    return out


def first_sentence(details: str) -> tuple[str, str]:
    """The person's first sentence, as (one line, its quote): at most 20 words, with "…" when trimmed. A period after
    an abbreviation ("Rs.", "No.", "e.g.") does not end a sentence. A sentence under two words gives way to the
    first words of the text."""
    text = " ".join(details.split())
    end = next(iter(sentence_ends(text)), len(text))
    words = text[:end].split()
    if len(words) < 2:
        words = text.split()
    quote = " ".join(words[:FIRST_SENTENCE_WORDS])
    return (quote + "…" if len(words) > FIRST_SENTENCE_WORDS else quote), quote


def _empty_field(
    fixed: dict[str, Any], path: str, details: str, padded: list[str], answers: dict[str, Any]
) -> None:
    """What a field becomes when nothing of the person's backs it (BLD-C028, BLD-C056): empty, except the one line
    (the person's own first sentence, backed by itself, or ""), the kind (the default "problem", unclaimed), the
    no-answer values, and the neutral summary ("" and never the person's words)."""
    provenance: dict[str, Any] = fixed["provenance"]
    evidence: dict[str, Any] = fixed["evidence"]
    provenance.pop(path, None)
    evidence.pop(path, None)
    if path == "neutral_summary":
        fixed["neutral_summary"] = ""
    elif path == "one_line":
        line, quote = first_sentence(details)
        usable = bool(quote) and not trivial(quote) and _found(quote, padded)
        fixed["one_line"] = line if usable else ""
        if usable:
            provenance["one_line"] = "suggested"
            evidence["one_line"] = [quote]
    elif path == "kind":
        fixed["kind"] = DEFAULT_KIND  # no provenance: the platform's default, shown to nobody as a guess
    elif path in NO_ANSWER:
        _set(fixed, path, NO_ANSWER[path])
    elif path in ("who.segments", "ecosystem.references"):
        _set(fixed, path, list(_get(answers, path) or []))
    else:
        _set(fixed, path, None)


def _drop(fixed: dict[str, Any], sent: dict[str, Any], path: str, code: str) -> None:
    if code == "stray_evidence":
        fixed["evidence"].pop(path, None)
        return
    if path == "kind" and sent.get("mode") == "attachment":
        fixed["evidence"].pop(path, None)
        fixed["provenance"].pop(path, None)
        return  # attachment mode keeps its kind
    answers = sent.get("canvas_answers") or {}
    _empty_field(fixed, path, str(answers.get("details") or ""), _padded(source_pieces(sent)), answers)


REPAIR_PASSES = 6
# Changes that mend without taking anything the person would see away: not counted as dropped (BLD-C048).
NOT_DROPS = frozenset({"assumption_words", "stray_evidence"})


def repair(sent: dict[str, Any], out: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Drop what `ungrounded` names, again until nothing is left to drop (a dropped figure can leave an assumption
    unused or a note unsupported). Returns the repaired output (the same object if nothing changed) and the paths
    dropped (IDs only). Corrected assumption words and removed stray evidence change the output but drop nothing."""
    fixed = copy.deepcopy(out)
    fixed["evidence"] = _dict(fixed.get("evidence"))
    fixed["provenance"] = _dict(fixed.get("provenance"))
    if not isinstance(fixed.get("assumptions"), list):
        fixed["assumptions"] = []
    dropped: list[str] = []
    changed = False
    allowed = allowed_assumptions(sent)
    for _ in range(REPAIR_PASSES):  # until nothing changes; `_repaired` validates the result again
        bad = ungrounded(sent, fixed)
        if not bad:
            break
        # Assumptions all at once (a position key would shift as items go): drop or correct their words.
        kept = []
        for key, a in _listed(fixed):
            if bad.get(key) == "assumption_words":
                kept.append({**a, "says": allowed[a["id"]]["says"]})
            elif key not in bad:
                kept.append(a)
        fixed["assumptions"] = kept
        for path, code in sorted(bad.items()):
            if not path.startswith("assumptions."):
                _drop(fixed, sent, path, code)
            changed = True
            if code not in NOT_DROPS:
                dropped.append(path)
    if not changed:
        return out, []
    return fixed, sorted(set(dropped))


# ---- after the person or the review desk changes the canvas -------------------------------------------------------


def _own_pieces(card: dict[str, Any]) -> list[str]:
    """The person's own text in a saved canvas: fields whose provenance is `submitter` (never a suggestion, not even
    an accepted one: that would back a suggestion with itself), references they gave and their clean files."""
    provenance = _dict(card.get("provenance"))
    pieces = [
        str(_get(card, p))
        for p in SOURCE_FIELDS
        if isinstance(_get(card, p), str) and (p == "details" or provenance.get(p) == "submitter")
    ]
    if provenance.get("ecosystem.references") == "submitter":
        pieces += [
            str(r.get("value"))
            for r in _get(card, "ecosystem.references") or []
            if isinstance(r, dict) and r.get("value")
        ]
    pieces += [
        str(x.get("digest"))
        for x in card.get("attachments") or []
        if isinstance(x, dict) and isinstance(x.get("digest"), str)
    ]
    return [p for p in pieces if p.strip()]


def still_backed(card: dict[str, Any], allowed_values: dict[str, float]) -> tuple[dict[str, Any], list[str]]:
    """After an edit (BLD-C045, BLD-C056): every quote checked again against the person's own text only. For any
    suggested or accepted field, quotes no longer found are dropped; a field left with none is emptied with its
    provenance (`_empty_field`: the one line and kind fallbacks, a blank neutral summary, never the person's words).
    A figure that no longer follows from its quotes goes too, and so does the note of a figure no longer there. The
    person's own answers are never touched; the assumptions kept are those a remaining figure needs. Returns the
    new canvas and the cleared paths."""
    fixed = copy.deepcopy(card)
    provenance = _dict(fixed.get("provenance"))
    old_evidence = _dict(fixed.get("evidence"))
    evidence: dict[str, Any] = {}
    fixed["provenance"], fixed["evidence"] = provenance, evidence
    padded = _padded(_own_pieces(fixed))
    cleared: list[str] = []
    for path, quotes in old_evidence.items():
        if provenance.get(path) == "submitter":
            continue  # the person's own answer
        kept = (
            [q for q in quotes if isinstance(q, str) and _found(q, padded)]
            if isinstance(quotes, list)
            else []
        )
        if kept:
            evidence[path] = kept
        elif path == "neutral_summary" or provenance.get(path) in ("suggested", "accepted"):
            _empty_field(fixed, path, str(fixed.get("details") or ""), padded, {})
            cleared.append(path)
    listed = [a for a in fixed.get("assumptions") or [] if isinstance(a, dict)]
    assumed = {a["id"]: allowed_values[a["id"]] for a in listed if a.get("id") in allowed_values}
    note = _get(fixed, "value.estimate.note")
    needed: set[str] = set()
    figures_left = False
    for path in NUMERIC_ESTIMATES:
        value = _get(fixed, path)
        if provenance.get(path) not in ("suggested", "accepted") or value is None:
            continue
        joined = " ".join(evidence.get(path) or [])
        need = reproduces(value, quantities(joined), assumed, path, _division_shown(note)) if joined else None
        if need is None:
            _set(fixed, path, None)
            provenance.pop(path, None)
            evidence.pop(path, None)
            cleared.append(path)
            continue
        needed |= need
        figures_left = True
    if not figures_left and provenance.get("value.estimate.note") in ("suggested", "accepted"):
        _set(fixed, "value.estimate.note", None)  # the working of a figure that is no longer there
        provenance.pop("value.estimate.note", None)
        evidence.pop("value.estimate.note", None)
        cleared.append("value.estimate.note")
    fixed["evidence"] = evidence
    fixed["provenance"] = provenance
    fixed["assumptions"] = [a for a in listed if a.get("id") in needed]
    return fixed, sorted(set(cleared))
