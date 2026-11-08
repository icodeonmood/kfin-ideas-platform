"""Shared rules for the public pages (§4.13 wall, §4.2 step 7, §3.1).

- An idea reaches the wall, or another person's view of its page, only once the review desk has accepted it
  (stage `reviewed` or later, never declined, parked, redirected, withdrawn or held): the desk is the
  moderation step before anything is shown to everyone (BLD-094).
- Other people see only the neutral summary (re-checked before display), the area tag, the stage in plain
  words and the number of colleagues on it. Never the person's own words, files or contributor code.
- Names appear only on the wall, and only for people who said yes to `public_name_consent`.
"""

from __future__ import annotations

import time
from typing import Any

from core.config import get_settings
from core.db import Conn
from scan.inputs import _taxonomy
from scan.matching import safe_summary

RECENT = ("reviewed", "in_cluster", "ready_for_scoring", "scored", "shortlisted", "presenting")
PICKED = ("picked",)
IN_GARAGE = ("handover", "in_garage", "in_fix_track")
SHIPPED = ("shipped", "resolved", "measuring", "closed")
PUBLIC_STAGES = RECENT + PICKED + IN_GARAGE + SHIPPED

# What everyone else sees. Never "duplicate", "rejected" or "already solved" (CLAUDE.md, words on screen).
PUBLIC_WORDS = {
    "reviewed": "Reviewed",
    "in_cluster": "Grouped with similar ideas",
    "ready_for_scoring": "Being assessed",
    "scored": "Being assessed",
    "shortlisted": "Shortlisted",
    "presenting": "Being presented",
    "picked": "Picked for the Garage",
    "handover": "In the Garage",
    "in_garage": "In the Garage",
    "in_fix_track": "Being fixed",
    "shipped": "Shipped",
    "resolved": "Fixed",
    "measuring": "Shipped",
    "closed": "Shipped",
}

_SAFE_TTL_S = 600
_safe_cache: dict[str, tuple[float, str | None]] = {}


def checked_summary(conn: Conn, summary: str | None) -> str | None:
    """The neutral summary if it passes the checks (tags, patterns, names), else None. Cached for ten minutes:
    the wall shows the same few dozen summaries to everyone."""
    if not summary:
        return None
    key = f"{conn.info.dsn}|{summary}"
    hit = _safe_cache.get(key)
    if hit and time.monotonic() - hit[0] < _SAFE_TTL_S:
        return hit[1]
    out = safe_summary(conn, summary)
    if len(_safe_cache) > 2000:
        _safe_cache.clear()
    _safe_cache[key] = (time.monotonic(), out)
    return out


def taxonomy_names() -> tuple[dict[str, str], dict[str, str]]:
    tax = _taxonomy(get_settings().company_repo_path)
    return {a["id"]: a["name"] for a in tax["areas"]}, {x["id"]: x["name"] for x in tax["lobs"]}


def first_area(area_ids: list[str] | None, areas: dict[str, str]) -> str | None:
    return next((areas[a] for a in area_ids or [] if a in areas), None)


def colleague_codes(conn: Conn, idea_id: str, owner_code: str) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT contributor_code FROM idea_links WHERE idea_id = %s "
        "AND link_type IN ('originator', 'joiner', 'plus_one')",
        (idea_id,),
    ).fetchall()
    return sorted({owner_code, *[r["contributor_code"] for r in rows]})


def consenting_names(conn: Conn, codes: list[str]) -> list[str]:
    """Names of the people behind these codes who agreed to be named on the wall (and still work here)."""
    if not codes:
        return []
    rows = conn.execute(
        "SELECT DISTINCT u.name FROM contributor_map m JOIN users u ON u.id = m.user_id "
        "JOIN comms_prefs p ON p.user_id = u.id WHERE m.contributor_code = ANY(%s) AND p.public_name_consent "
        "AND u.active ORDER BY u.name",
        (codes,),
    ).fetchall()
    return [str(r["name"]) for r in rows]


def is_public(idea: dict[str, Any]) -> bool:
    return idea["visibility"] == "org" and idea["stage"] in PUBLIC_STAGES


def public_card(conn: Conn, idea: dict[str, Any], areas: dict[str, str]) -> dict[str, Any] | None:
    """The card everyone may see, or None if the summary does not pass its checks (then it is simply left out)."""
    summary = checked_summary(conn, (idea.get("canvas") or {}).get("neutral_summary"))
    if summary is None:
        return None
    return {
        "idea_id": idea["idea_id"],
        "summary": summary,
        "area": first_area(idea["area_ids"], areas),
        "stage": PUBLIC_WORDS.get(idea["stage"], "Reviewed"),
        "colleagues": len(colleague_codes(conn, idea["idea_id"], idea["contributor_code"])),
    }
