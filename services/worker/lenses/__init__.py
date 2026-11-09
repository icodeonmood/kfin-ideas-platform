"""Lenses (§4.14): counts by line of business and by role, rebuilt weekly, and the people lens for working groups.
Counts only, never names or idea text; visible to committees and admins."""

from __future__ import annotations

import datetime as dt
from collections import Counter
from typing import Any

from psycopg.types.json import Jsonb

from core.config import get_settings
from core.db import Conn
from core.logging import get_logger
from scan.inputs import _taxonomy
from sla.calendar import add_working_days

log = get_logger("lenses")

# Plain groups of stages for the lens tables (the stage words people already know, DEC-038).
STAGE_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("With the review desk", ("scanned", "needs_info", "merged", "adoption_requested")),
    ("Reviewed or grouped", ("reviewed", "in_cluster")),
    ("Being assessed", ("ready_for_scoring", "scored", "shortlisted", "presenting")),
    ("Picked", ("picked",)),
    ("Being built", ("handover", "in_garage", "in_fix_track")),
    ("Shipped", ("shipped", "resolved", "measuring", "closed")),
    ("Parked or not taken up", ("parked", "declined", "already_solved", "already_planned", "appealed")),
)
COUNTED = tuple(s for _, stages in STAGE_GROUPS for s in stages)
AGEING_WD = 5
RELATED = 0.75  # centroid cosine similarity for the people lens (§4.14)


def group_counts(stages: list[str]) -> dict[str, int]:
    """Counts per plain stage group, in a fixed order, zeros included."""
    c = Counter(stages)
    return {label: sum(c[s] for s in members) for label, members in STAGE_GROUPS}


def _upsert(conn: Conn, kind: str, key: str, data: dict[str, Any], now: dt.datetime) -> None:
    conn.execute(
        "INSERT INTO lens_snapshots (kind, key, data, built_at) VALUES (%s, %s, %s, %s) "
        "ON CONFLICT (kind, key) DO UPDATE SET data = EXCLUDED.data, built_at = EXCLUDED.built_at",
        (kind, key, Jsonb(data), now),
    )


def build(conn: Conn, now: dt.datetime | None = None) -> dict[str, int]:
    """Rebuild every LOB and role lens from the database (counts only)."""
    now = now or dt.datetime.now(dt.UTC)
    tax = _taxonomy(get_settings().company_repo_path)
    ideas = conn.execute(
        "SELECT idea_id, stage, lobs, roles_affected, area_ids, submitted_at FROM ideas "
        "WHERE stage = ANY(%s) AND idea_id IS NOT NULL",
        (list(COUNTED),),
    ).fetchall()
    clusters = conn.execute(
        "SELECT id, lobs, member_count, distinct_contributors FROM clusters WHERE state <> 'retired'"
    ).fetchall()
    deliveries = conn.execute(
        "SELECT d.state, d.outcome, array_agg(DISTINCT l) FILTER (WHERE l IS NOT NULL) AS lobs FROM deliveries d "
        "LEFT JOIN ideas i ON (d.subject_type = 'idea' AND i.idea_id = d.subject_id) "
        "OR (d.subject_type = 'cluster' AND i.cluster_id = d.subject_id) "
        "LEFT JOIN LATERAL unnest(i.lobs) AS l ON true GROUP BY d.id, d.state, d.outcome"
    ).fetchall()
    ageing_cutoff = now
    areas = {a["id"]: a["name"] for a in tax["areas"]}
    with conn.transaction():
        for lob in tax["lobs"]:
            mine = [i for i in ideas if lob["id"] in (i["lobs"] or [])]
            waiting = [i for i in mine if i["stage"] == "scanned" and i["submitted_at"]]
            touching = [c for c in clusters if lob["id"] in (c["lobs"] or [])]
            ds = [d for d in deliveries if lob["id"] in (d["lobs"] or [])]
            data = {
                "name": lob["name"], "ideas": len(mine), "stages": group_counts([i["stage"] for i in mine]),
                "ageing": sum(1 for i in waiting if add_working_days(i["submitted_at"], AGEING_WD) < ageing_cutoff),
                "top_groups": [
                    {"id": c["id"], "ideas": int(c["member_count"]), "colleagues": int(c["distinct_contributors"])}
                    for c in sorted(touching, key=lambda c: -int(c["distinct_contributors"]))[:5]
                ],
                "cross_lob_groups": sum(1 for c in touching if len(c["lobs"] or []) > 1),
                "being_built": sum(1 for d in ds if d["state"] in ("drafting", "awaiting_sponsor", "in_delivery")),
                "measuring": sum(1 for d in ds if d["state"] in ("shipped", "resolved")),
                "closed": sum(1 for d in ds if d["state"] == "closed"),
                "adoptable": sum(1 for d in ds if d["state"] == "closed" and d["outcome"] == "target_met"),
            }  # fmt: skip
            _upsert(conn, "lob", lob["id"], data, now)
        for role in tax["roles"]:
            mine = [i for i in ideas if role["id"] in (i["roles_affected"] or [])]
            top_areas = Counter(a for i in mine for a in (i["area_ids"] or []))
            data = {
                "name": role["name"], "ideas": len(mine), "stages": group_counts([i["stage"] for i in mine]),
                "top_areas": [{"id": a, "name": areas.get(a, a), "ideas": n} for a, n in top_areas.most_common(5)],
            }  # fmt: skip
            _upsert(conn, "role", role["id"], data, now)
    counts = {"lobs": len(tax["lobs"]), "roles": len(tax["roles"])}
    log.info("lenses.built", **counts)
    return counts


def people(conn: Conn) -> list[dict[str, Any]]:
    """The people lens, counts only (§4.14): for each active group, how many colleagues contribute and how many
    more are active in related groups (centroid similarity at least 0.75), who could be asked to join its working
    group. Naming them is an identity reveal, so it stays with Admin's reveal (with a reason, logged)."""
    rows = conn.execute(
        "WITH active AS (SELECT id, centroid, distinct_contributors FROM clusters "
        "WHERE stage = ANY(%s) AND state <> 'retired' AND centroid IS NOT NULL), "
        "pairs AS (SELECT a.id AS cid, b.id AS rid, 1 - (a.centroid <=> b.centroid) AS sim FROM active a "
        "JOIN active b ON a.id <> b.id WHERE 1 - (a.centroid <=> b.centroid) >= %s), "
        "own AS (SELECT DISTINCT i.cluster_id AS cid, i.contributor_code AS code FROM ideas i WHERE i.cluster_id IS NOT NULL "
        "UNION SELECT DISTINCT l.cluster_id, l.contributor_code FROM idea_links l WHERE l.cluster_id IS NOT NULL "
        "AND l.link_type IN ('originator', 'joiner')) "
        "SELECT a.id, a.distinct_contributors, "
        "(SELECT count(*) FROM pairs p WHERE p.cid = a.id) AS related, "
        "(SELECT count(DISTINCT o.code) FROM pairs p JOIN own o ON o.cid = p.rid WHERE p.cid = a.id "
        "AND o.code NOT IN (SELECT code FROM own WHERE cid = a.id)) AS could_join "
        "FROM active a ORDER BY a.id",
        (["in_cluster", "ready_for_scoring", "scored", "shortlisted", "presenting", "picked", "handover",
          "in_garage", "in_fix_track"], RELATED),
    ).fetchall()  # fmt: skip
    return [
        {"id": r["id"], "colleagues": int(r["distinct_contributors"]), "related_groups": int(r["related"]),
         "could_join": int(r["could_join"])}
        for r in rows
    ]  # fmt: skip


VIEWERS = {"lob_committee", "core_committee", "core_chair", "admin"}


def overview(conn: Conn) -> dict[str, Any]:
    snaps = conn.execute("SELECT kind, key, data, built_at FROM lens_snapshots ORDER BY kind, key").fetchall()
    built = max((s["built_at"] for s in snaps), default=None)
    return {
        "built_at": built.isoformat() if built else None,
        "stage_groups": [label for label, _ in STAGE_GROUPS],
        "lobs": [{"id": s["key"], **s["data"]} for s in snaps if s["kind"] == "lob"],
        "roles": [{"id": s["key"], **s["data"]} for s in snaps if s["kind"] == "role"],
        "people": people(conn),
    }


def view(conn: Conn, viewer_id: str) -> dict[str, Any]:
    """Committees and admins only (the web checks `view_lenses`; this checks the grants again)."""
    from ones.service import roles
    from ones.text import OnesRefused

    have = roles(conn, viewer_id)
    if not have & VIEWERS:
        raise OnesRefused(403, "forbidden")
    return {**overview(conn), "can_rebuild": "admin" in have}


def rebuild(conn: Conn, actor: str) -> dict[str, Any]:
    """An admin rebuilds the lenses now instead of waiting for Monday. Audited."""
    from ones.service import roles
    from ones.text import OnesRefused

    if "admin" not in roles(conn, actor):
        raise OnesRefused(403, "forbidden")
    counts = build(conn)
    conn.execute(
        "INSERT INTO audit_log (actor, action, entity) VALUES (%s, 'lenses.rebuilt', 'lens_snapshots')",
        (f"user:{actor}",),
    )
    return counts
