"""Render an idea file (OKF concept, ARCHITECTURE §2.2) from the `ideas` read model.

The submitter's text is escaped so it can never add a heading, raw HTML or a frontmatter fence to the file.
The History table is carried over from the committed file and one row is appended per event.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from okf.frontmatter import FrontmatterError, dump, parse

IST = ZoneInfo("Asia/Kolkata")
HISTORY_HEADING = "## History"
_ROW = re.compile(r"^\|(.+)\|\s*$")

SEGMENTS = {
    "investors": "investors",
    "distributors": "distributors",
    "amc_clients": "AMC clients",
    "issuer_clients": "issuer and corporate clients",
    "kfin_teams": "KFin teams",
    "other": "others",
}
CATEGORIES = {
    "cost_saving": "cost saving",
    "new_revenue": "new revenue",
    "both": "both",
    "not_sure": "not sure yet",
}
PLAYS = {
    "process_improvement": "process improvement",
    "upsell": "upsell to an existing client",
    "cross_sell": "cross-sell to an existing client",
    "new_product": "new product or business line",
    "other": "other",
}
BASES = {
    "own_data": "my own data",
    "document": "a document or report",
    "conversation": "a conversation with a client or colleague",
    "hunch": "a hunch",
}
SOLVED = {"yes": "yes", "partly": "partly", "no": "no", "dont_know": "don't know"}
ESTIMATES = (
    ("hours_saved_per_month", "hours saved a month"),
    ("inr_saved_per_year", "₹ saved a year"),
    ("inr_revenue_one_time", "₹ one-time revenue"),
    ("inr_revenue_per_year", "₹ revenue a year"),
    ("clients_who_would_pay", "clients who would pay"),
)


@dataclass(frozen=True)
class HistoryRow:
    when: str
    event: str
    by: str
    note: str


def ist(ts: datetime) -> datetime:
    return ts.astimezone(IST)


def iso(ts: datetime) -> str:
    return ist(ts).isoformat(timespec="seconds")


def esc(text: str | None) -> str:
    """Make submitter text inert inside Markdown: no headings, fences, HTML or table breaks."""
    if not text:
        return ""
    text = html.escape(text.replace("\r\n", "\n").replace("\r", "\n"), quote=False)
    lines = []
    for line in text.split("\n"):
        stripped = line.lstrip()
        if stripped.startswith(("#", "---", "```", "~~~", "|", "=", "* ", "- ", "+ ")):
            line = line[: len(line) - len(stripped)] + "\\" + stripped
        lines.append(line)
    return "\n".join(lines)


def cell(text: str | None) -> str:
    return esc(text).replace("\n", " ").replace("|", "\\|")


def quote(text: str | None) -> str:
    return "\n".join("> " + ln if ln else ">" for ln in esc(text).split("\n")) if text else "> (none)"


def repo_path_for(idea_id: str, submitted_at: datetime) -> str:
    local = ist(submitted_at)
    return f"ideas/{local:%Y}/{local:%m}/{idea_id}.md"


def existing_state(text: str | None) -> tuple[list[HistoryRow], list[dict[str, Any]]]:
    """History rows and verified events from the committed version of the file, if any."""
    if not text:
        return [], []
    try:
        doc = parse(text)
    except FrontmatterError:
        return [], []
    verified = (doc.meta or {}).get("verified") or []
    if isinstance(verified, dict):
        verified = [verified]
    rows: list[HistoryRow] = []
    in_history = False
    for line in doc.body.split("\n"):
        if line.strip() == HISTORY_HEADING:
            in_history = True
            continue
        if in_history and line.startswith("## "):
            break
        m = _ROW.match(line) if in_history else None
        if m:
            parts = [p.strip() for p in re.split(r"(?<!\\)\|", m.group(1))]
            if len(parts) == 4 and parts[0] not in ("When", "---") and not set(parts[0]) <= {"-"}:
                rows.append(HistoryRow(*parts))
    return rows, list(verified)


def _bullets(pairs: list[tuple[str, str | None]]) -> str:
    lines = [f"- {label}: {esc(value)}" for label, value in pairs if value]
    return "\n".join(lines) if lines else "Not answered yet."


def render_idea(
    idea: dict[str, Any],
    *,
    history: list[HistoryRow],
    verified: list[dict[str, Any]],
    generated_by: str,
) -> str:
    canvas: dict[str, Any] = idea.get("canvas") or {}
    who = canvas.get("who") or {}
    value = canvas.get("value") or {}
    estimate = value.get("estimate") or {}
    eco = canvas.get("ecosystem") or {}
    sol = canvas.get("solution") or {}
    provenance: dict[str, str] = canvas.get("provenance") or {}
    one_line = canvas.get("one_line") or ""
    summary = canvas.get("neutral_summary") or one_line

    tags = [a.removeprefix("AREA-") for a in idea["area_ids"]]
    tags += [lob.removeprefix("LOB-") for lob in idea["lobs"]]
    tags += [s.removeprefix("GL-") for s in idea["systems"]]
    meta: dict[str, Any] = {
        "type": "idea",
        "title": one_line,
        "description": summary,
        "tags": list(dict.fromkeys(tags)),
        "status": "stable" if any(str(v.get("by", "")).startswith("human:") for v in verified) else "draft",
        "generated": {"by": generated_by, "at": iso(idea["updated_at"])},
    }
    if verified:
        meta["verified"] = verified
    meta["sources"] = [{"id": idea["submission_id"], "resource": f"submission:{idea['submission_id']}"}]
    meta["kfin"] = {
        "id": idea["idea_id"],
        "stage": idea["stage"],
        "kind": idea["kind"],
        "category": idea["category"],
        "play": idea["play"],
        "basis": idea["basis"],
        "strength": idea["strength"] if idea["strength"] is not None else 0,
        "scope": idea["scope"],
        "areas": list(idea["area_ids"]),
        "lobs": list(idea["lobs"]),
        "systems": list(idea["systems"]),
        "roles_affected": list(idea["roles_affected"]),
        "contributor": idea["contributor_code"],
        "co_contributors": list(idea.get("co_contributors") or []),
        "cluster": idea["cluster_id"],
        "visibility": idea["visibility"],
        "language": idea["language"] or "en",
        "attachments": [
            {k: a[k] for k in ("id", "name", "sha256", "bytes") if k in a}
            for a in (canvas.get("attachments") or [])
            if a.get("state") == "clean"
        ],
        "references": [
            {"kind": r.get("kind"), "value": r.get("value"), "player": r.get("player")}
            for r in (eco.get("references") or [])
        ],
    }

    figures = [
        f"{estimate[key]:,.0f} {label}"
        for key, label in ESTIMATES
        if isinstance(estimate.get(key), int | float)
    ]
    refs = eco.get("references") or []
    attachments = [a for a in (canvas.get("attachments") or []) if a.get("state") == "clean"]
    suggested = sorted((k, v) for k, v in provenance.items() if v in ("suggested", "accepted"))

    sections = [
        "## What it is",
        esc(one_line) or "Not answered yet.",
        "",
        esc(canvas.get("details")),
        "",
        "## Who it touches",
        _bullets(
            [
                (
                    "Who feels it or would pay",
                    ", ".join(SEGMENTS.get(s, s) for s in who.get("segments") or []),
                ),
                ("How often, or how many clients", who.get("frequency_or_reach")),
                ("What people do today", who.get("today_alternative")),
            ]
        ),
        "",
        "## What it's worth to KFintech (submitter's estimate and basis)",
        _bullets(
            [
                ("Category", CATEGORIES.get(value.get("category") or "", value.get("category"))),
                ("How KFintech benefits", PLAYS.get(value.get("play") or "", value.get("play"))),
                ("Rough size", "; ".join(figures) or None),
                ("Based on", BASES.get(value.get("basis") or "", value.get("basis"))),
                ("Note", estimate.get("note")),
            ]
        ),
        "",
        "## Solved elsewhere, and why KFintech",
        _bullets(
            [
                (
                    "Solved elsewhere",
                    SOLVED.get(eco.get("solved_elsewhere") or "", eco.get("solved_elsewhere")),
                ),
                (
                    "References",
                    "; ".join(f"{r.get('player') or 'other'}: {r.get('value')}" for r in refs) or None,
                ),
                ("Why KFintech", eco.get("our_advantage")),
            ]
        ),
        "",
        "## Proposed solution, needs and risks",
        _bullets([("How", sol.get("approach")), ("Needs", sol.get("needs")), ("Risks", sol.get("risks"))]),
        "",
        "## Research",
        "\n".join(
            f"- {a['id']} ({cell(a.get('name'))}): {esc(a.get('digest')) or 'digest pending'}"
            for a in attachments
        )
        or "No research files yet.",
        "",
        "## Answers suggested by the assistant",
        (
            "| Field | Status |\n|---|---|\n" + "\n".join(f"| {cell(k)} | {v} |" for k, v in suggested)
            if suggested
            else "None. Every answer came from the submitter."
        ),
        "",
        "## Original text",
        quote(canvas.get("original_text")),
        "",
        HISTORY_HEADING,
        "| When | Event | By | Note |",
        "|---|---|---|---|",
        *[f"| {r.when} | {r.event} | {r.by} | {r.note} |" for r in history],
        "",
    ]
    return dump(meta, "\n" + "\n".join(sections))


def index_line(idea_id: str, description: str) -> str:
    return f"* [{idea_id}]({idea_id}.md) - {cell(description)}"
