"""The handover pack drafted by the assistant (BLD-138). The `handover-draft` agent reads the picked idea, or each
idea in the picked group, through the gateway (tagged before sending, checked after) and proposes the metric, its
unit, the product, the feature type and, on the fix track, the objective. Numbers only when a member gave them.

It proposes; people decide. Nothing is saved here: the draft goes back to the person filling in the pack, who
edits it and saves it through the normal pack checks, and the sponsor approves the pack as before. Only the
delivery's editors can ask for a draft, only while the pack is being drafted. Audited with IDs only."""

from __future__ import annotations

from typing import Any

from cluster import cards
from core.db import Conn
from delivery import service
from delivery.phases import FEATURE_TYPES, METRIC_UNITS, PRODUCTS
from gateway import AgentFailed, run_agent
from ones.service import roles

MAX_MEMBERS = 12


def _members(conn: Conn, d: dict[str, Any]) -> list[dict[str, Any]]:
    if d["subject_type"] == "idea":
        ids = [str(d["subject_id"])]
    else:
        ids = [
            str(r["idea_id"])
            for r in conn.execute(
                "SELECT idea_id FROM ideas WHERE cluster_id = %s AND stage NOT IN ('withdrawn', 'declined', "
                "'parked', 'draft') ORDER BY submitted_at NULLS LAST, idea_id LIMIT %s",
                (d["subject_id"], MAX_MEMBERS),
            ).fetchall()
        ]
    found = cards.ideas(conn, ids)
    out = []
    for n, idea_id in enumerate(i for i in ids if i in found):
        card = cards.member_card(conn, f"M{n + 1}", found[idea_id])
        out.append({k: card[k] for k in ("ref", "kind", "one_line", "details", "who", "lobs", "fix")})
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
