"""What the admin page shows (lane A's minimal admin page): only the parts the person's grants allow. The review
desk sees "Take off the Wall"; admins see everything. Titles are the ideas' masked titles (L-HIDE.rules/3)."""

from __future__ import annotations

import datetime as dt
from typing import Any

from core.db import Conn
from programme import impact, ones, wall
from programme.common import Refused, day_label, roles


def _ideas(conn: Conn, status: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT i.idea_id, i.title, i.status_changed_at, bt.name AS team, u.name AS lead FROM ideas i "
        "LEFT JOIN build_teams bt ON bt.idea_uuid = i.id LEFT JOIN users u ON u.id = bt.lead_user_id "
        "WHERE i.status = %s AND i.idea_id IS NOT NULL ORDER BY i.status_changed_at DESC NULLS LAST, i.idea_id "
        "LIMIT 100",
        (status,),
    ).fetchall()
    return [
        {"idea_ref": r["idea_id"], "title": r["title"] or "", "team": r["team"], "lead": r["lead"],
         "since": r["status_changed_at"].isoformat() if r["status_changed_at"] else None,
         "since_label": day_label(r["status_changed_at"], year=True) if r["status_changed_at"] else None}
        for r in rows
    ]  # fmt: skip


def admin_view(conn: Conn, user_id: str, now: dt.datetime) -> dict[str, Any]:
    have = roles(conn, user_id)
    is_admin = "admin" in have
    if not is_admin and "reviewer" not in have:
        raise Refused(403, "forbidden", "You can't open this page.")
    out: dict[str, Any] = {
        "can": {"programme": is_admin, "wall": True},
        "off_wall": wall.removals(conn),
    }
    if is_admin:
        out.update(
            picked=_ideas(conn, "picked"),
            being_built=_ideas(conn, "being_built"),
            shipped=_ideas(conn, "shipped"),
            due=impact.due(conn, now),
            entered=[{**m, "entered_by_me": m.pop("entered_by") == user_id} for m in impact.entered(conn)],
            ones=ones.list_ones(conn),
            scale_nouns=list(impact.SCALE_NOUNS),
        )
    return out
