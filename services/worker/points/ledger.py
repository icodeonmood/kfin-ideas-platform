"""The points sync and a person's own view (BLD-130). Values come from `rules/points.md` in the company repo."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from core.config import get_settings
from core.db import Conn
from core.logging import get_logger
from rules import load_rule

log = get_logger("points")
IST = ZoneInfo("Asia/Kolkata")

# Stages an idea or group passes on its way (the decision flow, then delivery). Reaching a later one counts as
# having reached the earlier milestones on the usual path.
SHORTLISTED = ("shortlisted", "presenting", "picked", "handover", "in_garage", "in_fix_track", "shipped",
               "resolved", "measuring", "closed")  # fmt: skip
ACCEPTED = ("picked", "handover", "in_garage", "in_fix_track", "shipped", "resolved", "measuring", "closed")
SHIPPED = ("shipped", "resolved", "measuring", "closed")
REVIEWED_OR_LATER = ("reviewed", "in_cluster", "ready_for_scoring", "scored", *SHORTLISTED)

WORDS = {
    "submission": "You shared an idea",
    "joined_with_context": "You teamed up and said why",
    "strong_canvas": "A strong canvas",
    "accepted_into_cluster": "Your idea joined a group",
    "shortlisted": "Shortlisted",
    "accepted": "Picked",
    "shipped_or_resolved": "Shipped",
}
COMING_SOON = ["Presenting to the core committee", "Working group shipped", "Points restored after an appeal"]


def rules() -> dict[str, Any]:
    return dict(load_rule(get_settings().company_repo_path, "points").data)


def _month_key(ts: dt.datetime) -> tuple[int, int]:
    local = ts.astimezone(IST)
    return local.year, local.month


def _candidates(conn: Conn, r: dict[str, Any]) -> list[tuple[str, str, Decimal, str, dt.datetime]]:
    """(contributor_code, event, points, ref_id, when) for everything that has happened."""
    out: list[tuple[str, str, Decimal, str, dt.datetime]] = []

    def pts(value: Any) -> Decimal:
        return Decimal(str(value))

    for row in conn.execute(
        "SELECT idea_id, contributor_code, submitted_at, strength, stage FROM ideas "
        "WHERE stage NOT IN ('draft') AND submitted_at IS NOT NULL"
    ).fetchall():
        code, when = str(row["contributor_code"]), row["submitted_at"]
        out.append((code, "submission", pts(r["submission"]["points"]), str(row["idea_id"]), when))
        if row["stage"] in REVIEWED_OR_LATER and (row["strength"] or 0) >= 4:
            out.append((code, "strong_canvas", pts(r["strong_canvas"]["points"]), str(row["idea_id"]), when))
    for row in conn.execute(
        "SELECT id, contributor_code, created_at FROM idea_links WHERE link_type = 'joiner' "
        "AND coalesce(btrim(context_text), '') <> ''"
    ).fetchall():
        out.append((str(row["contributor_code"]), "joined_with_context",
                    pts(r["joined_with_context"]["points"]), f"link:{row['id']}", row["created_at"]))  # fmt: skip

    # Groups and later milestones: originators are the ideas' own authors; joiners teamed up after a match.
    people: list[tuple[str, str, str, str, dt.datetime]] = []  # (code, role, subject, stage, when)
    for row in conn.execute(
        "SELECT i.idea_id, i.cluster_id, i.contributor_code, i.stage, c.stage AS cluster_stage, "
        "coalesce(i.submitted_at, i.created_at) AS at FROM ideas i LEFT JOIN clusters c ON c.id = i.cluster_id "
        "WHERE i.stage <> 'draft'"
    ).fetchall():
        subject = str(row["cluster_id"] or row["idea_id"])
        stage = str(row["cluster_stage"] or row["stage"]) if row["cluster_id"] else str(row["stage"])
        people.append((str(row["contributor_code"]), "originator", subject, stage, row["at"]))
        if row["cluster_id"] and row["stage"] not in ("withdrawn", "declined", "parked"):
            out.append((str(row["contributor_code"]), "accepted_into_cluster",
                        pts(r["accepted_into_cluster"]["originator"]), str(row["cluster_id"]), row["at"]))  # fmt: skip
    for row in conn.execute(
        "SELECT l.contributor_code, coalesce(l.idea_id, l.cluster_id) AS subject, l.created_at, "
        "coalesce(c.stage, i.stage) AS stage, l.cluster_id FROM idea_links l "
        "LEFT JOIN ideas i ON i.idea_id = l.idea_id LEFT JOIN clusters c ON c.id = l.cluster_id "
        "WHERE l.link_type = 'joiner' AND (l.idea_id IS NOT NULL OR l.cluster_id IS NOT NULL)"
    ).fetchall():
        people.append((str(row["contributor_code"]), "joiner", str(row["subject"]), str(row["stage"] or ""),
                       row["created_at"]))  # fmt: skip
        if row["cluster_id"]:
            out.append((str(row["contributor_code"]), "accepted_into_cluster",
                        pts(r["accepted_into_cluster"]["joiner"]), str(row["cluster_id"]), row["created_at"]))  # fmt: skip
    for code, role, subject, stage, when in people:
        for event, stages in (("shortlisted", SHORTLISTED), ("accepted", ACCEPTED),
                              ("shipped_or_resolved", SHIPPED)):  # fmt: skip
            if stage in stages:
                out.append((code, event, pts(r[event][role]), subject, when))
    return out


def sync(conn: Conn) -> int:
    """Record every award not yet in the ledger, oldest first, within each monthly cap. Idempotent."""
    r = rules()
    caps = {k: int(v["monthly_cap"]) for k, v in r.items() if isinstance(v, dict) and "monthly_cap" in v}
    added = 0
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(hashtext('points.sync'))")  # one sync at a time
        have = {
            (str(x["contributor_code"]), str(x["event"]), str(x["ref_id"]))
            for x in conn.execute(
                "SELECT contributor_code, event, ref_id FROM points_ledger WHERE ref_id IS NOT NULL"
            )
        }
        used: dict[tuple[str, str, int, int], int] = {}
        for x in conn.execute(
            "SELECT contributor_code, event, created_at FROM points_ledger WHERE event = ANY(%s)",
            (list(caps),),
        ).fetchall():
            key = (str(x["contributor_code"]), str(x["event"]), *_month_key(x["created_at"]))
            used[key] = used.get(key, 0) + 1
        for code, event, points, ref, when in sorted(_candidates(conn, r), key=lambda c: (c[4], c[3])):
            if (code, event, ref) in have:
                continue
            if event in caps:
                key = (code, event, *_month_key(when))
                if used.get(key, 0) >= caps[event]:
                    continue
                used[key] = used.get(key, 0) + 1
            conn.execute(
                "INSERT INTO points_ledger (contributor_code, event, points, ref_id, created_at) "
                "VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                (code, event, points, ref, when),
            )
            have.add((code, event, ref))
            added += 1
    if added:
        log.info("points.synced", rows_added=added)  # a count only, never who or what
    return added


def mine(conn: Conn, user_id: str, now: dt.datetime | None = None) -> dict[str, Any]:
    """A person's own points: the total, the last 12 months and the latest awards. Never anyone else's."""
    now = now or dt.datetime.now(dt.UTC)
    codes = [str(x["contributor_code"]) for x in conn.execute(
        "SELECT contributor_code FROM contributor_map WHERE user_id = %s", (user_id,)).fetchall()]  # fmt: skip
    if not codes:
        return {"total": 0, "last_12_months": 0, "recent": [], "coming_soon": COMING_SOON}
    totals = conn.execute(
        "SELECT coalesce(sum(points), 0) AS total, coalesce(sum(points) FILTER (WHERE created_at >= %s), 0) AS year "
        "FROM points_ledger WHERE contributor_code = ANY(%s)",
        (now - dt.timedelta(days=365), codes),
    ).fetchone()
    recent = [
        {
            "what": WORDS.get(str(x["event"]), "Points"),
            "points": float(x["points"]),
            "on": x["created_at"].isoformat(),
        }
        for x in conn.execute(
            "SELECT event, points, created_at FROM points_ledger WHERE contributor_code = ANY(%s) "
            "ORDER BY created_at DESC, id DESC LIMIT 10",
            (codes,),
        ).fetchall()
    ]
    return {
        "total": float(totals["total"]) if totals else 0,
        "last_12_months": float(totals["year"]) if totals else 0,
        "recent": recent,
        "coming_soon": COMING_SOON,
    }
