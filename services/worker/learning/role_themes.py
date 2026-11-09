"""Recurring friction themes for each role (BLD-139), a weekly learning loop (Mondays, behind `learning.jobs`).

For each role with enough recent org-visible ideas, the `role-themes` agent groups their checked neutral summaries
into up to four themes, through the gateway. Kept: each theme's checked name and description and how many ideas
share it. Never idea IDs, idea text or names. Agents propose; the product team approves or declines each role's
set, and only approved themes show on the lenses page, as counts."""

from __future__ import annotations

import datetime as dt
from typing import Any

from psycopg.types.json import Jsonb

from core.config import get_settings
from core.db import Conn
from core.logging import get_logger
from ones.text import OnesRefused
from scan.inputs import _taxonomy

log = get_logger("learning.role_themes")
WINDOW_DAYS = 90
MIN_IDEAS = 4
MAX_IDEAS = 40


def _role_names() -> dict[str, str]:
    return {r["id"]: r["name"] for r in _taxonomy(get_settings().company_repo_path)["roles"]}


def propose(conn: Conn, now: dt.datetime, period: str) -> int:
    from gateway import AgentFailed, run_agent
    from views.common import checked_summary, taxonomy_names

    areas, lobs = taxonomy_names()
    added = failed = 0
    for role_id, role_name in sorted(_role_names().items()):
        if conn.execute(
            "SELECT 1 FROM role_themes WHERE role_id = %s AND period = %s", (role_id, period)
        ).fetchone():
            continue
        rows = conn.execute(
            "SELECT canvas ->> 'neutral_summary' AS summary, area_ids, lobs FROM ideas WHERE visibility = 'org' "
            "AND stage NOT IN ('draft', 'scanning', 'blocked', 'withdrawn') AND %s = ANY(roles_affected) "
            "AND submitted_at >= %s ORDER BY submitted_at DESC LIMIT %s",
            (role_id, now - dt.timedelta(days=WINDOW_DAYS), MAX_IDEAS),
        ).fetchall()
        ideas: list[dict[str, Any]] = []
        for r in rows:
            summary = checked_summary(conn, r["summary"])
            if summary:
                ideas.append({
                    "ref": f"I{len(ideas) + 1}", "summary": summary,
                    "areas": [areas.get(a, a) for a in r["area_ids"] or []][:3],
                    "lobs": [lobs.get(x, x) for x in r["lobs"] or []][:3],
                })  # fmt: skip
        if len(ideas) < MIN_IDEAS:
            continue
        try:
            out = run_agent(
                "role-themes", {"role": role_name, "ideas": ideas}, f"{role_id}:{period}", conn=conn
            )
        except AgentFailed:
            failed += 1
            continue
        themes = [
            {"name": t["name"], "description": t["description"], "ideas": len(set(t["refs"]))}
            for t in out.data["themes"]
        ]
        row = conn.execute(
            "INSERT INTO role_themes (role_id, period, themes, ideas_considered) VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (role_id, period) DO NOTHING RETURNING id",
            (role_id, period, Jsonb(themes), len(ideas)),
        ).fetchone()
        added += row is not None
    log.info("learning.role_themes", proposed=added, failed=failed)  # counts only
    return added


def decide(
    conn: Conn, actor: str, theme_id: Any, body: dict[str, Any], now: dt.datetime | None = None
) -> dict[str, Any]:
    """The product team (an admin) approves or declines one role's themes. Audited; nothing else moves."""
    from ones.service import roles

    now = now or dt.datetime.now(dt.UTC)
    try:
        tid = int(theme_id)
    except (TypeError, ValueError):
        raise OnesRefused(404, "not_found") from None
    verdict = body.get("verdict")
    if verdict not in ("approve", "decline"):
        raise OnesRefused(400, "verdict_required")
    if "admin" not in roles(conn, actor):
        raise OnesRefused(403, "forbidden")
    with conn.transaction():
        row = conn.execute("SELECT * FROM role_themes WHERE id = %s FOR UPDATE", (tid,)).fetchone()
        if row is None:
            raise OnesRefused(404, "not_found")
        if row["state"] != "proposed":
            raise OnesRefused(409, "not_open")
        state = "approved" if verdict == "approve" else "declined"
        conn.execute(
            "UPDATE role_themes SET state = %s, decided_by = %s, decided_at = %s WHERE id = %s",
            (state, actor, now, tid),
        )
        conn.execute(
            "INSERT INTO audit_log (actor, action, entity, after) VALUES (%s, %s, %s, %s)",
            (
                f"user:{actor}",
                f"learning.role_themes_{state}",
                f"role_themes:{tid}",
                Jsonb({"role": row["role_id"]}),
            ),
        )
    return {"id": tid, "state": state}


def _shape(conn: Conn, r: dict[str, Any], names: dict[str, str]) -> dict[str, Any]:
    return {
        "id": int(r["id"]), "role": names.get(str(r["role_id"]), "A role"), "period": r["period"],
        "state": r["state"], "themes": list(r["themes"] or []), "ideas_considered": int(r["ideas_considered"]),
    }  # fmt: skip


def listing(conn: Conn) -> list[dict[str, Any]]:
    """For the learning page (admins): proposals first, then recent decisions."""
    names = _role_names()
    rows = conn.execute(
        "SELECT * FROM role_themes ORDER BY (state = 'proposed') DESC, created_at DESC LIMIT 60"
    ).fetchall()
    return [_shape(conn, dict(r), names) for r in rows]


def approved(conn: Conn) -> list[dict[str, Any]]:
    """For the lenses page (committees and admins): each role's latest approved themes."""
    names = _role_names()
    rows = conn.execute(
        "SELECT DISTINCT ON (role_id) * FROM role_themes WHERE state = 'approved' ORDER BY role_id, created_at DESC"
    ).fetchall()
    return sorted((_shape(conn, dict(r), names) for r in rows), key=lambda x: x["role"])
