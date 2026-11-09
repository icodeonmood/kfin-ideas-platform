"""Read views for the committee flow: the desk's qualify screen and a working group's page."""

from __future__ import annotations

from typing import Any

from committee.qualify import FIELDS, GATES, computed
from committee.rounds import _cluster_card
from core.db import Conn
from pii import vault
from pii.restore import Mode, restore

GATE_WORDS = {
    "evidence": "Evidence exists",
    "not_solved": "Not already running somewhere",
    "not_planned": "Not already planned",
    "no_conflict": "No regulatory or IP conflict",
}


def qualify_view(conn: Conn, item_id: int, mode: Mode) -> dict[str, Any] | None:
    item = conn.execute(
        "SELECT * FROM review_items WHERE id = %s AND item_type = 'qualify'", (item_id,)
    ).fetchone()
    if item is None:
        return None
    cid = str(item["ref_id"])
    c = conn.execute(
        "SELECT stage, route_to, route_lob, tag_scope, scope FROM clusters WHERE id = %s", (cid,)
    ).fetchone()
    mapping = vault.mapping(conn, c["tag_scope"]) if c and c["tag_scope"] else {}
    gates = {
        r["gate"]: dict(r) for r in conn.execute("SELECT * FROM cluster_gates WHERE cluster_id = %s", (cid,))
    }
    impact = conn.execute("SELECT * FROM impact_estimates WHERE cluster_id = %s", (cid,)).fetchone()
    fields = dict((impact or {}).get("fields") or {})
    annual, payback = computed(fields)
    timer = conn.execute(
        "SELECT due_at FROM sla_timers WHERE entity_type = 'review_item' AND entity_id = %s AND stage = 'qualify' "
        "ORDER BY id DESC LIMIT 1",
        (str(item_id),),
    ).fetchone()
    return {
        "id": item_id, "cluster_id": cid, "state": item["state"], "assigned_to": str(item["assigned_to"]) if item["assigned_to"] else None,
        "stage": c["stage"] if c else None, "final": item["final"],
        "due_at": timer["due_at"].isoformat() if timer else None,
        "cluster": _cluster_card(conn, cid, "real" if mode == "real" else "neutral"),
        "gates": [
            {"gate": g, "label": GATE_WORDS[g], "proposed": gates.get(g, {}).get("proposed"),
             "evidence": gates.get(g, {}).get("evidence") or {}, "result": gates.get(g, {}).get("result"),
             "detail": gates.get(g, {}).get("detail"), "note": restore(gates.get(g, {}).get("note"), mapping, mode),
             "confirmed_by": gates.get(g, {}).get("confirmed_by")}
            for g in GATES
        ],
        "impact": {
            "fields": fields, "units": FIELDS, "basis": (impact or {}).get("basis") or {},
            "annual_net_benefit": annual, "payback_months": payback,
            "finance_required": bool((impact or {}).get("finance_required")),
            "finance_validated_by": (impact or {}).get("finance_validated_by"),
            "saved_by": (impact or {}).get("updated_by"),
        },
        "coming_soon": ["impact_draft", "core_brief", "compliance_reviewer_screen", "finance_screen", "evidence_replies", "lob_comments"],
    }  # fmt: skip


def working_group(conn: Conn, wg: str, user_id: str) -> dict[str, Any] | None:
    """A working group's page: its members (names shown to the group, the sponsor, the core committee and admins,
    who work together on it, BLD-220), the sponsor and the cluster. Charter, protected time with manager
    acknowledgement and the kick-off invite are "Coming soon"."""
    row = conn.execute("SELECT * FROM working_groups WHERE id = %s", (wg,)).fetchone()
    if row is None:
        return None
    codes = {m["contributor_code"] for m in row["members"] or []}
    mine = {
        r["contributor_code"]
        for r in conn.execute(
            "SELECT contributor_code FROM contributor_map WHERE user_id = %s", (user_id,)
        ).fetchall()
    }
    privileged = conn.execute(
        "SELECT 1 FROM role_grants WHERE user_id = %s AND valid_to IS NULL AND role IN ('core_committee', 'core_chair', 'admin') "
        "LIMIT 1",
        (user_id,),
    ).fetchone()
    if not (mine & codes) and str(row["sponsor_id"] or "") != user_id and not privileged:
        return None
    names = {
        r["contributor_code"]: r["name"]
        for r in conn.execute(
            "SELECT m.contributor_code, u.name FROM contributor_map m JOIN users u ON u.id = m.user_id "
            "WHERE m.contributor_code = ANY(%s)",
            (sorted(codes),),
        ).fetchall()
    }
    sponsor = (
        conn.execute("SELECT name FROM users WHERE id = %s", (row["sponsor_id"],)).fetchone()
        if row["sponsor_id"]
        else None
    )
    title = conn.execute(
        "SELECT title, tag_scope FROM clusters WHERE id = %s", (row["cluster_id"],)
    ).fetchone()
    mapping = vault.mapping(conn, title["tag_scope"]) if title and title["tag_scope"] else {}
    return {
        "id": wg, "cluster_id": row["cluster_id"], "decision_id": row["decision_id"], "state": row["state"],
        "name": restore((title or {}).get("title"), mapping, "real"),
        "sponsor": (sponsor or {}).get("name"),
        "members": [{"name": names.get(m["contributor_code"], "A colleague who has left"), "role": m["role"]}
                    for m in row["members"] or []],
        "formed_at": row["formed_at"].isoformat(),
    }  # fmt: skip
