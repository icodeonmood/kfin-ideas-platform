"""Qualify (§4.5): an approved cluster passes four gates and gets an impact estimate before it is scored.

Day-one-of-qualify scope (DEC-057, BLD-213): the rules and the judge propose each gate (the `gate-check` agent is
"Coming soon"); a reviewer confirms every gate; the impact form starts from the contributors' own estimates (the
`impact-draft` agent is "Coming soon"); the platform computes the annual net benefit and payback, flags the
finance check at ₹25 lakh, and routes the cluster: `lob` scope to that LOB's committee, everything else and every
business idea to the core committee. The core brief (build-vs-buy, priority) is "Coming soon".

Each action is one transaction. Notes are tagged under the cluster's scope; gate evidence holds IDs and counts.
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

from psycopg.types.json import Jsonb

from comms.route import emit
from core.config import get_settings
from core.db import Conn
from core.logging import get_logger
from desk.store import IDEA_OWN_A
from pii.patterns import scan
from pii.tagger import tag_payload
from review.service import ActionRefused, audited, staff_code
from rules import load_rule
from sla import engine

log = get_logger("committee.qualify")
GATES = ("evidence", "not_solved", "not_planned", "no_conflict")
REGULATED_LOBS = {"LOB-nps", "LOB-sif"}  # rules/compliance-tier.md regulated_products that are LOBs
_REGULATOR = re.compile(r"\b(sebi|pfrda|rbi|irdai|amfi|regulat\w*|circular|compliance)\b", re.I)
FIELDS: dict[str, str] = {  # §4.5 step 2: field → unit (fixed)
    "capex_inr": "₹",
    "opex_inr_per_year": "₹ a year",
    "one_time_revenue_inr": "₹",
    "one_time_saving_inr": "₹",
    "recurring_revenue_inr_per_year": "₹ a year",
    "recurring_saving_inr_per_year": "₹ a year",
    "hours_saved_per_month": "hours a month",
    "clients_who_would_pay": "count",
    "weeks_to_first_benefit": "weeks",
    "effort_person_weeks": "person-weeks",
    "dependencies": "count",
}
EVIDENCE_TYPES = ("data_backed", "estimate", "anecdote")
OUTCOMES = {  # a failed gate's outcome, most serious first
    "no_conflict": ("declined", "REG_CONFLICT"),
    "not_solved": ("already_solved", "ALREADY_SOLVED"),
    "not_planned": ("already_planned", "ALREADY_PLANNED"),
    "evidence": ("parked", "INSUFFICIENT_EVIDENCE"),
}


def _members(conn: Conn, cluster_id: str) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in conn.execute(
            "SELECT id, idea_id, contributor_code, kind, basis, area_ids, lobs, scope, canvas FROM ideas "
            "WHERE cluster_id = %s ORDER BY idea_id",
            (cluster_id,),
        ).fetchall()
    ]


def _contributors(conn: Conn, cluster_id: str) -> set[str]:
    rows = conn.execute(
        "SELECT contributor_code FROM ideas WHERE cluster_id = %s UNION SELECT contributor_code FROM idea_links "
        "WHERE cluster_id = %s AND link_type IN ('originator', 'joiner')",
        (cluster_id, cluster_id),
    ).fetchall()
    return {r["contributor_code"] for r in rows}


# ---- the pre-check (the rules and the judge propose) ----------------------------------------------------------


def _evidence(conn: Conn, cluster_id: str, members: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    people = len(_contributors(conn, cluster_id))
    own_data = [m["idea_id"] for m in members if m["basis"] in ("own_data", "document")]
    files = conn.execute(  # the members' own files: never one added for the conversation (DEC-124; BLD-B274)
        "SELECT count(*) AS n FROM attachments a JOIN ideas i ON i.id = a.idea_uuid "  # noqa: S608 (fixed text)
        f"WHERE i.cluster_id = %s AND a.state = 'clean' AND {IDEA_OWN_A}",
        (cluster_id,),
    ).fetchone()
    refs = sum(
        1
        for m in members
        for r in ((m["canvas"] or {}).get("ecosystem") or {}).get("references") or []
        if r.get("kind") in ("link", "attachment")
    )
    figures = [
        m["idea_id"]
        for m in members
        if any(
            isinstance(v, int | float) and v
            for k, v in (((m["canvas"] or {}).get("value") or {}).get("estimate") or {}).items()
            if k != "note"
        )
    ]
    clean_files = int(files["n"]) if files else 0
    found: dict[str, Any] = {"contributors": people, "own_data": own_data, "clean_files": clean_files,
                             "references": refs, "with_figures": figures}  # fmt: skip
    ok = people >= 2 or bool(own_data) or clean_files > 0 or refs > 0 or bool(figures)
    return ("pass" if ok else "fail"), found


def _not_solved(conn: Conn, cluster_id: str) -> tuple[str, dict[str, Any]]:
    """Plan P3 at cluster level against solutions; the judge labels what it finds (§4.5 step 1)."""
    from embeddings import embed
    from gateway import AgentFailed, run_agent
    from pii import vault
    from pii.restore import restore
    from router.match import match

    row = conn.execute(
        "SELECT title, summary, tag_scope FROM clusters WHERE id = %s", (cluster_id,)
    ).fetchone()
    if row is None:
        return "check", {"reason": "no_summary"}
    text = "\n".join(str(x or "") for x in (row["title"], (row["summary"] or {}).get("problem")))
    found = [
        c
        for c in match(conn, text, [], card_vector=embed([text])[0])
        if c.file_type == "solution" and c.kfin_id
    ]
    if not found:
        return "pass", {"solutions_found": 0}
    real = restore({"one_line": row["title"], "details": (row["summary"] or {}).get("problem")},
                   vault.mapping(conn, row["tag_scope"]) if row["tag_scope"] else {}, "real")  # fmt: skip
    try:
        out = run_agent(
            "judge",
            {
                "card": {
                    "kind": "problem",
                    **real,
                    "who": {"segments": []},
                    "areas": [],
                    "lobs": [],
                    "systems": [],
                },
                "candidates": [
                    {
                        "cid": c.kfin_id,
                        "type": "solution",
                        "title": c.text.partition("\n")[0][:160],
                        "summary": " ".join(c.text.partition("\n")[2].split())[:480],
                        "stage": c.stage,
                        "areas": c.area_ids,
                        "lobs": c.lobs,
                    }
                    for c in found[:20]
                ],
                "past_corrections": [],
            },
            row["tag_scope"] or cluster_id,
            conn=conn,
        )
    except AgentFailed:
        return "check", {"solutions": [c.kfin_id for c in found[:5]], "assistant": "unavailable"}
    same = [r["cid"] for r in out.data["results"] if r["label"] == "same"]
    related = [r["cid"] for r in out.data["results"] if r["label"] == "related"]
    return ("fail" if same else "pass"), {"same": same, "related": related}


def _not_planned(conn: Conn) -> tuple[str, dict[str, Any]]:
    """Plan P5 needs the Garage roadmap mirrored into the index (week 4, §4.9). Until then nothing is found."""
    n = conn.execute("SELECT count(*) AS n FROM chunks WHERE file_type = 'garage_feature'").fetchone()
    return "pass", {"roadmap_connected": bool(n and n["n"])}


def _no_conflict(conn: Conn, cluster_id: str, members: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    """`rules/compliance-tier.md` triggers the rules can see; anything they flag needs the compliance reviewer."""
    triggers: list[str] = []
    if any("AREA-compliance" in (m["area_ids"] or []) for m in members):
        triggers.append("area_tag:AREA-compliance")
    if any(((m["canvas"] or {}).get("solution") or {}).get("risks") for m in members):
        triggers.append("submitter_named_risk")
    lobs = {lob for m in members for lob in m["lobs"] or []}
    if lobs & REGULATED_LOBS:
        triggers.append("regulated_product")
    row = conn.execute("SELECT title, summary FROM clusters WHERE id = %s", (cluster_id,)).fetchone()
    text = " ".join(
        str(x or "") for x in ((row or {}).get("title"), ((row or {}).get("summary") or {}).get("problem"))
    )
    if _REGULATOR.search(text):
        triggers.append("regulator_surface")
    return ("check" if triggers else "pass"), {"triggers": triggers}


def precheck(conn: Conn, cluster_id: str) -> dict[str, tuple[str, dict[str, Any]]]:
    members = _members(conn, cluster_id)
    return {
        "evidence": _evidence(conn, cluster_id, members),
        "not_solved": _not_solved(conn, cluster_id),
        "not_planned": _not_planned(conn),
        "no_conflict": _no_conflict(conn, cluster_id, members),
    }


# ---- the impact estimate (§4.5 step 2) -------------------------------------------------------------------------


def computed(fields: dict[str, Any]) -> tuple[float | None, float | None]:
    """Annual net benefit = recurring revenue + recurring saving − opex − capex ÷ 5; payback in months =
    capex ÷ ((recurring revenue + recurring saving − opex) ÷ 12) when that is positive."""

    def n(k: str) -> float:
        v = fields.get(k)
        return float(v) if isinstance(v, int | float) else 0.0

    if not any(isinstance(fields.get(k), int | float) for k in FIELDS):
        return None, None
    yearly = n("recurring_revenue_inr_per_year") + n("recurring_saving_inr_per_year") - n("opex_inr_per_year")
    annual = yearly - n("capex_inr") / 5
    payback = (n("capex_inr") / (yearly / 12)) if yearly > 0 and n("capex_inr") > 0 else None
    return round(annual, 2), (round(payback, 1) if payback is not None else None)


def prefill(members: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    """The contributors' own estimates: the largest figure given for each field (several people estimating the
    same saving must not add up), with which idea it came from; the evidence type from their stated basis."""
    pairs = {
        "inr_saved_per_year": "recurring_saving_inr_per_year",
        "inr_revenue_per_year": "recurring_revenue_inr_per_year",
        "inr_revenue_one_time": "one_time_revenue_inr",
        "hours_saved_per_month": "hours_saved_per_month",
        "clients_who_would_pay": "clients_who_would_pay",
    }
    fields: dict[str, Any] = {}
    basis: dict[str, Any] = {}
    for m in members:
        est = (((m["canvas"] or {}).get("value") or {}).get("estimate")) or {}
        for src, dst in pairs.items():
            v = est.get(src)
            if isinstance(v, int | float) and v > (fields.get(dst) or 0):
                fields[dst], basis[dst] = v, m["idea_id"]
    bases = {m["basis"] for m in members}
    fields["evidence_type"] = (
        "data_backed" if bases & {"own_data", "document"} else "estimate" if fields else "anecdote"
    )
    return fields, basis


def _clean_fields(given: Any) -> dict[str, Any]:
    if not isinstance(given, dict):
        raise ActionRefused(400, "bad_request")
    out: dict[str, Any] = {}
    for k in FIELDS:
        v = given.get(k)
        if v in (None, ""):
            continue
        if not isinstance(v, int | float) or isinstance(v, bool) or v < 0 or v > 1e12:
            raise ActionRefused(422, f"bad_{k}")
        out[k] = v
    et = given.get("evidence_type")
    if et not in EVIDENCE_TYPES:
        raise ActionRefused(422, "bad_evidence_type")
    out["evidence_type"] = et
    names = given.get("dependency_names")
    if names:
        if (
            not isinstance(names, list)
            or len(names) > 20
            or not all(isinstance(x, str) and len(x) <= 80 for x in names)
        ):
            raise ActionRefused(422, "bad_dependency_names")
        out["dependency_names"] = [x.strip() for x in names if x.strip()]
    return out


# ---- the review item ------------------------------------------------------------------------------------------


def start(conn: Conn, cluster_id: str, now: dt.datetime | None = None) -> int | None:
    """Open the qualify item for an approved cluster (§4.5 trigger): gate pre-checks, the impact prefill and a
    10-working-day timer. Does nothing if one is already open or the cluster is past qualifying."""
    now = now or dt.datetime.now(dt.UTC)
    cluster = conn.execute("SELECT stage, state FROM clusters WHERE id = %s", (cluster_id,)).fetchone()
    if cluster is None or cluster["state"] != "approved" or cluster["stage"] != "in_cluster":
        return None
    if conn.execute(
        "SELECT 1 FROM review_items WHERE item_type = 'qualify' AND ref_id = %s AND state IN ('open', 'in_progress')",
        (cluster_id,),
    ).fetchone():
        return None
    checks = precheck(conn, cluster_id)
    for gate, (proposed, evidence) in checks.items():
        conn.execute(
            "INSERT INTO cluster_gates (cluster_id, gate, proposed, evidence) VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (cluster_id, gate) DO UPDATE SET proposed = EXCLUDED.proposed, evidence = EXCLUDED.evidence, "
            "result = NULL, detail = NULL, note = NULL, confirmed_by = NULL, confirmed_at = NULL",
            (cluster_id, gate, proposed, Jsonb(evidence)),
        )
    fields, basis = prefill(_members(conn, cluster_id))
    annual, payback = computed(fields)
    finance = _finance_required(fields, annual)
    conn.execute(
        "INSERT INTO impact_estimates (cluster_id, fields, basis, annual_net_benefit, payback_months, finance_required) "
        "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (cluster_id) DO NOTHING",
        (cluster_id, Jsonb(fields), Jsonb(basis), annual, payback, finance),
    )
    item = conn.execute(
        "INSERT INTO review_items (item_type, ref_id, proposal) VALUES ('qualify', %s, %s) RETURNING id",
        (cluster_id, Jsonb({g: c[0] for g, c in checks.items()})),
    ).fetchone()
    assert item is not None
    engine.start(conn, "review_item", str(item["id"]), "qualify", now=now)
    log.info("qualify.started", cluster_id=cluster_id, review_item_id=item["id"])
    return int(item["id"])


def start_job(conn: Conn, cluster_id: str) -> int | None:
    """The `qualify.start` job, in its own transaction; nothing while `committee.flow` is off."""
    from core import killswitch

    if not killswitch.is_on("committee.flow", conn):
        return None
    with conn.transaction():
        return start(conn, cluster_id)


def backfill(conn: Conn) -> int:
    """The `qualify.backfill` job: approved groups still waiting for qualify (approved while the switch was off,
    or a start that failed). Each in its own transaction, so one failure does not stop the rest."""
    from core import killswitch

    if not killswitch.is_on("committee.flow", conn):
        return 0
    waiting = conn.execute(
        "SELECT c.id FROM clusters c WHERE c.state = 'approved' AND c.stage = 'in_cluster' AND NOT EXISTS "
        "(SELECT 1 FROM review_items i WHERE i.item_type = 'qualify' AND i.ref_id = c.id) ORDER BY c.id LIMIT 50"
    ).fetchall()
    started = 0
    for row in waiting:
        try:
            with conn.transaction():
                started += 1 if start(conn, str(row["id"])) else 0
        except Exception as exc:  # one group's failure is logged by ID and retried next time
            log.warning("qualify.backfill_failed", cluster_id=row["id"], error_type=type(exc).__name__)
    return started


def _finance_required(fields: dict[str, Any], annual: float | None) -> bool:
    limit = float(load_rule(get_settings().company_repo_path, "routing").data["finance_check_inr"])
    capex = fields.get("capex_inr") or 0
    return bool((annual or 0) >= limit or capex >= limit)


def _load(conn: Conn, item_id: int) -> tuple[dict[str, Any], str]:
    item = conn.execute("SELECT * FROM review_items WHERE id = %s FOR UPDATE", (item_id,)).fetchone()
    if item is None or item["item_type"] != "qualify":
        raise ActionRefused(404, "not_found")
    if item["state"] not in ("open", "in_progress"):
        raise ActionRefused(409, "already_decided")
    cluster = conn.execute(
        "SELECT id, stage FROM clusters WHERE id = %s FOR UPDATE", (item["ref_id"],)
    ).fetchone()
    if cluster is None or cluster["stage"] != "in_cluster":
        raise ActionRefused(409, "cluster_moved_on")
    return dict(item), str(item["ref_id"])


def _refuse_own(conn: Conn, user_id: str, cluster_id: str, item_id: int, action: str) -> None:
    if user_id and _contributors(conn, cluster_id) & {
        r["contributor_code"]
        for r in conn.execute(
            "SELECT contributor_code FROM contributor_map WHERE user_id = %s", (user_id,)
        ).fetchall()
    }:
        raise ActionRefused(
            409,
            "own_idea",
            (f"user:{user_id}", "review.own_idea_refused", f"qualify:{item_id}", {"action": action}),
        )


def _tagged_note(conn: Conn, cluster_id: str, note: Any) -> str | None:
    text = str(note or "").strip()
    if not text:
        return None
    if len(text) > 1000:
        raise ActionRefused(422, "note_length")
    if any(m.action == "block" for m in scan(text, kfin_domains=get_settings().kfin_domains)):
        raise ActionRefused(422, "personal_data")
    scope = conn.execute("SELECT tag_scope FROM clusters WHERE id = %s", (cluster_id,)).fetchone()
    return str(tag_payload(conn, (scope or {}).get("tag_scope") or cluster_id, {"t": text}).payload["t"])


def act(
    conn: Conn, item_id: int, reviewer: str, body: dict[str, Any], now: dt.datetime | None = None
) -> dict[str, Any]:
    now = now or dt.datetime.now(dt.UTC)
    action = body.get("action")
    if action not in ("confirm_gate", "save_impact", "finance_validated", "complete", "recheck"):
        raise ActionRefused(400, "unknown_action")
    with audited(conn), conn.transaction():
        item, cid = _load(conn, item_id)
        _refuse_own(conn, reviewer, cid, item_id, str(action))
        rev = staff_code(conn, reviewer)
        conn.execute(
            "UPDATE review_items SET state = 'in_progress', assigned_to = coalesce(assigned_to, %s) WHERE id = %s",
            (reviewer, item_id),
        )
        if action == "confirm_gate":
            gate, result = body.get("gate"), body.get("result")
            if gate not in GATES or result not in ("pass", "fail"):
                raise ActionRefused(400, "gate_and_result_required")
            detail = body.get("detail") if gate == "no_conflict" else None
            if gate == "no_conflict" and detail not in ("clear", "clear_with_conditions", "conflict"):
                raise ActionRefused(400, "compliance_outcome_required")
            if gate == "no_conflict":
                result = "fail" if detail == "conflict" else "pass"
            note = _tagged_note(conn, cid, body.get("note"))
            rules_said = conn.execute(
                "SELECT proposed FROM cluster_gates WHERE cluster_id = %s AND gate = %s", (cid, gate)
            ).fetchone()
            overrides = result == "pass" and rules_said is not None and rules_said["proposed"] == "fail"
            if (detail == "clear_with_conditions" or result == "fail" or overrides) and not note:
                raise ActionRefused(422, "note_required")  # a pass over the rules' "fail" says why
            conn.execute(
                "UPDATE cluster_gates SET result = %s, detail = %s, note = %s, confirmed_by = %s, confirmed_at = %s "
                "WHERE cluster_id = %s AND gate = %s",
                (result, detail, note, rev, now, cid, gate),
            )
            return {"gate": gate, "result": result}
        if action == "recheck":
            for gate, (proposed, evidence) in precheck(conn, cid).items():
                conn.execute(
                    "UPDATE cluster_gates SET proposed = %s, evidence = %s WHERE cluster_id = %s AND gate = %s "
                    "AND confirmed_at IS NULL",
                    (proposed, Jsonb(evidence), cid, gate),
                )
            return {"rechecked": True}
        if action == "save_impact":
            fields = _clean_fields(body.get("fields"))
            annual, payback = computed(fields)
            finance = _finance_required(fields, annual)
            conn.execute(
                "UPDATE impact_estimates SET fields = %s, annual_net_benefit = %s, payback_months = %s, "
                "finance_required = %s, finance_validated_by = CASE WHEN %s THEN finance_validated_by END, "
                "finance_validated_at = CASE WHEN %s THEN finance_validated_at END, updated_by = %s, "
                "version = version + 1 WHERE cluster_id = %s",
                (Jsonb(fields), annual, payback, finance, False, False, rev, cid),
            )  # any change to the numbers needs Finance to look again
            return {"annual_net_benefit": annual, "payback_months": payback, "finance_required": finance}
        if action == "finance_validated":
            row = conn.execute(
                "UPDATE impact_estimates SET finance_validated_by = %s, finance_validated_at = %s "
                "WHERE cluster_id = %s AND finance_required RETURNING 1",
                (rev, now, cid),
            ).fetchone()
            if row is None:
                raise ActionRefused(409, "finance_not_required")
            conn.execute(
                "INSERT INTO audit_log (actor, action, entity) VALUES (%s, 'qualify.finance_validated', %s)",
                (rev, f"cluster:{cid}"),
            )
            return {"finance_validated": True}
        return _complete(conn, item, cid, reviewer, rev, now)


def _complete(
    conn: Conn, item: dict[str, Any], cid: str, reviewer: str, rev: str, now: dt.datetime
) -> dict[str, Any]:
    gates = {
        r["gate"]: dict(r) for r in conn.execute("SELECT * FROM cluster_gates WHERE cluster_id = %s", (cid,))
    }
    if any(gates.get(g, {}).get("confirmed_at") is None for g in GATES):
        raise ActionRefused(409, "gates_not_confirmed")
    failed = [g for g in OUTCOMES if gates[g]["result"] == "fail"]
    members = _members(conn, cid)
    if failed:
        stage, reason = OUTCOMES[failed[0]]
        route_to, route_lob = None, None
    else:
        impact = conn.execute("SELECT * FROM impact_estimates WHERE cluster_id = %s", (cid,)).fetchone()
        if impact is None or impact["updated_by"] is None:
            raise ActionRefused(409, "impact_not_saved")
        if impact["finance_required"] and impact["finance_validated_at"] is None:
            raise ActionRefused(409, "finance_check_pending")
        stage, reason = "ready_for_scoring", None
        scope = conn.execute("SELECT scope, lobs FROM clusters WHERE id = %s", (cid,)).fetchone()
        business = any(m["kind"] == "business_idea" for m in members)
        lobs = list((scope or {}).get("lobs") or [])
        if (scope or {}).get("scope") == "lob" and not business and len(lobs) == 1:
            route_to, route_lob = "lob", lobs[0]
        else:
            route_to, route_lob = "core", None
    conn.execute(
        "UPDATE clusters SET stage = %s, reason_code = %s, route_to = %s, route_lob = %s, qualified_at = %s "
        "WHERE id = %s",
        (stage, reason, route_to, route_lob, now, cid),
    )
    conn.execute("UPDATE ideas SET stage = %s WHERE cluster_id = %s", (stage, cid))  # members mirror (§2.4)
    final = {
        "action": "complete",
        "stage": stage,
        "reason_code": reason,
        "route_to": route_to,
        "route_lob": route_lob,
    }
    conn.execute(
        "UPDATE review_items SET state = 'decided', decided_by = %s, decided_at = %s, final = %s WHERE id = %s",
        (reviewer, now, Jsonb(final), item["id"]),
    )
    engine.stop(conn, "review_item", str(item["id"]), "qualify")
    word = "qualified" if stage == "ready_for_scoring" else stage
    outbox = "INSERT INTO outbox (event_type, aggregate_id, actor, payload) VALUES (%s, %s, %s, %s)"
    conn.execute(outbox, ("cluster.updated", cid, rev, Jsonb({"note": reason or f"route {route_to}"})))
    for m in members:
        conn.execute(outbox, ("idea.stage_changed", m["idea_id"], rev,
                              Jsonb({"history": [{"event": word, "by": rev, "note": reason or ""}]})))  # fmt: skip
    if failed:
        emit(conn, "cluster.gate_outcome", {"cluster_id": cid, "reason_code": reason})
    conn.execute(
        "INSERT INTO audit_log (actor, action, entity, after) VALUES (%s, 'qualify.completed', %s, %s)",
        (rev, f"cluster:{cid}", Jsonb(final)),
    )
    log.info("qualify.completed", cluster_id=cid, stage=stage)
    return {"state": "decided"} | final
