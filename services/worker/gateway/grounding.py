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
MIN_QUOTE_CHARS = 12  # a two-word quote shorter than this needs a word that is not a stopword
UNIT_FACTORS = (60.0,)  # minutes in an hour: a unit, not an assumption, so it is never listed
MAX_OPERANDS = 4  # numbers in one product or quotient, e.g. 2 hours × 10 people × 22 days
ASSUMPTION_ID = re.compile(r"^[a-z][a-z0-9_]{0,40}$")
STOPWORDS = frozenset(
    re.findall(
        r"\S+",
        "a an and are as at be by for from has have i in is it its my no not of on or our so that the their they "
        "this to us was we were with you your hai hain ka ke ki ko se mein me aur bhi to ye yeh wo woh nahi na",
    )
)

# Sent back to the model on the re-ask: field paths and rules only, never text (checks.py convention).
MESSAGES = {
    "no_quote": "needs `evidence`: 1 to 3 exact quotes from the person's own text that support it, or leave it null",
    "not_found": "a quote in `evidence` is not word for word in one of the person's answers; copy one continuous "
    "phrase from a single answer exactly (no ellipses, no joining), or leave the field null",
    "too_short": "each quote in `evidence` must be at least two words and say something (not just 'of the')",
    "no_figure": "an estimate needs a quote that holds the person's own figures, or leave it null",
    "new_number": "holds a number that is neither the person's own nor worked from their numbers and the "
    "assumptions you list; use only their figures and the allowed assumptions, or leave it null",
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
_NUMBER = re.compile(
    r"(?<![\d.,])(\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(?:\s*(lakhs?|lacs?|crores?|cr|k|thousand|million)\b)?",
    re.I,
)
_MULTIPLIER = {"lakh": 1e5, "lac": 1e5, "crore": 1e7, "cr": 1e7, "k": 1e3, "thousand": 1e3, "million": 1e6}
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
_HAS_FIGURE = re.compile(
    r"\d|\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|thirty|forty|fifty|"
    r"hundred|thousand|lakh|lakhs|crore|crores|dozen|half)\b",
    re.I,
)
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
    words = tokens(quote)
    if len(words) < 2:
        return True
    return len(" ".join(words)) < MIN_QUOTE_CHARS and all(w in STOPWORDS for w in words)


# ---- numbers -----------------------------------------------------------------------------------------------------


def numbers(text: str) -> set[float]:
    """Figures written in digits, Indian forms included: ₹ or Rs. dropped, 1,20,000 and 5 lakh or 2 crore read."""
    clean = _CURRENCY.sub(" ", TAG_RE.sub(" ", _prepare(text)))
    out = set()
    for digits, unit in _NUMBER.findall(clean):
        value = float(digits.replace(",", ""))
        if unit:
            key = unit.casefold().rstrip("s")
            value *= _MULTIPLIER.get(key, 1.0)
        out.add(value)
    return out


def _word_numbers(text: str) -> set[float]:
    """Small English number words ("ten people"), for estimates only: prose would read "one of" as a figure."""
    return {_WORD_NUMBERS[w] for w in tokens(text) if w in _WORD_NUMBERS}


def _close(value: float, result: float) -> bool:
    return abs(value - result) <= max(0.5, 0.01 * abs(result))


def reproduces(value: float, quoted: set[float], assumed: dict[str, float]) -> set[str] | None:
    """The assumption IDs a figure needs, if it is one of the person's numbers (none) or a product or quotient of
    their numbers, listed assumptions and unit factors (each used at most once, at least one of theirs, at most
    four in all). None when it does not follow."""
    q = sorted(x for x in quoted if x > 0)[:10]
    if value == 0:
        return set() if 0.0 in quoted else None
    if any(_close(value, x) for x in q):
        return set()
    listed = sorted((k, v) for k, v in assumed.items() if v > 0)
    for n_assumed in range(len(listed) + 1):
        for chosen in combinations(listed, n_assumed):
            for n_units in range(len(UNIT_FACTORS) + 1):
                for units in combinations(UNIT_FACTORS, n_units):
                    for n_quoted in range(1, MAX_OPERANDS - n_assumed - n_units + 1):
                        for theirs in combinations(q, n_quoted):
                            operands = [*theirs, *(v for _, v in chosen), *units]
                            for signs in product((1, -1), repeat=len(operands)):
                                result = math.prod(
                                    x if s > 0 else 1 / x for x, s in zip(operands, signs, strict=True)
                                )
                                if _close(value, result):
                                    return {k for k, _ in chosen}
    return None


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
    for i, a in enumerate(items):
        aid = a.get("id") if isinstance(a, dict) else None
        key = (
            f"assumptions.{aid}" if isinstance(aid, str) and ASSUMPTION_ID.match(aid) else f"assumptions.{i}"
        )
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
            if not _HAS_FIGURE.search(joined):
                bad[path] = "no_figure"
                continue
            theirs = numbers(joined) | _word_numbers(joined)
            need = reproduces(float(value), theirs, assumed) if isinstance(value, int | float) else None
            if need is None:
                bad[path] = "new_number"
                continue
            used |= need
            figures |= theirs
        elif path in PROSE and isinstance(value, str) and not numbers(value) <= numbers(joined):
            bad[path] = "new_number"
    note = _get(out, "value.estimate.note")
    if "value.estimate.note" in paths and "value.estimate.note" not in bad and isinstance(note, str):
        own = numbers(" ".join(evidence.get("value.estimate.note") or []))
        results = {
            float(v) for p in NUMERIC_ESTIMATES if p not in bad and isinstance(v := _get(out, p), int | float)
        }
        if not numbers(note) <= own | figures | results | set(assumed.values()) | set(UNIT_FACTORS):
            bad["value.estimate.note"] = "new_number"
    if _empty(_get(answers, "ecosystem.references")) and not _empty(_get(out, "ecosystem.references")):
        bad["ecosystem.references"] = "not_given"
    for key in evidence:
        if key not in paths:
            bad.setdefault(key, "stray_evidence")
    seen: set[str] = set()
    for key, a in listed:
        aid = a.get("id")
        if not isinstance(aid, str) or aid not in allowed:
            bad[key] = "unknown_assumption"
        elif aid in seen or aid not in used:
            bad[key] = "unused_assumption"
        elif a.get("says") != allowed[aid]["says"]:
            bad[key] = "assumption_words"
        if isinstance(aid, str):
            seen.add(aid)
    return bad


def problems(sent: dict[str, Any], out: dict[str, Any]) -> list[str]:
    return [f"{path}: {MESSAGES[code]}" for path, code in sorted(ungrounded(sent, out).items())]


# ---- the repair ----------------------------------------------------------------------------------------------------


def first_sentence(details: str) -> tuple[str, str]:
    """The person's first sentence, as (one line, its quote): at most 20 words, with "…" when trimmed. A period after
    an abbreviation ("Rs.", "No.", "e.g.") does not end a sentence. A sentence under two words gives way to the
    first words of the text."""
    text = " ".join(details.split())
    end = len(text)
    for m in _END.finditer(text):
        if text[m.start()] == ".":
            before = re.search(r"(\S+)$", text[: m.start()])
            word = before.group(1).casefold().lstrip("(\"'") if before else ""
            if word in _ABBREVIATIONS:
                continue
        end = m.end()
        break
    words = text[:end].split()
    if len(words) < 2:
        words = text.split()
    quote = " ".join(words[:FIRST_SENTENCE_WORDS])
    return (quote + "…" if len(words) > FIRST_SENTENCE_WORDS else quote), quote


def _drop(fixed: dict[str, Any], sent: dict[str, Any], path: str, code: str) -> None:
    evidence: dict[str, Any] = fixed["evidence"]
    provenance: dict[str, Any] = fixed["provenance"]
    answers = sent.get("canvas_answers") or {}
    evidence.pop(path, None)
    if code == "stray_evidence":
        return
    provenance.pop(path, None)
    if path == "neutral_summary":
        fixed["neutral_summary"] = ""
    elif path == "one_line":
        line, quote = first_sentence(str(answers.get("details") or ""))
        usable = quote and not trivial(quote) and _found(quote, _padded(source_pieces(sent)))
        fixed["one_line"] = line if usable else ""
        if usable:
            provenance["one_line"] = "suggested"
            evidence["one_line"] = [quote]
    elif path == "kind":
        if sent.get("mode") != "attachment":
            fixed["kind"] = DEFAULT_KIND  # no provenance: the platform's default, shown to nobody as a guess
    elif path in NO_ANSWER:
        _set(fixed, path, NO_ANSWER[path])
    elif path in ("who.segments", "ecosystem.references"):
        _set(fixed, path, list(_get(answers, path) or []))
    else:
        _set(fixed, path, None)


def repair(sent: dict[str, Any], out: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Drop what `ungrounded` names, again until nothing is left to drop (a dropped figure can leave an assumption
    unused or a note unsupported). Returns the repaired output and the dropped paths (IDs only)."""
    fixed = copy.deepcopy(out)
    fixed["evidence"] = _dict(fixed.get("evidence"))
    fixed["provenance"] = _dict(fixed.get("provenance"))
    if not isinstance(fixed.get("assumptions"), list):
        fixed["assumptions"] = []
    dropped: list[str] = []
    allowed = allowed_assumptions(sent)
    for _ in range(4):
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
            dropped.append(path)
    if not dropped:
        return out, []
    return fixed, sorted(set(dropped))


# ---- after the person or the review desk changes the canvas -------------------------------------------------------


def still_backed(
    card: dict[str, Any], allowed_values: dict[str, float]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """After an edit: the evidence whose quotes are still in the person's words, and the listed assumptions that a
    remaining suggested figure still needs (BLD-C028). The card has the canvas_answers shape."""
    padded = _padded(source_pieces({"canvas_answers": card}))
    evidence = {
        path: quotes
        for path, quotes in _dict(card.get("evidence")).items()
        if isinstance(quotes, list)
        and quotes
        and all(isinstance(q, str) and _found(q, padded) for q in quotes)
    }
    provenance = _dict(card.get("provenance"))
    listed = [a for a in card.get("assumptions") or [] if isinstance(a, dict)]
    assumed = {a["id"]: allowed_values[a["id"]] for a in listed if a.get("id") in allowed_values}
    needed: set[str] = set()
    for path in NUMERIC_ESTIMATES:
        value = _get(card, path)
        if provenance.get(path) not in ("suggested", "accepted") or not isinstance(value, int | float):
            continue
        joined = " ".join(evidence.get(path) or [])
        need = reproduces(float(value), numbers(joined) | _word_numbers(joined), assumed) if joined else None
        needed |= need or set()
    return evidence, [a for a in listed if a.get("id") in needed]
