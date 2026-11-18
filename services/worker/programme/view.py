"""What the admin page shows (lane A's minimal admin page): only the parts the person's grants allow. The review
desk sees "Take off the Wall"; admins see everything. Titles are the ideas' masked titles (L-HIDE.rules/3).

Each picked idea carries `asked_to_join`: who asked to join its build team (L-DECIDE.rules/6, DEC-111, BLD-A226),
oldest first, from lane B's `desk.join_build.asks_for_idea` as it returns them (id, name, time; no email), plus the
page's day label. The admin sees them while choosing the team (J-ONE step 1)."""

from __future__ import annotations

import datetime as dt
from typing import Any

from core.db import Conn
from desk import join_build
from programme import impact, ones, wall
from programme.common import Refused, day_label, roles


def _ideas(conn: Conn, status: str, *, with_uuid: bool = False) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT i.id, i.idea_id, i.title, i.status_changed_at, bt.name AS team, u.name AS lead FROM ideas i "
        "LEFT JOIN build_teams bt ON bt.idea_uuid = i.id LEFT JOIN users u ON u.id = bt.lead_user_id "
        "WHERE i.status = %s AND i.idea_id IS NOT NULL ORDER BY i.status_changed_at DESC NULLS LAST, i.idea_id "
        "LIMIT 100",
        (status,),
    ).fetchall()
    return [
        {"idea_ref": r["idea_id"], "title": r["title"] or "", "team": r["team"], "lead": r["lead"],
         "since": r["status_changed_at"].isoformat() if r["status_changed_at"] else None,
         "since_label": day_label(r["status_changed_at"], year=True) if r["status_changed_at"] else None,
         **({"uuid": str(r["id"])} if with_uuid else {})}
        for r in rows
    ]  # fmt: skip


def _asked_to_join(conn: Conn, idea_uuid: str) -> list[dict[str, Any]]:
    """Who asked to join the build team (L-DECIDE.rules/6): lane B's read, oldest first, each with the page's label
    ("18 Nov 2026", as `since_label`). On an idea a Pick joined to another, the asks are on the lead idea (BLD-B256),
    which is the one in the picked list."""
    return [
        {**a, "asked_label": day_label(dt.datetime.fromisoformat(a["asked_at"]), year=True)}
        for a in join_build.asks_for_idea(conn, idea_uuid)
    ]


def _picked(conn: Conn) -> list[dict[str, Any]]:
    rows = _ideas(conn, "picked", with_uuid=True)
    for r in rows:
        r["asked_to_join"] = _asked_to_join(conn, r.pop("uuid"))
    return rows


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
            picked=_picked(conn),
            being_built=_ideas(conn, "being_built"),
            shipped=_ideas(conn, "shipped"),
            due=impact.due(conn, now),
            entered=[{**m, "entered_by_me": m.pop("entered_by") == user_id} for m in impact.entered(conn)],
            ones=ones.list_ones(conn),
            scale_nouns=list(impact.SCALE_NOUNS),
        )
    return out
