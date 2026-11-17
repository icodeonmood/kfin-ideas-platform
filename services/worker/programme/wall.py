"""Taking an idea off the Wall (DEC-106, SHIP_PLAN_1PC §6.3): the review desk or an admin takes a shared idea's
summary off the Wall, with a reason, and can put it back. Both are audited. It replaces the retired spam hold and
committee-only visibility; the idea itself, its decision and its people are untouched.

Readers filter with the database function `idea_off_wall(idea uuid)` (20261122100400), through lane E's one Wall
filter, `wall.common.on_wall_sql` (Kindling, Just in, the live fixes), and the old wall view. Nobody acts on an idea
they shared (as on the desk, L-AUDIT.permissions).
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import psycopg

from core.db import Conn
from programme.common import Refused, audit, idea, need, now_utc, owner_user, reason

STAFF = {"reviewer", "admin"}


def _clear_wall_cache() -> None:
    """The Wall shows the change at once: lane E's Kindling and Just in cache, and the old wall view's."""
    from views.wall import clear_cache
    from wall import kindling

    clear_cache()
    kindling.clear_cache()


def take_off(
    conn: Conn, actor: str, ref: Any, body: dict[str, Any], now: dt.datetime | None = None
) -> dict[str, Any]:
    now = now or now_utc()
    need(conn, actor, STAFF)
    why = reason(body.get("reason"))
    try:
        with conn.transaction():
            row = idea(conn, ref, lock=True)
            if row["shared_at"] is None and row["status"] in ("draft", "checking"):
                raise Refused(
                    409, "not_shared", "This idea is not on the Wall. It hasn't been shared.", field="idea"
                )
            if owner_user(conn, row["contributor_code"]) == actor:
                raise Refused(403, "own_idea", "Someone else takes your own idea off the Wall.", field="idea")
            removal = conn.execute(
                "INSERT INTO wall_removals (idea_uuid, by, reason, at) VALUES (%s, %s, %s, %s) RETURNING id",
                (row["id"], actor, why, now),
            ).fetchone()
            assert removal is not None
            audit(conn, actor, "wall.taken_off", f"idea:{row['idea_id']}", {"wall_removal_id": int(removal["id"])},
                  reason=why)  # fmt: skip
    except psycopg.errors.UniqueViolation:
        raise Refused(409, "already_off", "This idea is already off the Wall.", field="idea") from None
    _clear_wall_cache()
    return {"idea": row["idea_id"], "off_wall": True, "id": int(removal["id"])}


def restore(
    conn: Conn, actor: str, ref: Any, body: dict[str, Any], now: dt.datetime | None = None
) -> dict[str, Any]:
    now = now or now_utc()
    need(conn, actor, STAFF)
    why = reason(body.get("reason"))
    with conn.transaction():
        row = idea(conn, ref, lock=True)
        done = conn.execute(
            "UPDATE wall_removals SET restored_at = %s, restored_by = %s, restore_reason = %s "
            "WHERE idea_uuid = %s AND restored_at IS NULL RETURNING id",
            (now, actor, why, row["id"]),
        ).fetchone()
        if done is None:
            raise Refused(409, "not_off", "This idea is on the Wall already.", field="idea")
        audit(conn, actor, "wall.restored", f"idea:{row['idea_id']}", {"wall_removal_id": int(done["id"])},
              reason=why)  # fmt: skip
    _clear_wall_cache()
    return {"idea": row["idea_id"], "off_wall": False}


def removals(conn: Conn) -> list[dict[str, Any]]:
    """Ideas off the Wall now, newest first, with who took each off and why (staff only)."""
    rows = conn.execute(
        "SELECT r.id, r.reason, r.at, i.idea_id, i.title, u.name AS by_name FROM wall_removals r "
        "JOIN ideas i ON i.id = r.idea_uuid JOIN users u ON u.id = r.by WHERE r.restored_at IS NULL "
        "ORDER BY r.at DESC"
    ).fetchall()
    return [
        {"id": int(r["id"]), "idea_ref": r["idea_id"], "title": r["title"] or "", "by": r["by_name"],
         "reason": r["reason"], "at": r["at"].isoformat()}
        for r in rows
    ]  # fmt: skip
