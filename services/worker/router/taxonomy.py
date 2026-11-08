"""P2 `taxonomy_slice`: the glossary systems a text mentions (exact, then fuzzy with pg_trgm), plus the full,
small lists of LOBs, area tags, roles, categories and plays for canvas assist."""

from __future__ import annotations

import re
from typing import Any

from core.db import Conn
from scan.inputs import _taxonomy  # the repo's LOB, area, role and glossary lists (cached per minute)

FUZZY_MIN = 0.4  # §3.3 P2
CATEGORIES = ["cost_saving", "new_revenue", "both", "not_sure"]
PLAYS = ["process_improvement", "upsell", "cross_sell", "new_product", "other"]


def glossary_ids(conn: Conn, text: str) -> list[str]:
    """GL- IDs whose term or alias appears in the text: exactly, or as a near spelling (pg_trgm strict word
    similarity ≥ 0.4, only for aliases of five or more characters, so SIP and SIF never stand in for each other)."""
    rows = conn.execute(
        "SELECT glossary_id, alias, strict_word_similarity(lower(alias), lower(%s)) AS fuzzy FROM terms",
        (text,),
    ).fetchall()
    best: dict[str, float] = {}
    for r in rows:
        alias = str(r["alias"])
        exact = re.search(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", text, re.I) is not None
        score = 1.0 if exact else (float(r["fuzzy"]) if len(alias) >= 5 else 0.0)
        best[r["glossary_id"]] = max(best.get(r["glossary_id"], 0.0), score)
    return [g for g, score in sorted(best.items(), key=lambda h: (-h[1], h[0])) if score >= FUZZY_MIN][:30]


def taxonomy_slice(conn: Conn, text: str) -> dict[str, Any]:
    t = _taxonomy_lists()
    names = {g["id"]: g["name"] for g in t["glossary"]}
    return {
        "lobs": [{"id": x["id"], "name": x["name"]} for x in t["lobs"]],
        "areas": [{"id": x["id"], "name": x["name"]} for x in t["areas"]],
        "systems": [{"id": g, "name": names.get(g, g)} for g in glossary_ids(conn, text)],
        "roles": [{"id": x["id"], "name": x["name"]} for x in t["roles"]],
        "categories": CATEGORIES,
        "plays": PLAYS,
    }


def _taxonomy_lists() -> dict[str, Any]:
    from core.config import get_settings

    return _taxonomy(get_settings().company_repo_path)
