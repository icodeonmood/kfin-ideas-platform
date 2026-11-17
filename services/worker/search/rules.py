"""L-SEARCH: the pure rules, tested without a database (lane F, BLD-F039 to BLD-F041).

- `terms`, `score`, `snippet_at`: how a query meets an idea's searchable fields and what a row shows (L-SEARCH/2–3).
- `normalise`, `matches`, `facets`: the filters, each option with a live count given the other filters (L-SEARCH/5).
- `sentence`, `matched_line`, `empty`: the two plain sentences over a result set and the no-result state
  (L-SEARCH/3, /7).

Nothing here logs. The query and the text searched are the person's own list only, and never leave this module
except as the result the person asked for (non-negotiable 3).
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

# The fields searched, strongest first: (key, how the "matched on" line names it, weight). Hidden details are never
# here: "your own words" is the masked copy (L-SEARCH/2, DEC-103).
FIELDS: tuple[tuple[str, str, int], ...] = (
    ("title", "titles", 5),
    ("reference", "references", 4),
    ("summary", "short summaries", 3),
    ("words", "your own words", 2),
    ("reasons", "the review desk’s reasons", 1),
)
FIELD_NAME = {k: name for k, name, _ in FIELDS}
FIELD_WEIGHT = {k: w for k, _, w in FIELDS}
SNIPPET_MAX = 96
QUERY_MAX = 200

_STOP = frozenset(
    {"a", "an", "and", "are", "about", "for", "from", "in", "is", "it", "my", "of", "on", "or", "the", "to",
     "with", "which", "what", "who", "this", "that", "me", "i", "we", "our", "ideas", "idea"}
)  # fmt: skip
_REF = re.compile(r"\bidea-\d{4}-\d{6}\b", re.I)
_WORD = re.compile(r"[a-z0-9]+")
_ENDINGS = ("ions", "ing", "ies", "ion", "es", "ed", "s")


def _stem(word: str) -> str:
    """A light stem so "rejections", "rejected" and "rejection" meet as prefixes. Short words stay whole."""
    for end in _ENDINGS:
        if len(word) - len(end) >= 4 and word.endswith(end):
            return word[: -len(end)]
    return word


def terms(q: str | None) -> list[str]:
    """The query's telling words, lower-case and stemmed, in order, once each. A reference (IDEA-2026-001412) is
    kept whole. Stop words go unless nothing else is left."""
    text = " ".join((q or "").split())[:QUERY_MAX].lower()
    refs = _REF.findall(text)
    rest = _REF.sub(" ", text)
    words = _WORD.findall(rest)
    kept = [w for w in words if w not in _STOP and len(w) >= 2] or [w for w in words if len(w) >= 2]
    out: list[str] = []
    for t in [*(r.lower() for r in refs), *(_stem(w) for w in kept)]:
        if t not in out:
            out.append(t)
    return out


def _finder(term: str) -> re.Pattern[str]:
    if term.startswith("idea-"):
        return re.compile(re.escape(term), re.I)
    return re.compile(r"(?<![a-z0-9])" + re.escape(term), re.I)


@dataclass(frozen=True)
class Match:
    score: float
    matched_on: tuple[str, ...]
    snippet: str
    found: int = 0
    of: int = 0
    per_field: dict[str, int] = field(default_factory=dict)


def snippet_at(text: str, at: int, limit: int = SNIPPET_MAX) -> str:
    """About `limit` characters around position `at`, cut at words, with "…" where it was cut."""
    t = " ".join(text.split())
    if len(t) <= limit:
        return t
    # Re-find the position in the collapsed text: count the characters before `at` in the original.
    pos = len(" ".join(text[:at].split()))
    start = max(0, pos - limit // 3)
    end = min(len(t), start + limit)
    start = max(0, end - limit)
    piece = t[start:end]
    if start > 0:
        piece = piece.split(" ", 1)[1] if " " in piece else piece
    if end < len(t):
        piece = piece.rsplit(" ", 1)[0] if " " in piece else piece
    piece = piece.strip(" ,;:")
    return f"{'…' if start > 0 else ''}{piece}{'…' if end < len(t) else ''}"


def score(fields: Mapping[str, str | None], q: str | None, ts: Sequence[str] | None = None) -> Match | None:
    """How well a query meets one idea (L-SEARCH/2), or None for no match.

    Each term counts once, at the weight of the strongest field holding it; the whole query in the title adds a
    bonus. At least half the terms (one at least) must be found. The snippet comes from the strongest field other
    than the title that holds a term (the title is on the row already), else the short summary's start."""
    ts = list(ts if ts is not None else terms(q))
    if not ts:
        return None
    found = 0
    total = 0.0
    per_field: dict[str, int] = {}
    first_hit: dict[str, int] = {}
    for t in ts:
        finder = _finder(t)
        best = None
        for key, _, weight in FIELDS:
            text = fields.get(key) or ""
            m = finder.search(text)
            if not m:
                continue
            per_field[key] = per_field.get(key, 0) + 1
            first_hit.setdefault(key, m.start())
            if best is None:
                best = weight
        if best is not None:
            found += 1
            total += best
    if found < max(1, math.ceil(len(ts) / 2)):
        return None
    phrase = " ".join((q or "").split()).lower()
    if phrase and len(ts) > 1 and phrase in (fields.get("title") or "").lower():
        total += FIELD_WEIGHT["title"]
    matched = tuple(k for k, _, _ in FIELDS if k in per_field)
    snip = ""
    for key in matched:
        if key in ("title", "reference"):
            continue
        snip = snippet_at(fields.get(key) or "", first_hit[key])
        break
    if not snip and fields.get("summary"):
        snip = snippet_at(fields["summary"] or "", 0)
    return Match(total + found / len(ts), matched, snip, found, len(ts), per_field)


# ---------------------------------------------------------------------------------------------------------------
# Filters with live counts (L-SEARCH/5)
# ---------------------------------------------------------------------------------------------------------------
Active = dict[str, list[str]]


@dataclass(frozen=True)
class Facet:
    """One filter: its key, its label, whether it takes one value or many, its options in order, and labels."""

    key: str
    label: str
    multi: bool
    order: tuple[str, ...] = ()
    labels: Mapping[str, str] = field(default_factory=dict)
    sort_by_label: bool = False


def normalise(filters: Mapping[str, Iterable[str] | str | None] | None, facets: Sequence[Facet]) -> Active:
    """Known keys only; values trimmed, kept once, in the order given. A single-value facet keeps its last value; a
    facet with a fixed list of options drops values outside it."""
    out: Active = {}
    for f in facets:
        raw = (filters or {}).get(f.key)
        vals = [raw] if isinstance(raw, str) else list(raw or [])
        seen: list[str] = []
        for v in vals:
            s = str(v).strip()[:120]
            if not s or s in seen or (f.order and s not in f.order):
                continue
            seen.append(s)
        if seen:
            out[f.key] = seen if f.multi else seen[-1:]
    return out


def matches(row: Mapping[str, Any], active: Active, skip: str | None = None) -> bool:
    """A row passes when, for every filter in use (other than `skip`), its value is one of those picked."""
    for key, vals in active.items():
        if key == skip or not vals:
            continue
        v = row.get(key)
        have = set(v) if isinstance(v, list | tuple | set) else {v}
        if not have & set(vals):
            return False
    return True


def facets(rows: Sequence[Mapping[str, Any]], active: Active, specs: Sequence[Facet]) -> list[dict[str, Any]]:
    """Every filter with its options and live counts: an option's count is how many rows it would show with the
    other filters as they are, so a picked option keeps its own count. Fixed options keep their order (and show at
    0); open ones (area) follow the rows, then the alphabet when asked; a picked value no row has still shows."""
    out: list[dict[str, Any]] = []
    for f in specs:
        present: list[str] = []
        for r in rows:
            v = r.get(f.key)
            for val in v if isinstance(v, list | tuple) else [v]:
                if val is not None and str(val) and str(val) not in present:
                    present.append(str(val))
        values = (
            list(f.order) if f.order else sorted(present, key=str.casefold) if f.sort_by_label else present
        )
        values += [v for v in active.get(f.key, []) if v not in values]
        tally = dict.fromkeys(values, 0)
        for r in rows:
            if not matches(r, active, skip=f.key):
                continue
            v = r.get(f.key)
            for val in v if isinstance(v, list | tuple) else [v]:
                if val is not None and str(val) in tally:
                    tally[str(val)] += 1
        on = set(active.get(f.key, []))
        out.append({
            "key": f.key,
            "label": f.label,
            "multi": f.multi,
            "options": [{"value": v, "label": f.labels.get(v, v), "count": tally[v], "active": v in on}
                        for v in values],
        })  # fmt: skip
    return out


def chips(active: Active, specs: Sequence[Facet]) -> list[dict[str, str]]:
    """The filters in use, for the chips in the bar (C-SEARCH): each removable."""
    by_key = {f.key: f for f in specs}
    return [
        {"key": k, "value": v, "label": by_key[k].labels.get(v, v)}
        for k in (f.key for f in specs)
        for v in active.get(k, [])
    ]


# ---------------------------------------------------------------------------------------------------------------
# The sentences (L-SEARCH/3, /7)
# ---------------------------------------------------------------------------------------------------------------
def _count(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _join(names: Sequence[str]) -> str:
    if len(names) <= 1:
        return "".join(names)
    return f"{', '.join(names[:-1])} and {names[-1]}"


def sentence(q: str, mine: int, teamed: int, closest_title: str | None) -> str:
    """L-SEARCH/3, the first sentence: what was found, and the closest hit (lane E's My ideas wording)."""
    if not closest_title:
        return f"Nothing found for “{q}”."
    return (
        f"Found {_count(mine + teamed, 'idea', 'ideas')} about “{q}”: {mine} of yours and {teamed} you teamed up on. "
        f"Closest: “{closest_title}”."
    )


def matched_line(fields: Iterable[str]) -> str:
    """L-SEARCH/3, the second sentence: what the results matched on, strongest field first."""
    got = set(fields)
    names = [name for key, name, _ in FIELDS if key in got]
    return f"Matched on {_join(names)}." if names else ""


def empty(q: str) -> dict[str, Any]:
    """L-SEARCH/7: the filtered-to-nothing state, with "Show all ideas"."""
    return {
        "kind": "no_results",
        "title": f"Nothing found for “{q}”." if q else "No ideas match these filters.",
        "line": "Try other words, or clear the search." if q else "Try fewer filters.",
        "action": {"label": "Show all ideas", "op": "clear"},
    }
