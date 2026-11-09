"""What the delivery console shows (§4.8 to §4.11). Committee members and admins see every delivery and the picked
ideas still waiting for a handover; owners, sponsors, PMs and milestone owners see the deliveries they are part of.
Idea text is never shown here beyond each idea's checked neutral summary; checked free text (metric, objective,
milestones, notes) is shown only to people who can see the delivery."""

from __future__ import annotations

import datetime as dt
from typing import Any

from core.db import Conn
from delivery import extras, service, writeups
from delivery.phases import (
    COMPLIANCE_TIERS,
    FEATURE_TYPES,
    METRIC_UNITS,
    PHASES,
    PRODUCTS,
    TRACKS,
    shown_as,
)
from ones.service import MEASURE_UNITS, roles
from ones.text import unseal
from views.common import checked_summary

STATE_WORDS = {
    "drafting": "Handover pack in progress",
    "awaiting_sponsor": "Waiting for the sponsor",
    "in_delivery": "Being built",
    "shipped": "Shipped, being measured",
    "resolved": "Fixed, being measured",
    "closed": "Closed",
}
TRACK_WORDS = {"build": "Build", "fix": "Non-tech fix", "procurement": "Buy or partner"}


def _iso(value: Any) -> str | None:
    return value.isoformat() if value else None


def _names(conn: Conn, ids: set[str]) -> dict[str, dict[str, str]]:
    ids = {i for i in ids if i and i != "None"}
    if not ids:
        return {}
    rows = conn.execute(
        "SELECT id, name, email FROM users WHERE id = ANY(%s::uuid[])", (list(ids),)
    ).fetchall()
    return {str(r["id"]): {"name": str(r["name"]), "email": str(r["email"])} for r in rows}


def _label(conn: Conn, subject_type: str, subject_id: str) -> str:
    """The idea's checked neutral summary, or a cluster's size; never anything else from the idea."""
    if subject_type == "idea":
        row = conn.execute("SELECT canvas FROM ideas WHERE idea_id = %s", (subject_id,)).fetchone()
        summary = checked_summary(conn, ((row["canvas"] if row else None) or {}).get("neutral_summary"))
        return summary or subject_id
    row = conn.execute("SELECT member_count FROM clusters WHERE id = %s", (subject_id,)).fetchone()
    return f"Group {subject_id}, {int(row['member_count']) if row else 0} ideas"


def _next_measurement(conn: Conn, delivery_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT m.mark, m.due_at, m.filled_at, m.confirmed_at FROM delivery_measurements m "
        "JOIN deliveries d ON d.id = m.delivery_id WHERE m.delivery_id = %s AND m.confirmed_at IS NULL "
        "AND d.state IN ('shipped', 'resolved') ORDER BY m.due_at LIMIT 1",
        (delivery_id,),
    ).fetchone()
    if row is None:
        return None
    return {"mark": row["mark"], "due_at": _iso(row["due_at"]), "filled": row["filled_at"] is not None}


def console(conn: Conn, viewer_id: str) -> dict[str, Any]:
    have = roles(conn, viewer_id)
    wide = bool(have & ({"admin"} | service.COMMITTEE))
    if wide:
        rows = conn.execute("SELECT * FROM deliveries ORDER BY updated_at DESC LIMIT 300").fetchall()
    else:
        rows = conn.execute(
            "SELECT DISTINCT d.* FROM deliveries d LEFT JOIN delivery_milestones m ON m.delivery_id = d.id "
            "WHERE d.owner_user_id = %s OR d.sponsor_user_id = %s OR d.pm_user_id = %s OR m.owner_user_id = %s "
            "ORDER BY d.updated_at DESC LIMIT 300",
            (viewer_id, viewer_id, viewer_id, viewer_id),
        ).fetchall()
    people = _names(conn, {str(r[k]) for r in rows for k in ("owner_user_id", "sponsor_user_id")})
    deliveries = []
    for r in rows:
        d = dict(r)
        deliveries.append(
            {
                "id": d["id"], "subject_id": d["subject_id"], "subject_type": d["subject_type"],
                "label": _label(conn, d["subject_type"], d["subject_id"]),
                "track": d["track"], "track_words": TRACK_WORDS[d["track"]],
                "state": d["state"], "state_words": STATE_WORDS[d["state"]],
                "phase_words": shown_as(d["phase"]), "blocked": d["gate_status"] == "blocked",
                "owner": people.get(str(d["owner_user_id"]), {}).get("name"),
                "sponsor": people.get(str(d["sponsor_user_id"]), {}).get("name"),
                "next_measurement": _next_measurement(conn, d["id"]),
                "outcome": d["outcome"], "updated_at": _iso(d["updated_at"]),
            }
        )  # fmt: skip
    waiting: list[dict[str, Any]] = []
    if wide:
        for r in conn.execute(
            "SELECT 'idea' AS t, idea_id AS id FROM ideas i WHERE stage = 'picked' AND cluster_id IS NULL "
            "AND NOT EXISTS (SELECT 1 FROM deliveries d WHERE d.subject_type = 'idea' AND d.subject_id = i.idea_id) "
            "UNION ALL SELECT 'cluster', id FROM clusters c WHERE stage = 'picked' "
            "AND NOT EXISTS (SELECT 1 FROM deliveries d WHERE d.subject_type = 'cluster' AND d.subject_id = c.id) "
            "LIMIT 100"
        ).fetchall():
            waiting.append(
                {"subject_type": r["t"], "subject_id": r["id"], "label": _label(conn, r["t"], r["id"])}
            )
    return {
        "deliveries": deliveries,
        "waiting": waiting,
        "can_start": bool(have & ({"admin"} | service.COMMITTEE)),
    }


def detail(
    conn: Conn, viewer_id: str, delivery_id: Any, now: dt.datetime | None = None
) -> dict[str, Any] | None:
    now = now or dt.datetime.now(dt.UTC)
    try:
        d = dict(service._delivery(conn, delivery_id))
    except service.Refused:
        return None
    have = roles(conn, viewer_id)
    if not service.can_see(conn, d, viewer_id, have):
        return None
    admin = "admin" in have
    owner = viewer_id == str(d["owner_user_id"])
    sponsor = viewer_id == str(d["sponsor_user_id"]) and bool(have & service.SPONSOR_ROLES)
    pm = viewer_id == str(d["pm_user_id"])
    people = _names(conn, {str(d[k]) for k in ("owner_user_id", "sponsor_user_id", "pm_user_id")})
    milestones = []
    for m in conn.execute(
        "SELECT * FROM delivery_milestones WHERE delivery_id = %s ORDER BY due_on, id", (d["id"],)
    ).fetchall():
        who = _names(conn, {str(m["owner_user_id"])}).get(str(m["owner_user_id"]), {})
        milestones.append(
            {
                "id": m["id"], "title": unseal(m["title_encrypted"], f"milestone:{m['id']}"),
                "owner": who.get("name"), "due_on": m["due_on"].isoformat(), "status": m["status"],
                "overdue": m["status"] == "open" and m["due_on"] < now.date(),
                "can_set": admin or owner or viewer_id == str(m["owner_user_id"]),
            }
        )  # fmt: skip
    measurements = []
    for m in conn.execute(
        "SELECT * FROM delivery_measurements WHERE delivery_id = %s ORDER BY due_at", (d["id"],)
    ).fetchall():
        results = dict(m["results"] or {})
        money_ok = m["finance_confirmed_at"] is not None
        measurements.append(
            {
                "mark": m["mark"], "due_at": _iso(m["due_at"]), "results": results,
                "notes": unseal(m["notes_encrypted"], f"measurement:{m['id']}"),
                "filled_at": _iso(m["filled_at"]), "confirmed_at": _iso(m["confirmed_at"]),
                "finance_confirmed": money_ok,
                "can_fill": (admin or owner) and m["confirmed_at"] is None and d["state"] in ("shipped", "resolved"),
                "can_confirm": sponsor and m["filled_at"] is not None and m["confirmed_at"] is None
                and str(m["filled_by"]) != viewer_id,
                "can_finance_confirm": admin and "money" in results and not money_ok,
            }
        )  # fmt: skip
    pack = dict(d["pack"] or {})
    completion = dict(d["completion"] or {}) if d["completion"] else None
    editable = d["state"] in ("drafting", "awaiting_sponsor") and service._can_edit(have, d, viewer_id)
    in_fix = d["track"] == "fix" and d["state"] == "in_delivery"
    return {
        "id": d["id"], "subject_id": d["subject_id"], "subject_type": d["subject_type"],
        "label": _label(conn, d["subject_type"], d["subject_id"]),
        "track": d["track"], "track_words": TRACK_WORDS[d["track"]],
        "state": d["state"], "state_words": STATE_WORDS[d["state"]],
        "owner": people.get(str(d["owner_user_id"])), "sponsor": people.get(str(d["sponsor_user_id"])),
        "pm": people.get(str(d["pm_user_id"])),
        "pack": pack, "metric": unseal(d["metric_encrypted"], f"delivery:{d['id']}:metric"),
        "objective": unseal(d["objective_encrypted"], f"delivery:{d['id']}:objective"),
        "missing": service.missing(d) if d["state"] in ("drafting", "awaiting_sponsor") else [],
        "sponsor_approved_at": _iso(d["sponsor_approved_at"]),
        "phase": d["phase"], "phase_words": shown_as(d["phase"]), "gate_status": d["gate_status"],
        "blocked_since": _iso(d["blocked_since"]), "link_state": d["link_state"],
        "pipeline_page_id": d["pipeline_page_id"] if admin else None,
        "completion": completion,
        "completion_notes": unseal(d["completion_notes"], f"delivery:{d['id']}:completion"),
        "completed_at": _iso(d["completed_at"]),
        "milestones": milestones, "measurements": measurements, "outcome": d["outcome"],
        "evidence": extras.evidence(conn, d, viewer_id, have),
        "checkins": extras.checkins(conn, d, viewer_id, have, now) if d["track"] == "fix" else None,
        "writeup": writeups.view(conn, d, viewer_id, have),
        "shipped_at": _iso(d["shipped_at"]), "resolved_at": _iso(d["resolved_at"]),
        "closed_at": _iso(d["closed_at"]),
        "options": {
            "tracks": list(TRACKS), "products": list(PRODUCTS), "feature_types": list(FEATURE_TYPES),
            "compliance_tiers": list(COMPLIANCE_TIERS), "metric_units": list(METRIC_UNITS),
            "phases": [{"id": p, "words": w} for p, w in PHASES],
            "measure_units": {k: list(v) for k, v in MEASURE_UNITS.items()},
        },
        "can": {
            "edit": editable,
            "submit": d["state"] == "drafting" and (admin or owner),
            "approve": d["state"] == "awaiting_sponsor" and sponsor,
            "set_phase": d["state"] == "in_delivery" and d["track"] != "fix" and (admin or pm),
            "link": admin and d["track"] != "fix" and d["state"] in ("in_delivery", "shipped"),
            "add_milestone": in_fix and (admin or owner),
            "complete": in_fix and (admin or owner),
            "approve_completion": in_fix and sponsor and d["completed_at"] is not None,
            "add_evidence": d["state"] in ("in_delivery", "shipped", "resolved") and (admin or owner),
        },
    }  # fmt: skip
