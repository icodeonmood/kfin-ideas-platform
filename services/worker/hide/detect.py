"""What to hide in a piece of text (L-HIDE.detect, DEC-103): patterns, then the gatekeeper, then names.

1. Values already hidden on this idea (a reviewer's "Hide this", an earlier gatekeeper find) are hidden again
   wherever they appear, so a value once hidden stays hidden in every new message and edit.
2. The shared pattern rules (`pii/patterns.yaml`): only `block` matches, mapped to a kind by `hide/config.yaml`,
   plus the patterns only hiding uses (UPI ids).
3. The gatekeeper, through the gateway (tagged first, non-negotiables 1 and 2), when the assistant is on: the
   customers it names (`investor_context_tags`) and its spans at or above `gatekeeper.personal_data_block`.
4. A person's name (Presidio and the KFin name recognisers), only in the same sentence as another hidden detail.
   Colleagues' names (the people directory) are never hidden.

A `Found` carries the value, so it is never logged; callers log counts and kinds only.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from core.config import get_settings
from core.db import Conn
from core.logging import get_logger
from pii.patterns import scan

log = get_logger("hide")
CONFIG_FILE = Path(__file__).with_name("config.yaml")
KINDS = ("folio", "pan", "phone", "email", "account", "aadhaar", "name")  # E-ENUMS.hidden (hidden_kind)
PRIORITY = {"reviewer": 0, "known": 0, "patterns": 1, "gatekeeper": 2, "names": 3}
_MASK_TOKEN = re.compile(r"(?:Folio|PAN|Phone|Email|Account|Aadhaar|Name) ••••\S{0,2}")
CONTEXT_CHARS = 40
_SENTENCE_END = re.compile(r"[.!?]+(?=\s|$)|\n")


@dataclass(frozen=True)
class Found:
    start: int
    end: int
    kind: str
    value: str
    found_by: str = "patterns"  # hidden_details.found_by: patterns | gatekeeper | reviewer


@dataclass(frozen=True)
class Config:
    from_patterns: dict[str, str]
    extra: tuple[tuple[str, re.Pattern[str]], ...]
    labels: dict[str, str]
    nouns: dict[str, str]
    articles: dict[str, str]
    gatekeeper_kinds: dict[str, str | None]


@lru_cache(maxsize=1)
def config(path: Path = CONFIG_FILE) -> Config:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    for section in ("labels", "nouns", "articles"):
        missing = set(KINDS) - set(raw[section])
        if missing:
            raise ValueError(f"hide config: {section} lacks {sorted(missing)}")
    kinds = list(raw["from_patterns"].values()) + [e["kind"] for e in raw.get("extra", [])]
    kinds += [k for k in raw["gatekeeper_kinds"].values() if k is not None]
    if not set(kinds) <= set(KINDS):
        raise ValueError("hide config: unknown hidden kind")
    return Config(
        from_patterns=dict(raw["from_patterns"]),
        extra=tuple((e["kind"], re.compile(e["regex"])) for e in raw.get("extra", [])),
        labels=dict(raw["labels"]),
        nouns=dict(raw["nouns"]),
        articles=dict(raw["articles"]),
        gatekeeper_kinds=dict(raw["gatekeeper_kinds"]),
    )


# ---- masks and words ---------------------------------------------------------------------------------------


MASK_TAIL_FROM = (
    5  # a value shorter than this shows no last characters, so a mask never gives most of it away
)


def mask(kind: str, value: str) -> str:
    """ "Folio ••••89": the kind's label, four dots and the value's last two characters (L-HIDE.rules/3). A value of
    fewer than five characters shows the label and the dots only (BLD-C069)."""
    compact = re.sub(r"\s", "", value)
    return f"{config().labels[kind]} ••••{compact[-2:] if len(compact) >= MASK_TAIL_FROM else ''}"


def mask_tokens(text: str) -> list[tuple[int, int]]:
    """Where masks already sit in a masked copy."""
    return [(m.start(), m.end()) for m in _MASK_TOKEN.finditer(text)]


def noun(kind: str, *, article: bool = False) -> str:
    c = config()
    return f"{c.articles[kind]} {c.nouns[kind]}" if article else c.nouns[kind]


def kinds_line(kinds: Iterable[str]) -> str:
    """ "Folio number, PAN and phone number" for the draft panel's folded bar (C-HIDDEN.where), in first-seen order."""
    seen: list[str] = []
    for k in kinds:
        if k not in seen:
            seen.append(k)
    words = [noun(k) for k in seen]
    if not words:
        return ""
    line = words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]
    return line[0].upper() + line[1:]


def receipt(masks: list[str]) -> str | None:
    """ "Hid 3 personal details from everyone but you: Folio ••••89, PAN ••••4F, Phone ••••10." (C-HIDDEN.where)."""
    if not masks:
        return None
    n = len(masks)
    return f"Hid {n} personal detail{'' if n == 1 else 's'} from everyone but you: {', '.join(masks)}."


# ---- detection ---------------------------------------------------------------------------------------------


def pattern_finds(text: str) -> list[Found]:
    c = config()
    out: list[Found] = []
    for m in scan(text, kfin_domains=get_settings().kfin_domains):
        kind = c.from_patterns.get(m.pattern_id)
        if kind and m.action == "block":
            out.append(Found(m.start, m.end, kind, text[m.start : m.end]))
    for kind, rx in c.extra:
        out.extend(Found(m.start(), m.end(), kind, m.group(0)) for m in rx.finditer(text))
    return out


def classify(value: str, text: str | None = None, start: int | None = None) -> str:
    """The kind for words someone selected to hide: the pattern that covers most of them, read with the words around
    them when given (a folio number needs "folio" nearby), else Name."""
    if text is None or start is None:
        text, start = value, 0
    lo = max(0, start - CONTEXT_CHARS)
    window = text[lo : start + len(value) + CONTEXT_CHARS]
    s, e = start - lo, start - lo + len(value)
    best, cover = "name", 0
    for f in pattern_finds(window):
        overlap = min(e, f.end) - max(s, f.start)
        if overlap > cover:
            best, cover = f.kind, overlap
    return best if cover * 2 >= len(value.strip()) else "name"


def occurrences(text: str, value: str) -> list[tuple[int, int]]:
    """Exact, case-sensitive places of `value` (mapping a selection back to the words it came from)."""
    out: list[tuple[int, int]] = []
    if not value:
        return out
    at = text.find(value)
    while at != -1:
        out.append((at, at + len(value)))
        at = text.find(value, at + len(value))
    return out


@lru_cache(maxsize=256)
def value_pattern(value: str) -> re.Pattern[str] | None:
    """`value` as whole words, any case, any run of spaces between its words: "kiran  rao" matches "Kiran Rao",
    and "Rao" does not match inside "Raona" (BLD-C066)."""
    words = value.split()
    if not words:
        return None
    body = r"\s+".join(re.escape(w) for w in words)
    return re.compile(rf"(?<!\w){body}(?!\w)", re.IGNORECASE)


def value_places(text: str, value: str, *, skip_masks: bool = True) -> list[tuple[int, int]]:
    """Where `value` appears in `text` as whole words, in any case, outside the masks already there."""
    rx = value_pattern(value)
    if rx is None or not text:
        return []
    masks = mask_tokens(text) if skip_masks else []
    return [
        (m.start(), m.end())
        for m in rx.finditer(text)
        if all(m.end() <= a or m.start() >= b for a, b in masks)
    ]


def same_value(a: str, b: str) -> bool:
    rx = value_pattern(a)
    return rx is not None and rx.fullmatch(b) is not None


def mask_in(text: str, value: str, masked: str | None = None, kind: str = "name") -> tuple[str, int]:
    """`text` with every whole-word, any-case place of `value` replaced by its mask; and how many were replaced.
    Each place is masked from its own characters unless `masked` is given."""
    places = value_places(text, value)
    out = text
    for s, e in reversed(places):
        out = out[:s] + (masked if masked is not None else mask(kind, text[s:e])) + out[e:]
    return out, len(places)


def known_finds(text: str, known: Mapping[str, tuple[str, str]]) -> list[Found]:
    """Every place a value already hidden on this idea appears again, as whole words in any case. `known`: value ->
    (kind, found_by). Each find carries the characters as written there."""
    out: list[Found] = []
    for value, (kind, found_by) in known.items():
        out.extend(Found(s, e, kind, text[s:e], found_by) for s, e in value_places(text, value))
    return out


# ---- offsets: the browser counts UTF-16 code units, Python counts code points ------------------------------


def from_utf16(text: str, offset: int) -> int | None:
    """The code-point offset for a UTF-16 offset in `text`, or None when it is outside or splits a character."""
    if offset < 0:
        return None
    units = 0
    for i, ch in enumerate(text):
        if units == offset:
            return i
        units += 2 if ord(ch) > 0xFFFF else 1
        if units > offset:
            return None
    return len(text) if units == offset else None


def to_utf16(text: str, offset: int) -> int:
    """The UTF-16 offset for a code-point offset in `text`."""
    return sum(2 if ord(ch) > 0xFFFF else 1 for ch in text[: max(0, offset)])


def non_overlapping(found: Iterable[Found]) -> list[Found]:
    """Highest priority first, then the longer span; in text order."""
    chosen: list[Found] = []
    for f in sorted(found, key=lambda f: (PRIORITY.get(f.found_by, 9), -(f.end - f.start), f.start)):
        if f.end > f.start and all(f.end <= c.start or f.start >= c.end for c in chosen):
            chosen.append(f)
    return sorted(chosen, key=lambda f: f.start)


def sentences(text: str) -> list[tuple[int, int]]:
    out, start = [], 0
    for m in _SENTENCE_END.finditer(text):
        out.append((start, m.end()))
        start = m.end()
    if start < len(text):
        out.append((start, len(text)))
    return out


def names_near(text: str, people: Iterable[tuple[int, int]], others: list[Found]) -> list[Found]:
    """A name hides only when it shares a sentence with another hidden detail (L-HIDE.detect default)."""
    spans = sentences(text)
    out: list[Found] = []
    for s, e in people:
        sentence = next(((a, b) for a, b in spans if a <= s < b), (0, len(text)))
        if any(sentence[0] <= o.start < sentence[1] for o in others):
            out.append(Found(s, e, "name", text[s:e], "patterns"))
    return out


def people_in(conn: Conn | None, text: str, d: Any = None) -> list[tuple[int, int]]:
    """Spans of people's names that are not colleagues (Presidio + KFin recognisers, `pii.detect`)."""
    if not any(ch.isupper() for ch in text):
        return []
    from pii.detect import Directory, detect, directory

    if d is None:
        d = directory(conn) if conn is not None else Directory().compile()
    return [
        (f.start, f.end)
        for f in detect(text, d, kfin_domains=get_settings().kfin_domains)
        if f.type == "PERSON"
    ]


def _threshold() -> float:
    try:
        from rules import load_rule

        t = load_rule(Path(get_settings().company_repo_path), "thresholds").data["gatekeeper"]
        return float(t["personal_data_block"])
    except Exception:  # an unreadable rules file must not stop hiding; the stricter default applies
        return 0.5


def gatekeeper_kind(data_type: str, value: str) -> str | None:
    kind = config().gatekeeper_kinds.get(data_type, "name")
    if kind is None:
        return None
    by_pattern = classify(value)
    if by_pattern != "name" and kind in ("account", "pan"):
        return by_pattern  # "account_or_folio_number" that is a folio; a "government_id" that is an Aadhaar
    if kind == "account" and re.search(r"(?i)folio", value):
        return "folio"
    return kind


@dataclass(frozen=True)
class Gate:
    """The gatekeeper's finds for one text. `skipped` is the gateway's error code when it could not run (the text
    then goes on with the patterns and names only, and a re-check is queued, BLD-C067)."""

    finds: list[Found]
    skipped: str | None = None
    switched_off: bool = False


def gatekeeper_finds(conn: Conn, text: str, scope: str) -> Gate:
    """The gatekeeper's finds, mapped back to positions in `text`. Empty when the assistant is off or failed: the
    patterns have already run, and the person's draft must not wait on the model."""
    from core import killswitch

    if not text.strip() or not killswitch.is_on("ai.all", conn):
        return Gate([])
    from gateway import AgentFailed, AgentSwitchedOff, run_agent
    from pii import vault
    from pii.restore import restore

    try:
        out = run_agent("gatekeeper", {"mode": "submission", "submission": {"text": text}}, scope, conn=conn)
    except AgentFailed as exc:
        log.info("hide.gatekeeper_skipped", reason_code=exc.code)
        return Gate([], exc.code, isinstance(exc, AgentSwitchedOff))
    mapping = vault.mapping(conn, scope)
    found: list[Found] = []
    for tag in out.data.get("investor_context_tags") or []:
        if tag in mapping:
            value = mapping[tag][1]
            found.extend(Found(s, e, "name", text[s:e], "gatekeeper") for s, e in occurrences(text, value))
    floor = _threshold()
    for span in (out.data.get("personal_data") or {}).get("spans") or []:
        if float(span.get("confidence", 0)) < floor:
            continue
        quote = str(restore(str(span.get("quote", "")), mapping, "real")).strip()
        if not quote or "[[" in quote:
            continue
        kind = gatekeeper_kind(str(span.get("data_type", "other")), quote)
        if kind is None:
            continue
        found.extend(Found(s, e, kind, quote, "gatekeeper") for s, e in occurrences(text, quote))
    return Gate(found)


def find(
    conn: Conn | None,
    text: str,
    *,
    scope: str | None = None,
    known: Mapping[str, tuple[str, str]] | None = None,
    gatekeeper: bool = True,
    names: bool = True,
    directory: Any = None,
    gate: Iterable[Found] = (),
) -> list[Found]:
    """Everything to hide in `text`, non-overlapping, in text order. Nothing is stored. `gate`: gatekeeper finds the
    caller already has (`hide_into` asks the model before it takes the idea's lock)."""
    found = known_finds(text, known or {}) + pattern_finds(text) + list(gate)
    if gatekeeper and conn is not None and scope is not None:
        found += gatekeeper_finds(conn, text, scope).finds
    chosen = non_overlapping(found)
    if names and chosen:
        people = [
            (s, e)
            for s, e in people_in(conn, text, directory)
            if all(e <= c.start or s >= c.end for c in chosen)
        ]
        chosen = non_overlapping(chosen + names_near(text, people, chosen))
    return chosen
