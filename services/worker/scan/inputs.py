"""Turn a submitted canvas (web shape) into agent inputs, and build the day-one taxonomy slice.

The slice here is the simple B4 version: every LOB, area tag and role family, plus glossary systems whose
term or alias appears in the text. Router plan P2 (B5) replaces it with a retrieval-ranked slice.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

from core.config import get_settings
from okf.frontmatter import parse

FREE_TEXT = (
    "one_line", "details", "who.frequency_or_reach", "who.today_alternative", "value.estimate.note",
    "ecosystem.our_advantage", "solution.approach", "solution.needs", "solution.risks", "visibility_reason",
)  # fmt: skip


def _get(canvas: dict[str, Any], path: str) -> Any:
    node: Any = canvas
    for key in path.split("."):
        node = node.get(key) if isinstance(node, dict) else None
    return node


def gatekeeper_input(canvas: dict[str, Any]) -> dict[str, Any]:
    fields = {p: str(_get(canvas, p)) for p in FREE_TEXT if str(_get(canvas, p) or "").strip()}
    for i, ref in enumerate((canvas.get("ecosystem") or {}).get("references") or [], start=1):
        if str(ref.get("value") or "").strip():
            fields[f"ecosystem.references.{i}"] = str(ref["value"])
    return {"mode": "submission", "submission": fields}


def _none(v: Any) -> Any:
    return None if v in ("", None) else v


def canvas_answers(canvas: dict[str, Any], attachments: list[dict[str, Any]]) -> dict[str, Any]:
    who = canvas.get("who") or {}
    value = canvas.get("value") or {}
    est = value.get("estimate") or {}
    eco = canvas.get("ecosystem") or {}
    sol = canvas.get("solution") or {}
    return {
        "kind": canvas.get("kind"),
        "one_line": _none(canvas.get("one_line")),
        "details": canvas.get("details") or "",
        "who": {
            "segments": list(who.get("segments") or []),
            "frequency_or_reach": _none(who.get("frequency_or_reach")),
            "today_alternative": _none(who.get("today_alternative")),
        },
        "value": {
            "category": value.get("category"),
            "play": value.get("play"),
            "estimate": {
                k: _none(est.get(k))
                for k in (
                    "hours_saved_per_month",
                    "inr_saved_per_year",
                    "inr_revenue_one_time",
                    "inr_revenue_per_year",
                    "clients_who_would_pay",
                    "note",
                )
            },
            "basis": value.get("basis"),
        },
        "ecosystem": {
            "solved_elsewhere": eco.get("solved_elsewhere"),
            "references": [
                {"kind": r.get("kind"), "value": r.get("value"), "player": r.get("player")}
                for r in eco.get("references") or []
            ],
            "our_advantage": _none(eco.get("our_advantage")),
        },
        "solution": {k: _none(sol.get(k)) for k in ("approach", "needs", "risks")},
        "attachments": attachments,
    }


def assumptions(repo: Path | None = None) -> list[dict[str, Any]]:
    """The fixed list of basic assumptions canvas-assist may use (DEC-097), from `rules/thresholds.md`. An older
    company repo without the key allows none."""
    from rules import load_rule

    data = load_rule(repo or get_settings().company_repo_path, "thresholds").data
    return [
        {"id": str(a["id"]), "value": a["value"], "says": str(a["says"])}
        for a in data.get("assumptions") or []
    ]


_slice_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def _entries(repo: Path, folder: str, prefix: str) -> list[dict[str, Any]]:
    out = []
    for path in sorted((repo / "taxonomy" / folder).glob(f"{prefix}-*.md")):
        meta = parse(path.read_text(encoding="utf-8")).meta or {}
        k = meta.get("kfin") or {}
        out.append(
            {"id": k.get("id") or path.stem, "name": meta.get("title"), "aliases": k.get("aliases") or []}
        )
    return out


def _taxonomy(repo: Path) -> dict[str, Any]:
    key = str(repo)
    hit = _slice_cache.get(key)
    if hit and time.monotonic() - hit[0] < 60:
        return hit[1]
    data = {
        "lobs": _entries(repo, "lobs", "LOB"),
        "areas": _entries(repo, "areas", "AREA"),
        "roles": _entries(repo, "roles", "ROLE"),
        "glossary": _entries(repo, "glossary", "GL"),
    }
    _slice_cache[key] = (time.monotonic(), data)
    return data


def taxonomy_slice(text: str, repo: Path | None = None) -> dict[str, Any]:
    t = _taxonomy(repo or get_settings().company_repo_path)
    systems = []
    for g in t["glossary"]:
        terms = [g["name"], *g["aliases"]]
        if any(
            term and re.search(r"(?<!\w)" + re.escape(str(term)) + r"(?!\w)", text, re.I) for term in terms
        ):
            systems.append({"id": g["id"], "name": g["name"]})
    return {
        "lobs": [{"id": x["id"], "name": x["name"]} for x in t["lobs"]],
        "areas": [{"id": x["id"], "name": x["name"]} for x in t["areas"]],
        "systems": systems[:30],
        "roles": [{"id": x["id"], "name": x["name"]} for x in t["roles"]],
    }
