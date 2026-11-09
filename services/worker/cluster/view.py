"""What the review desk sees of one cluster proposal. Text is restored on view (§3.2 step 8): each member's
one-line from that idea's own scope, and the summary and judge reasons from the proposal's scope. The caller (web,
`src/server/clusters.ts`) chooses the mode from §3.1."""

from __future__ import annotations

from typing import Any

from core.db import Conn
from pii import vault
from pii.restore import Mode, restore

KIND_WORDS = {
    "new": "New group",
    "grow": "Add to a group",
    "merge": "Merge groups",
    "split": "Split a group",
}


def _restored(conn: Conn, scope: str | None, payload: Any, mode: Mode) -> Any:
    if not scope or payload is None:
        return payload
    return restore(payload, vault.mapping(conn, scope), mode)


def proposal_view(conn: Conn, item_id: int, mode: Mode) -> dict[str, Any] | None:
    item = conn.execute(
        "SELECT * FROM review_items WHERE id = %s AND item_type = 'cluster_proposal'", (item_id,)
    ).fetchone()
    prop = conn.execute("SELECT * FROM cluster_proposals WHERE review_item_id = %s", (item_id,)).fetchone()
    if item is None or prop is None:
        return None
    members_ids = list(prop["members"])
    dropped = list(prop["dropped"] or [])
    targets = list(prop["targets"] or [])
    every = sorted(set(members_ids) | {d["idea_id"] for d in dropped})
    rows = {
        r["idea_id"]: r
        for r in conn.execute(
            "SELECT idea_id, stage, lobs, area_ids, contributor_code, cluster_id, canvas->>'one_line' AS one_line "
            "FROM ideas WHERE idea_id = ANY(%s)",
            (every,),
        ).fetchall()
    }

    def idea(i: str) -> dict[str, Any]:
        r = rows.get(i)
        if r is None:
            return {"idea_id": i, "missing": True}
        return {
            "idea_id": i,
            "one_line": _restored(conn, i, r["one_line"], mode),
            "stage": r["stage"],
            "lobs": list(r["lobs"] or []),
            "areas": list(r["area_ids"] or []),
            "contributor": r["contributor_code"],
            "cluster_id": r["cluster_id"],
        }

    target_rows = conn.execute(
        "SELECT id, title, tag_scope, member_count, state FROM clusters WHERE id = ANY(%s) ORDER BY id",
        (targets,),
    ).fetchall()
    summary = dict(prop["summary"] or {})
    refs: dict[str, str] = summary.pop("refs", {}) or {}
    timer = conn.execute(
        "SELECT due_at, state FROM sla_timers WHERE entity_type = 'review_item' AND entity_id = %s "
        "AND stage = 'cluster_proposal' ORDER BY id DESC LIMIT 1",
        (str(item_id),),
    ).fetchone()
    return {
        "id": item_id,
        "proposal_id": prop["id"],
        "run_id": prop["run_id"],
        "kind": prop["kind"],
        "kind_words": KIND_WORDS[prop["kind"]],
        "state": prop["state"],
        "item_state": item["state"],
        "targets": [
            {
                "id": t["id"],
                "title": _restored(conn, t["tag_scope"], t["title"], mode),
                "member_count": t["member_count"],
                "state": t["state"],
            }
            for t in target_rows
        ],
        "members": [idea(i) for i in members_ids],
        "dropped": [
            {
                **idea(d["idea_id"]),
                "reason": _restored(conn, prop["tag_scope"], d.get("reason"), mode),
                "removed_by": d.get("removed_by"),
                "code": d.get("code"),
            }
            for d in dropped
        ],
        "split_groups": prop["split_groups"],
        "summary": _restored(conn, prop["tag_scope"], summary, mode) if summary else None,
        "refs": refs,
        "generated_by": prop["generated_by"],
        "metrics": prop["metrics"],
        "checks_skipped": (item["reasons"] or {}).get("checks_skipped") or [],
        "due_at": timer["due_at"].isoformat() if timer else None,
        "decided_by": prop["decided_by"],
        "decided_at": prop["decided_at"].isoformat() if prop["decided_at"] else None,
        "cluster_id": prop["cluster_id"],
        "final": _restored(conn, prop["tag_scope"], item["final"], mode),
    }


def runs(conn: Conn, limit: int = 5) -> list[dict[str, Any]]:
    """The latest runs, for the desk's queue page (numbers only)."""
    return [
        {
            "id": r["id"],
            "state": r["state"],
            "pool_size": r["pool_size"],
            "counts": r["counts"],
            "started_at": r["started_at"].isoformat(),
            "finished_at": r["finished_at"].isoformat() if r["finished_at"] else None,
        }
        for r in conn.execute(
            "SELECT * FROM cluster_runs ORDER BY started_at DESC LIMIT %s", (limit,)
        ).fetchall()
    ]
