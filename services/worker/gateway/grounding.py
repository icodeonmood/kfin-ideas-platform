"""Only the person's own words (DEC-095): every answer `canvas-assist` suggests carries, in `evidence`, the exact
words from the person's input it came from, and the gateway checks each quote against what was sent.

`ungrounded` names the suggestions that fail, by field path and a reason code (never the text). The gateway sends
those problems back on its one re-ask (BLD-158); if the second answer still fails only here, `repair` drops just
those suggestions and the scan carries on. A dropped field stays empty, except:

- `one_line` becomes the person's own first sentence, trimmed to 20 words, offered as a suggestion backed by itself;
- `kind` becomes "problem" (what quick capture asks about), backed by the same sentence;
- `neutral_summary` becomes "", so match cards show no summary for the idea rather than anything unchecked;
- the no-answer values ("not sure yet", "don't know") need no quote, because they say nothing.

Quotes may come only from the person's own text: the free-text answers in `canvas_answers`, the references they
gave, and digests of their clean files. Never from past corrections (other people's words), the taxonomy or the
gatekeeper block.
"""

from __future__ import annotations

import copy
import re
from typing import Any

from pii.tagger import TAG_RE

ESTIMATES = (
    "hours_saved_per_month",
    "inr_saved_per_year",
    "inr_revenue_one_time",
    "inr_revenue_per_year",
    "clients_who_would_pay",
)
# Answers the assistant may suggest when the person left them empty. Each needs a quote.
SUGGESTIBLE = (
    "kind",
    "one_line",
    "who.segments",
    "who.frequency_or_reach",
    "who.today_alternative",
    "value.category",
    "value.play",
    *(f"value.estimate.{k}" for k in ESTIMATES),
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

# Sent back to the model on the re-ask: field paths and rules only, never text (checks.py convention).
MESSAGES = {
    "no_quote": "needs `evidence`: 1 to 3 exact quotes from the person's own text that support it, or leave it null",
    "not_found": "a quote in `evidence` is not word for word in the person's own text; copy one continuous phrase "
    "exactly (no ellipses, no changes), or leave the field null",
    "too_short": "each quote in `evidence` must be at least two words",
    "no_figure": "an estimate needs a quote that holds the person's own figures, or leave it null",
    "new_number": "holds a number that is not in its quotes; use only the person's figures",
    "not_marked": "you added this answer, so mark its provenance `suggested` and give `evidence`, or leave it empty",
    "not_given": "may only hold references the person gave; return the person's list unchanged",
    "stray_evidence": "`evidence` is only for answers you suggested and for neutral_summary; remove this key",
}

_PUNCT = str.maketrans({"–": "-", "—": "-", "‑": "-", "‘": "'", "’": "'", "“": '"', "”": '"'})
_EDGES = (
    " \t\n\"'.,;:!?…()[]"  # a quote's surrounding marks are not part of it (tags keep their brackets below)
)
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_HAS_FIGURE = re.compile(
    r"\d|\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|thirty|forty|fifty|"
    r"hundred|thousand|lakh|lakhs|crore|crores|dozen|half|ek|do|teen|char|chaar|paanch|panch|chhe|saat|aath|nau|"
    r"das|bees|sau|hazaar|hazar)\b",
    re.I,
)
_SENTENCE_END = re.compile(r"(?<=[.!?।])\s+")  # includes the Devanagari danda


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


def normalise(text: str) -> str:
    """For comparison only: case folded and whitespace collapsed outside tags; tags kept exactly as written."""
    text = text.translate(_PUNCT).replace(" ", " ")
    parts: list[str] = []
    last = 0
    for m in TAG_RE.finditer(text):
        parts.append(text[last : m.start()].casefold())
        parts.append(m.group(0))
        last = m.end()
    parts.append(text[last:].casefold())
    return " ".join("".join(parts).split())


def _clean_quote(quote: str) -> str:
    """Drop surrounding quote marks and punctuation, but never a tag's closing brackets."""
    q = quote.strip()
    while q and q[0] in _EDGES and not q.startswith("[["):
        q = q[1:]
    while q and q[-1] in _EDGES and not q.endswith("]]"):
        q = q[:-1]
    return q.strip()


def source_text(sent: dict[str, Any]) -> str:
    """The person's own words, as the model saw them (tagged)."""
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
    return "\n".join(pieces)


def _numbers(text: str) -> set[float]:
    return {float(n.replace(",", "")) for n in _NUMBER.findall(TAG_RE.sub(" ", text))}


def _quote_problem(path: str, value: Any, quotes: Any, source: str) -> str | None:
    if not isinstance(quotes, list) or not quotes or len(quotes) > MAX_QUOTES:
        return "no_quote"
    cleaned = [_clean_quote(q) for q in quotes if isinstance(q, str)]
    if len(cleaned) != len(quotes) or any(not q for q in cleaned):
        return "no_quote"
    if any(len(q.split()) < 2 and len(q) < 10 for q in cleaned):
        return "too_short"
    if any(normalise(q) not in source for q in cleaned):
        return "not_found"
    joined = " ".join(cleaned)
    if (
        path.startswith("value.estimate.")
        and path != "value.estimate.note"
        and not _HAS_FIGURE.search(joined)
    ):
        return "no_figure"
    if path in PROSE and isinstance(value, str) and not _numbers(value) <= _numbers(joined):
        return "new_number"
    return None


def suggested_paths(sent: dict[str, Any], out: dict[str, Any]) -> list[str]:
    """Answers the assistant added (the person left them empty), plus neutral_summary when it has one."""
    answers = sent.get("canvas_answers") or {}
    paths = []
    for path in SUGGESTIBLE:
        if not _empty(_get(answers, path)):
            continue  # the person's own answer: checks.canvas_assist makes sure it is copied unchanged
        got = _get(out, path)
        if _empty(got) or NO_ANSWER.get(path) == got:
            continue
        paths.append(path)
    if isinstance(out.get("neutral_summary"), str) and out["neutral_summary"].strip():
        paths.append("neutral_summary")
    return paths


def ungrounded(sent: dict[str, Any], out: dict[str, Any]) -> dict[str, str]:
    """Field path -> reason code, for every suggestion not backed by the person's own words."""
    source = normalise(source_text(sent))
    evidence = _dict(out.get("evidence"))
    provenance = _dict(out.get("provenance"))
    answers = sent.get("canvas_answers") or {}
    bad: dict[str, str] = {}
    paths = suggested_paths(sent, out)
    for path in paths:
        if path != "neutral_summary" and provenance.get(path) != "suggested":
            bad[path] = "not_marked"
            continue
        code = _quote_problem(path, _get(out, path), evidence.get(path), source)
        if code:
            bad[path] = code
    if _empty(_get(answers, "ecosystem.references")) and not _empty(_get(out, "ecosystem.references")):
        bad["ecosystem.references"] = "not_given"
    for key in evidence:
        if key not in paths:
            bad.setdefault(key, "stray_evidence")
    return bad


def problems(sent: dict[str, Any], out: dict[str, Any]) -> list[str]:
    return [f"{path}: {MESSAGES[code]}" for path, code in sorted(ungrounded(sent, out).items())]


def first_sentence(details: str) -> tuple[str, str]:
    """The person's first sentence, as (one line, its quote): at most 20 words, with "…" when trimmed."""
    sentence = _SENTENCE_END.split(details.strip(), maxsplit=1)[0] if details.strip() else ""
    words = sentence.split()
    quote = " ".join(words[:FIRST_SENTENCE_WORDS])
    return (quote + "…" if len(words) > FIRST_SENTENCE_WORDS else quote), quote


def repair(sent: dict[str, Any], out: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Drop the suggestions `ungrounded` names. Returns the repaired output and the dropped paths (IDs only)."""
    bad = ungrounded(sent, out)
    if not bad:
        return out, []
    fixed = copy.deepcopy(out)
    if not isinstance(fixed.get("evidence"), dict):
        fixed["evidence"] = {}
    if not isinstance(fixed.get("provenance"), dict):
        fixed["provenance"] = {}
    evidence: dict[str, Any] = fixed["evidence"]
    provenance: dict[str, Any] = fixed["provenance"]
    answers = sent.get("canvas_answers") or {}
    one_line, quote = first_sentence(str(answers.get("details") or ""))
    for path, code in bad.items():
        evidence.pop(path, None)
        if code == "stray_evidence":
            continue
        provenance.pop(path, None)
        if path == "neutral_summary":
            fixed["neutral_summary"] = ""
        elif path in ("one_line", "kind"):
            _set(fixed, path, one_line if path == "one_line" else "problem")
            if quote:
                provenance[path] = "suggested"
                evidence[path] = [quote]
        elif path in NO_ANSWER:
            _set(fixed, path, NO_ANSWER[path])
        elif path in ("who.segments", "ecosystem.references"):
            _set(fixed, path, list(_get(answers, path) or []))
        else:
            _set(fixed, path, None)
    return fixed, sorted(bad)
