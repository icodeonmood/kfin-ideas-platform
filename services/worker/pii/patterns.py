"""Level-1 personal-data check (ARCHITECTURE §4.2 step 2) driven by `patterns.yaml`.

Results carry positions and labels, never the matched value, so they are safe to log and return.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml

PATTERNS_FILE = Path(__file__).with_name("patterns.yaml")

Action = Literal["block", "warn"]

# Verhoeff tables (Aadhaar check digit).
_D = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6),
    (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8),
    (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2),
    (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4),
    (9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
)
_P = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2),
    (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0),
    (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5),
    (7, 0, 4, 6, 9, 1, 3, 2, 5, 8),
)


def verhoeff_valid(digits: str) -> bool:
    check = 0
    for i, ch in enumerate(reversed(digits)):
        check = _D[check][_P[i % 8][int(ch)]]
    return check == 0


def luhn_valid(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


@dataclass(frozen=True)
class Pattern:
    id: str
    label: str
    data_type: str
    regex: re.Pattern[str]
    action: Action
    checksum: str | None
    context: tuple[re.Pattern[str], ...]
    warn_if_kfin_domain: bool
    block_if_also: tuple[str, ...]
    log_ok: bool


@dataclass(frozen=True)
class Match:
    pattern_id: str
    label: str
    data_type: str
    start: int
    end: int
    action: Action


@dataclass(frozen=True)
class Rules:
    version: str
    window: int
    patterns: tuple[Pattern, ...]
    log_rules: dict[str, Any]


def _keyword(kw: str) -> re.Pattern[str]:
    return re.compile(r"(?<![A-Za-z0-9])" + re.escape(kw) + r"(?![A-Za-z0-9])", re.IGNORECASE)


@lru_cache(maxsize=1)
def load_rules(path: Path = PATTERNS_FILE) -> Rules:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    patterns = []
    for p in raw["patterns"]:
        flags = re.IGNORECASE if "i" in str(p.get("flags", "")) else 0
        patterns.append(
            Pattern(
                id=p["id"],
                label=p["label"],
                data_type=p["data_type"],
                regex=re.compile(p["regex"], flags),
                action=p["action"],
                checksum=p.get("checksum"),
                context=tuple(_keyword(k) for k in p.get("context", [])),
                warn_if_kfin_domain=bool(p.get("warn_if_domain_in_env")),
                block_if_also=tuple(p.get("block_if_also", [])),
                log_ok=bool(p.get("log_ok", False)),
            )
        )
    return Rules(
        version=str(raw["version"]),
        window=int(raw["context_window_chars"]),
        patterns=tuple(patterns),
        log_rules=raw["log_rules"],
    )


def _has_context(text: str, start: int, end: int, keywords: tuple[re.Pattern[str], ...], window: int) -> bool:
    lo, hi = max(0, start - window), min(len(text), end + window)
    neighbourhood = text[lo:start] + " " + text[end:hi]
    return any(k.search(neighbourhood) for k in keywords)


def scan(text: str, *, kfin_domains: list[str] | None = None, rules: Rules | None = None) -> list[Match]:
    """Every personal-data match in `text`, with the action that applies (block or warn)."""
    r = rules or load_rules()
    domains = [d.lower() for d in (kfin_domains or [])]
    found: list[Match] = []
    for p in r.patterns:
        for m in p.regex.finditer(text):
            value = m.group(0)
            digits = re.sub(r"[^0-9]", "", value)
            if p.checksum == "verhoeff" and not verhoeff_valid(digits):
                continue
            if p.checksum == "luhn" and not (13 <= len(digits) <= 19 and luhn_valid(digits)):
                continue
            if p.context and not _has_context(text, m.start(), m.end(), p.context, r.window):
                continue
            action: Action = p.action
            if p.warn_if_kfin_domain and value.rsplit("@", 1)[-1].lower() in domains:
                action = "warn"
            found.append(Match(p.id, p.label, p.data_type, m.start(), m.end(), action))
    ids = {f.pattern_id for f in found}
    by_id = {p.id: p for p in r.patterns}
    return [
        Match(f.pattern_id, f.label, f.data_type, f.start, f.end, "block")
        if any(other in ids for other in by_id[f.pattern_id].block_if_also)
        else f
        for f in found
    ]


def blocks(text: str, *, kfin_domains: list[str] | None = None) -> bool:
    return any(m.action == "block" for m in scan(text, kfin_domains=kfin_domains))
