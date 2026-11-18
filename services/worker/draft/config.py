"""The draft engine's settings: `rules/drafting.md` (when parts form, the sorting lists, the loader's starting
times) and the two promises it keeps from `rules/promises.md` (the minimum to check, how long a draft is kept).
Both live in the company repo, so they change without a release. Read at most once a minute; a company repo seeded
before these files existed gets the defaults below, which equal the seed (BLD-C070)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from core.config import get_settings
from core.logging import get_logger

log = get_logger("draft.config")
TTL_SECONDS = 60.0
PART_KEYS = ("title", "often", "who", "value", "area", "similar")  # E-ENUMS.draft (onepc enums: draft_part)


@dataclass(frozen=True)
class Option:
    label: str
    cues: tuple[str, ...]


@dataclass(frozen=True)
class DraftRules:
    parts_from_chars: int
    similar_from_chars: int
    run_stale_seconds: int
    latency_days: int
    max_message_chars: int
    max_messages: int
    default_means_ms: dict[str, int]
    affects: tuple[Option, ...]
    area: tuple[Option, ...]
    min_chars_to_check: int
    kept_days: int


DEFAULT_DRAFTING: dict[str, Any] = {
    "parts_from_chars": 25,
    "similar_from_chars": 50,
    "run_stale_seconds": 60,
    "latency_days": 7,
    "max_message_chars": 4000,
    "max_messages": 60,
    "default_means_ms": {
        "title": 1800,
        "often": 900,
        "who": 1200,
        "value": 1500,
        "area": 700,
        "similar": 2600,
    },
    "affects": [
        {"label": "Investors", "cues": ["investor", "investors", "customer", "customers"]},
        {"label": "KFin teams", "cues": ["branch", "team", "ops", "operations", "staff"]},
        {"label": "Distributors", "cues": ["distributor", "distributors", "ifa", "mfd", "broker"]},
        {"label": "AMC clients", "cues": ["amc", "amcs", "fund house"]},
        {"label": "Issuer and corporate clients", "cues": ["issuer", "company", "shareholder", "ipo", "agm"]},
    ],
    "area": [
        {"label": "Investor service", "cues": ["investor", "investors", "sms", "call", "calls", "complaint"]},
        {"label": "Operations", "cues": ["manual", "by hand", "process", "courier", "form", "forms"]},
        {"label": "Distributor experience", "cues": ["distributor", "distributors", "iris"]},
        {"label": "Corporate registry", "cues": ["issuer", "shareholder", "ipo", "agm", "dividend"]},
        {"label": "Technology", "cues": ["system", "screen", "app", "portal", "report"]},
        {"label": "Compliance", "cues": ["sebi", "amfi", "circular", "audit", "compliance"]},
        {"label": "Sales", "cues": ["sales", "sell", "lead", "leads"]},
        {"label": "New business", "cues": ["revenue", "product", "market"]},
        {"label": "Distributor services", "cues": ["empanelment", "onboarding", "arn"]},
    ],
}
DEFAULT_PROMISES = {"min_chars_to_check": 30, "kept_days": 30}

_cache: dict[str, Any] = {"at": 0.0, "rules": None}


def _options(items: list[dict[str, Any]]) -> tuple[Option, ...]:
    return tuple(
        Option(str(i["label"]), tuple(str(c).casefold() for c in i.get("cues") or [])) for i in items
    )


def build(drafting: dict[str, Any], promises: dict[str, Any]) -> DraftRules:
    return DraftRules(
        parts_from_chars=int(drafting["parts_from_chars"]),
        similar_from_chars=int(drafting["similar_from_chars"]),
        run_stale_seconds=int(drafting["run_stale_seconds"]),
        latency_days=int(drafting["latency_days"]),
        max_message_chars=int(drafting["max_message_chars"]),
        max_messages=int(drafting["max_messages"]),
        default_means_ms={k: int(v) for k, v in drafting["default_means_ms"].items()},
        affects=_options(drafting["affects"]),
        area=_options(drafting["area"]),
        min_chars_to_check=int(promises["min_chars_to_check"]),
        kept_days=int(promises["kept_days"]),
    )


def rules(*, fresh: bool = False) -> DraftRules:
    now = time.monotonic()
    cached = _cache["rules"]
    if cached is not None and not fresh and now - _cache["at"] < TTL_SECONDS:
        return cached  # type: ignore[no-any-return]
    from rules import load_rule
    from rules.loader import RulesConfigError

    repo = get_settings().company_repo_path
    try:
        drafting = dict(load_rule(repo, "drafting").data)
    except (RulesConfigError, OSError) as exc:
        log.warning("draft.rules_default", rule_code="drafting", error_type=type(exc).__name__)
        drafting = DEFAULT_DRAFTING
    try:
        draft_promises = dict(load_rule(repo, "promises").data["draft"])
    except (RulesConfigError, OSError, KeyError) as exc:
        log.warning("draft.rules_default", rule_code="promises", error_type=type(exc).__name__)
        draft_promises = DEFAULT_PROMISES
    built = with_sorting(build(drafting, draft_promises), _sorting_lists(repo))
    _cache.update(at=now, rules=built)
    return built


NOT_SUGGESTED = frozenset({"others"})  # a catch-all the person may choose, never one words can back


def _sorting_lists(repo: Any) -> dict[str, list[str]] | None:
    """L-SORT's lists (`rules/sorting.md`, c/sort-submit) when that rule exists: then they are the ones offered."""
    from rules import load_rule
    from rules.loader import RULE_PATHS, RulesConfigError

    if "sorting" not in RULE_PATHS:
        return None
    try:
        data = load_rule(repo, "sorting").data
    except (RulesConfigError, OSError):
        return None
    out = {}
    for key, field in (("affects", "affects"), ("area", "areas")):
        lists = data.get(field) or {}
        out[key] = [str(x) for x in [*(lists.get("shown") or []), *(lists.get("more") or [])]]
    return out


def with_sorting(r: DraftRules, lists: dict[str, list[str]] | None) -> DraftRules:
    """The sorting lists' labels, each with the cues `rules/drafting.md` gives that label (none if it gives none)."""
    if not lists:
        return r

    def merged(own: tuple[Option, ...], labels: list[str]) -> tuple[Option, ...]:
        cues = {o.label.casefold(): o.cues for o in own}
        keep = [lab for lab in labels if lab.casefold() not in NOT_SUGGESTED]
        return tuple(Option(lab, cues.get(lab.casefold(), ())) for lab in keep) or own

    from dataclasses import replace

    return replace(
        r, affects=merged(r.affects, lists.get("affects") or []), area=merged(r.area, lists.get("area") or [])
    )


def clear_cache() -> None:
    _cache.update(at=0.0, rules=None)
