"""The public wall (§4.13 "Public wall (Day 1)", AT-B7-01/04): recent org-visible ideas, recently picked
clusters, what is being built, what has shipped, and what already runs (`solutions/` in the company repo).
`wall.public` off: nothing (the web app shows the banner instead)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from core import killswitch
from core.config import get_settings
from core.db import Conn
from okf.frontmatter import FrontmatterError, parse
from views.common import (
    IN_GARAGE,
    PICKED,
    PUBLIC_STAGES,
    PUBLIC_WORDS,
    RECENT,
    SHIPPED,
    checked_summary,
    consenting_names,
    first_area,
    public_card,
    taxonomy_names,
)

LIMIT = 30
CACHE_S = 30.0  # the wall is the same for everyone: build it at most twice a minute (B7 review)
_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def _ideas(
    conn: Conn, stages: tuple[str, ...], areas: dict[str, str], limit: int, *, unclustered: bool = False
) -> list[dict[str, Any]]:
    """Org-visible ideas at these stages. Named only for the person who shared the idea, and only if they said
    yes; people who joined or added +1 are counted, never named (B7 review). An idea the desk or an admin took off
    the Wall is left out (`idea_off_wall`, DEC-106, BLD-A212)."""
    rows = conn.execute(
        "SELECT idea_id, stage, visibility, canvas, area_ids, contributor_code FROM ideas "
        "WHERE visibility = 'org' AND stage = ANY(%s) AND idea_id IS NOT NULL AND (NOT %s OR cluster_id IS NULL) "
        "AND NOT idea_off_wall(id) "
        "ORDER BY updated_at DESC, idea_id LIMIT %s",
        (list(stages), unclustered, limit),
    ).fetchall()
    out = []
    for r in rows:
        card = public_card(conn, dict(r), areas)
        if card is None:
            continue
        card["names"] = consenting_names(conn, [r["contributor_code"]])
        out.append(card)
    return out


def _clusters(conn: Conn, stages: tuple[str, ...], areas: dict[str, str], limit: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT c.id, c.stage, c.distinct_contributors, f.summary, f.area_ids FROM clusters c "
        "JOIN repo_files f ON f.kfin_id = c.id AND f.visibility = 'org' WHERE c.stage = ANY(%s) "
        "ORDER BY c.updated_at DESC, c.id LIMIT %s",
        (list(stages), limit),
    ).fetchall()
    out = []
    for r in rows:
        summary = checked_summary(conn, r["summary"])
        if summary is None:
            continue
        # Named: the people who shared a member idea that everyone may see. Never the owner of a committee-only
        # idea, never someone who only joined or added +1 (B7 review).
        sharers = [
            x["contributor_code"]
            for x in conn.execute(
                "SELECT DISTINCT contributor_code FROM ideas WHERE cluster_id = %s AND visibility = 'org' "
                "AND stage = ANY(%s)",
                (r["id"], list(PUBLIC_STAGES)),
            ).fetchall()
        ]
        out.append(
            {
                "cluster_id": r["id"],
                "summary": summary,
                "area": first_area(r["area_ids"], areas),
                "stage": PUBLIC_WORDS.get(r["stage"], "Grouped with similar ideas"),
                "colleagues": max(int(r["distinct_contributors"] or 0), len(sharers)),
                "names": consenting_names(conn, sharers),
            }
        )
    return out


def showcase(repo: Path | None = None) -> list[dict[str, Any]]:
    """Solutions the company already runs (`solutions/SOL-*.md`), newest first. Written by the product team, so
    the title and description are shown as they are."""
    repo = repo or get_settings().company_repo_path
    _, lobs = taxonomy_names()
    out = []
    for path in sorted((repo / "solutions").glob("SOL-*.md")):
        try:
            meta = parse(path.read_text(encoding="utf-8")).meta or {}
        except (FrontmatterError, OSError):
            continue
        k = meta.get("kfin") or {}
        if meta.get("type") != "solution" or (k.get("visibility") or "org") != "org":
            continue
        out.append(
            {
                "solution_id": str(k.get("id") or path.stem),
                "title": str(meta.get("title") or ""),
                "description": str(meta.get("description") or ""),
                "owner_team": lobs.get(str(k.get("owner_team") or ""), None),
                "shipped_on": str(k.get("shipped_on") or "") or None,
            }
        )
    return sorted(out, key=lambda s: (s["shipped_on"] or "", s["solution_id"]), reverse=True)


def wall(conn: Conn) -> dict[str, Any]:
    if not killswitch.is_on("wall.public", conn):
        return {"paused": True}  # checked on every request, never cached
    key = conn.info.dsn
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < CACHE_S:
        return hit[1]
    areas, _ = taxonomy_names()
    out = {
        "paused": False,
        "recent": _ideas(conn, RECENT, areas, LIMIT),
        # A cluster's member ideas take its stage: show the cluster, not each member again.
        "picked": _clusters(conn, PICKED, areas, 10) + _ideas(conn, PICKED, areas, 10, unclustered=True),
        "in_garage": _clusters(conn, IN_GARAGE, areas, 10)
        + _ideas(conn, IN_GARAGE, areas, 10, unclustered=True),
        "shipped": _clusters(conn, SHIPPED, areas, 10) + _ideas(conn, SHIPPED, areas, 10, unclustered=True),
        "showcase": showcase(),
    }
    _cache[key] = (time.monotonic(), out)
    return out


def clear_cache() -> None:
    _cache.clear()
