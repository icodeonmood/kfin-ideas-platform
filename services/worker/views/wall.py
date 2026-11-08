"""The public wall (§4.13 "Public wall (Day 1)", AT-B7-01/04): recent org-visible ideas, recently picked
clusters, what is in the Garage, what has shipped, and the Garage showcase from `solutions/` in the company repo.
`wall.public` off: nothing (the web app shows the banner instead)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core import killswitch
from core.config import get_settings
from core.db import Conn
from okf.frontmatter import FrontmatterError, parse
from views.common import (
    IN_GARAGE,
    PICKED,
    PUBLIC_WORDS,
    RECENT,
    SHIPPED,
    checked_summary,
    colleague_codes,
    consenting_names,
    first_area,
    public_card,
    taxonomy_names,
)

LIMIT = 30


def _ideas(conn: Conn, stages: tuple[str, ...], areas: dict[str, str], limit: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT idea_id, stage, visibility, canvas, area_ids, contributor_code FROM ideas "
        "WHERE visibility = 'org' AND stage = ANY(%s) AND idea_id IS NOT NULL ORDER BY updated_at DESC, idea_id "
        "LIMIT %s",
        (list(stages), limit),
    ).fetchall()
    out = []
    for r in rows:
        card = public_card(conn, dict(r), areas)
        if card is None:
            continue
        card["names"] = consenting_names(conn, colleague_codes(conn, r["idea_id"], r["contributor_code"]))
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
        codes = [
            x["contributor_code"]
            for x in conn.execute(
                "SELECT DISTINCT contributor_code FROM idea_links WHERE cluster_id = %s "
                "UNION SELECT contributor_code FROM ideas WHERE cluster_id = %s AND visibility = 'org'",
                (r["id"], r["id"]),
            ).fetchall()
        ]
        out.append(
            {
                "cluster_id": r["id"],
                "summary": summary,
                "area": first_area(r["area_ids"], areas),
                "stage": PUBLIC_WORDS.get(r["stage"], "Grouped with similar ideas"),
                "colleagues": int(r["distinct_contributors"] or len(codes)),
                "names": consenting_names(conn, codes),
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
        return {"paused": True}
    areas, _ = taxonomy_names()
    return {
        "paused": False,
        "recent": _ideas(conn, RECENT, areas, LIMIT),
        "picked": _clusters(conn, PICKED, areas, 10) + _ideas(conn, PICKED, areas, 10),
        "in_garage": _clusters(conn, IN_GARAGE, areas, 10) + _ideas(conn, IN_GARAGE, areas, 10),
        "shipped": _clusters(conn, SHIPPED, areas, 10) + _ideas(conn, SHIPPED, areas, 10),
        "showcase": showcase(),
    }
