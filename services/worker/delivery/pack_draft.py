"""The handover pack drafted by the assistant (BLD-138, BLD-141). The `handover-draft` agent reads the picked idea,
or each idea in the picked group, through the gateway and proposes the metric, its unit, the product, the feature
type and, on the fix track, the objective. Numbers only when a member's summary gave them.

What it reads (BLD-141): only org-visible member ideas, and only their checked neutral summaries, the same text
everyone may already see. Never an idea's one-line, details or proposed fix, and never a committee-only idea, so
nothing a member could not see shapes the draft (non-negotiable 7).

It proposes; people decide. Nothing is saved here: the draft goes back to the person filling in the pack, who
edits it and saves it through the normal pack checks, and the sponsor approves the pack as before. Only the
delivery's editors can ask for a draft, while the pack is open. Audited with a member count only."""

from __future__ import annotations

from typing import Any

from core.db import Conn
from delivery import service
from delivery.phases import FEATURE_TYPES, METRIC_UNITS, PRODUCTS
from gateway import AgentFailed, run_agent
from ones.service import roles
from views.common import checked_summary, taxonomy_names

MAX_MEMBERS = 12


def _members(conn: Conn, d: dict[str, Any]) -> list[dict[str, Any]]:
    """Org-visible member ideas as checked neutral summaries with their lines of business."""
    rows = conn.execute(
        "SELECT nullif(btrim(canvas ->> 'neutral_summary'), '') AS summary, lobs FROM ideas "
        "WHERE (CASE WHEN %s = 'idea' THEN idea_id ELSE cluster_id END) = %s AND visibility = 'org' "
        "AND stage NOT IN ('withdrawn', 'declined', 'parked', 'draft') ORDER BY submitted_at NULLS LAST, idea_id "
        "LIMIT %s",
        (d["subject_type"], d["subject_id"], MAX_MEMBERS),
    ).fetchall()
    _areas, lobs = taxonomy_names()
    out: list[dict[str, Any]] = []
    for r in rows:
        summary = checked_summary(conn, r["summary"])
        if summary:
            out.append({"ref": f"M{len(out) + 1}", "summary": summary,
                        "lobs": [lobs.get(x, x) for x in r["lobs"] or []][:3]})  # fmt: skip
    return out


def draft(conn: Conn, actor: str, delivery_id: Any) -> dict[str, Any]:
    d = service._delivery(conn, delivery_id)
    if not service._can_edit(roles(conn, actor), d, actor):
        raise service.Refused(403, "owner_only")
    if d["state"] not in ("drafting", "awaiting_sponsor"):
        raise service.Refused(409, "pack_not_open")
    members = _members(conn, d)
    if not members:
        raise service.Refused(409, "nothing_to_draft_from")
    inputs = {
        "members": members,
        "track": d["track"],
        "options": {
            "units": list(METRIC_UNITS),
            "products": list(PRODUCTS),
            "feature_types": list(FEATURE_TYPES),
        },
    }
    try:
        out = run_agent("handover-draft", inputs, str(d["subject_id"]), conn=conn)
    except AgentFailed as exc:
        raise service.Refused(503, "assistant_unavailable") from exc
    service._audit(conn, actor, "delivery.pack_drafted", f"delivery:{d['id']}", {"members": len(members)})
    data = out.data
    return {
        "metric": data["metric"],
        "unit": data["unit"],
        "baseline": data["baseline"],
        "target": data["target"],
        "product": data["product"],
        "feature_type": data["feature_type"],
        "objective": data["objective"] if d["track"] == "fix" else None,
        "notes": data["notes"],
    }
