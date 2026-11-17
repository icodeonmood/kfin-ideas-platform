"""Log scrubber rules (non-negotiable 3): logs, traces and errors carry IDs only.

`check_field_name` and `check_value` guard the logger as it writes. `scan_log_line` is the after-the-fact
check used by the log-scrubber test and `scripts/ci/check_logs.py` over any captured log stream.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from pii.patterns import Rules, load_rules, scan


@dataclass(frozen=True)
class Violation:
    line_no: int
    kind: str  # "field" | "pattern" | "event_name"
    where: str  # field path or pattern id, never the offending value


@lru_cache(maxsize=1)
def _compiled() -> tuple[re.Pattern[str], frozenset[str], re.Pattern[str], Rules, frozenset[str]]:
    rules = load_rules()
    lr = rules.log_rules
    flags = re.IGNORECASE if "i" in str(lr.get("forbidden_field_flags", "")) else 0
    return (
        re.compile(lr["forbidden_field_regex"], flags),
        frozenset(n.lower() for n in lr["forbidden_field_names"]),
        re.compile(lr["event_name_regex"]),
        rules,
        frozenset(n.lower() for n in lr.get("allowed_field_names", [])),
    )


def field_is_forbidden(name: str) -> bool:
    regex, names, _, _, allowed = _compiled()
    lowered = name.lower()
    if lowered in allowed:
        return False
    return lowered in names or bool(regex.search(name))


def event_name_ok(event: str) -> bool:
    return bool(_compiled()[2].match(event))


@lru_cache(maxsize=1)
def _safe_value() -> re.Pattern[str]:
    return re.compile(load_rules().log_rules["safe_value_regex"])


def value_patterns(value: str) -> list[str]:
    """Pattern IDs found in a value, ignoring business identifiers marked `log_ok` and safe values (hashes, IDs)."""
    if _safe_value().fullmatch(value):
        return []
    rules = _compiled()[3]
    ok = {p.id for p in rules.patterns if p.log_ok}
    # Every email is personal data in a log, KFin domain or not, so no domain exemption here.
    return sorted({m.pattern_id for m in scan(value, kfin_domains=[]) if m.pattern_id not in ok})


def _walk(obj: Any, path: str) -> Iterator[tuple[str, str, Any]]:
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = str(k)
            yield ("key", f"{path}.{key}" if path else key, key)
            yield from _walk(v, f"{path}.{key}" if path else key)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        yield ("value", path, obj)


def scan_log_line(line: str, line_no: int = 0) -> list[Violation]:
    out: list[Violation] = []
    stripped = line.strip()
    if not stripped:
        return out
    try:
        parsed: Any = json.loads(stripped)
    except ValueError:
        parsed = None
    if isinstance(parsed, dict):
        event = parsed.get("event")
        if isinstance(event, str) and not event_name_ok(event):
            out.append(Violation(line_no, "event_name", "event"))
        for kind, path, item in _walk(parsed, ""):
            if kind == "key" and field_is_forbidden(item):
                out.append(Violation(line_no, "field", path))
            elif kind == "value":
                out.extend(Violation(line_no, "pattern", f"{path}:{pid}") for pid in value_patterns(item))
        return out
    out.extend(Violation(line_no, "pattern", pid) for pid in value_patterns(stripped))
    return out


def scan_log_lines(lines: Iterable[str]) -> list[Violation]:
    violations: list[Violation] = []
    for i, line in enumerate(lines, start=1):
        violations.extend(scan_log_line(line, i))
    return violations
