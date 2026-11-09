"""Company repo documents written from approved records (BLD-133, BLD-136): solution write-ups (`solutions/`),
glossary terms (`taxonomy/glossary/`) and area tags (`taxonomy/areas/`). Text in them was checked before it was
approved; everything is escaped so it stays inert Markdown. Frontmatter follows the OKF concept rules."""

from __future__ import annotations

import datetime as dt
from typing import Any

from okf.frontmatter import dump
from repo_writer.render import esc as _esc
from repo_writer.render import iso


def esc(text: str | None) -> str:
    """The idea files' escaping, plus brackets: text everyone reads can't become a link (no `javascript:`)."""
    return _esc(text).replace("[", "\\[").replace("]", "\\]")


def _one_sentence(text: str, limit: int = 200) -> str:
    first = text.split(". ")[0].strip()
    first = first if first.endswith(".") else first + "."
    return first if len(first) <= limit else first[: limit - 1].rstrip() + "…"


def render_solution(sol: str, parts: dict[str, str], facts: dict[str, Any]) -> str:
    """`facts`: approved_at, owner_team (LOB- or None), lobs, areas, source_cluster, shipped_on, delivery_id."""
    approved: dt.datetime = facts["approved_at"]
    meta: dict[str, Any] = {
        "type": "solution",
        "title": parts["title"],
        "description": _one_sentence(parts["what_it_does"]),
        "tags": ["solution"],
        "status": "stable",
        "generated": {"by": "process:solution-writeup", "at": iso(approved)},
        "verified": [{"by": "process:sponsor-approval", "at": iso(approved)}],
        "stale_after": iso(approved + dt.timedelta(days=182)),
        "kfin": {
            "id": sol,
            "owner_team": facts.get("owner_team"),
            "owner_role": "The delivery's owner (see How another team can adopt it)",
            "lobs_in_use": list(facts.get("lobs") or []),
            "areas": list(facts.get("areas") or []),
            "systems": [],
            "source_cluster": facts.get("source_cluster"),
            "garage_feature_slug": None,
            "shipped_on": facts.get("shipped_on"),
            "delivery_id": facts.get("delivery_id"),
        },
    }
    body = [
        "## What it does",
        esc(parts["what_it_does"]),
        "",
        "## Where it runs",
        esc(parts["where_it_runs"]),
        "",
        "## Result",
        esc(parts["result"]),
        "",
        "## How another team can adopt it",
        esc(parts["how_to_adopt"]),
        "",
    ]
    return dump(meta, "\n" + "\n".join(body))


def doc_index_line(doc_id: str, title: str) -> str:
    """The same line style as the seeded index files: `- [GL-nav.md](GL-nav.md) — NAV`."""
    return f"- [{doc_id}.md]({doc_id}.md) — {esc(title).replace(chr(10), ' ')}"


def render_glossary_term(gid: str, term: str, definition: str, aliases: list[str], at: dt.datetime) -> str:
    meta: dict[str, Any] = {
        "type": "glossary-term",
        "title": term,
        "description": definition,
        "tags": ["glossary"],
        "status": "draft",
        "generated": {"by": "process:learning-approval", "at": iso(at)},
        "kfin": {
            "id": gid,
            "term": term,
            "aliases": sorted({term, *aliases}),
            "owning_team": None,
            "definition_confirmed": True,
        },
    }
    body = [
        f"## {esc(term)}",
        "",
        esc(definition),
        "",
        "## Related",
        "",
        "Clusters and solutions that mention this term are linked here by the indexer.",
        "",
    ]
    return dump(meta, "\n" + "\n".join(body))


def render_area_tag(area_id: str, title: str, description: str, at: dt.datetime) -> str:
    meta: dict[str, Any] = {
        "type": "area-tag",
        "title": title,
        "description": description,
        "tags": ["taxonomy", "area"],
        "status": "draft",
        "generated": {"by": "process:learning-approval", "at": iso(at)},
        "kfin": {"id": area_id},
    }
    body = [
        f"## {esc(title)}",
        "",
        esc(description),
        "",
        "Internal tag for search and routing. Submitters are never asked for it; `canvas-assist` proposes it and "
        "the review desk confirms.",
        "",
    ]
    return dump(meta, "\n" + "\n".join(body))
