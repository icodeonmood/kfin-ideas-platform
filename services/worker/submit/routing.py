"""L-SORT.rules/7: the area maps to a review queue. The map is configuration owned by the review desk lead
(`rules/sorting.md` review_routing). Until the lead sends one, every area goes to any reviewer, never the sharer
(SHIP_PLAN §8). Routing follows the latest area, so a change in the edit window or a reviewer's recategorising
moves the idea with no extra step (`L-SORT.rules/6`).

Lane B's desk asks `may_review` before showing or opening an idea, and `reviewers_for` names the people the queue
belongs to. The sharer never reviews their own idea, whatever the map says (L-REVIEW, `refuse_own`).
"""

from __future__ import annotations

from typing import Any

from core.db import Conn
from submit import config

REVIEWER_ROLES = ("reviewer",)


def _active_reviewers(conn: Conn) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT DISTINCT u.id, lower(u.email) AS email FROM role_grants g JOIN users u ON u.id = g.user_id "
        "WHERE g.role = ANY(%s) AND g.valid_to IS NULL AND u.active ORDER BY u.id",
        (list(REVIEWER_ROLES),),
    ).fetchall()
    return [dict(r) for r in rows]


def _sharer_user(conn: Conn, idea: dict[str, Any]) -> str | None:
    row = conn.execute(
        "SELECT user_id FROM contributor_map WHERE contributor_code = %s", (idea["contributor_code"],)
    ).fetchone()
    return str(row["user_id"]) if row else None


def reviewers_for(conn: Conn, idea: dict[str, Any], li: config.Lists | None = None) -> list[str]:
    """The users.id values whose queue this idea is in: the area's reviewers from the map, or any reviewer when the
    area is not mapped or none of its reviewers is active. Never the sharer."""
    li = li or config.lists()
    everyone = _active_reviewers(conn)
    sharer = _sharer_user(conn, idea)
    eligible = [r for r in everyone if str(r["id"]) != sharer]
    area = li.area_label(idea.get("area")) if idea.get("area") else None
    mapped = next((v for k, v in li.routing_areas.items() if area and k.casefold() == area.casefold()), ())
    if mapped:
        wanted = {e.casefold() for e in mapped}
        named = [r for r in eligible if (r["email"] or "").casefold() in wanted]
        if named:
            return [str(r["id"]) for r in named]
    return [str(r["id"]) for r in eligible]


def may_review(conn: Conn, idea: dict[str, Any], user_id: str) -> bool:
    return user_id in reviewers_for(conn, idea)
