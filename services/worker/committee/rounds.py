"""Preliminary review and shortlist (§4.6): a written, blind review whose outcome is a shortlist of clusters
whose contributors are invited to present.

- **Open a cycle** (the chair): every `ready_for_scoring` cluster joins a round for its committee (core, or the
  LOB committee for `lob` routes). The roster is fixed from active role grants; members who contributed to the
  cluster, and a contributor's direct manager in the HR directory, are flagged (conflict of interest, §3.1,
  BLD-221). A contributor must recuse; an admin may clear a manager flag with a reason. Conflicts
  are checked live on every view and action, so a colleague who joins later counts too, and a recusal carries
  into the presentation stage. `prescore` runs as a job after the round opens and stays hidden. A
  10-working-day timer starts.
- **Score**, blind: six dimensions, 1 to 5, the scorecard's anchors on screen; financial value starts from the band
  the impact estimate gives and may move one level with a reason. Contributors read as "Contributor 1…n" and every
  person tag stays a neutral label (restore mode `blind`).
- **Reveal** when every eligible member has scored, or by the chair at the deadline with quorum (60% of members
  not recused). Medians, ranges, the AI pre-score and two flags: range ≥ 2 "members disagree", |AI − median| ≥ 2
  "AI differs". Each member may revise once after reveal.
- **Final score** = Σ(weight × median) ÷ 5 × confidence multiplier (from the evidence type).
- **Decide** (core: the chair; LOB: a member of that LOB committee): shortlist (at or above the threshold, or below
  with a written reason by the chair), park or decline with a reason code (appealable), or nominate (LOB, at the
  nomination threshold). Shortlists beyond the cycle's presentation slots wait in score order.
Individual scores never leave the database and never reach the repo; the cluster file gets the medians only.
"""

from __future__ import annotations

import datetime as dt
import statistics
from typing import Any

from psycopg.types.json import Jsonb

from comms.route import emit
from core.config import get_settings
from core.db import Conn
from core.logging import get_logger
from pii import vault
from pii.patterns import scan
from pii.restore import restore
from pii.tagger import tag_payload
from review.service import ActionRefused, audited, staff_code
from rules import load_rule
from sla import engine
from sla.calendar import add_working_days

log = get_logger("committee.rounds")
FLAG_POINTS = 2
CYCLE_LOCK = 4_201_114_202


def scorecard() -> dict[str, Any]:
    return dict(load_rule(get_settings().company_repo_path, "scorecard").data)


def routing() -> dict[str, Any]:
    return dict(load_rule(get_settings().company_repo_path, "routing").data)


def band_for(annual: float | None, sc: dict[str, Any]) -> int | None:
    if annual is None:
        return None
    for level, (lo, hi) in sorted(sc["financial_bands_inr_per_year"].items(), key=lambda kv: int(kv[0])):
        if (lo is None or annual >= lo) and (hi is None or annual < hi):
            return int(level)
    return None


def final_score(medians: dict[str, float], sc: dict[str, Any], multiplier: float) -> float:
    total = sum(float(d["weight"]) * float(medians.get(name, 0)) for name, d in sc["dimensions"].items())
    return round(total / 5 * multiplier, 1)


def _roster(conn: Conn, body: str, lob: str | None) -> list[str]:
    if body == "core":
        rows = conn.execute(
            "SELECT DISTINCT g.user_id FROM role_grants g JOIN users u ON u.id = g.user_id "
            "WHERE g.role IN ('core_committee', 'core_chair') AND g.valid_to IS NULL AND u.active ORDER BY 1"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT DISTINCT g.user_id FROM role_grants g JOIN users u ON u.id = g.user_id "
            "WHERE g.role = 'lob_committee' AND g.scope_id = %s AND g.valid_to IS NULL AND u.active ORDER BY 1",
            (lob,),
        ).fetchall()
    return [str(r["user_id"]) for r in rows]


def _contributor_users(conn: Conn, cluster_id: str) -> set[str]:
    rows = conn.execute(
        "SELECT m.user_id FROM contributor_map m WHERE m.contributor_code IN (SELECT contributor_code FROM ideas "
        "WHERE cluster_id = %s UNION SELECT contributor_code FROM idea_links WHERE cluster_id = %s "
        "UNION SELECT l.contributor_code FROM idea_links l JOIN ideas i ON i.idea_id = l.idea_id WHERE i.cluster_id = %s)",
        (cluster_id, cluster_id, cluster_id),
    ).fetchall()
    return {str(r["user_id"]) for r in rows}


def manager_levels() -> int:
    """How far up a contributor's reporting line a committee member steps aside: `conflicts.manager_levels` in
    `rules/routing.md`. 0, the launch setting, checks no manager: the product lead kept managers in for the first
    quarter, as they are often the people closest to the problem (BLD-226). 1 is the direct manager (BLD-221), 2 the
    manager's manager as well. A repo without the setting reads as 0."""
    return int((routing().get("conflicts") or {}).get("manager_levels", 0))


def _managers_of(conn: Conn, users: set[str], depth: int) -> set[str]:
    """People up to `depth` levels above these users in the HR manager chain; nobody when `depth` is 0."""
    if not users or depth < 1:
        return set()
    rows = conn.execute(
        "WITH RECURSIVE up(id, lvl) AS (SELECT manager_user_id, 1 FROM users WHERE id = ANY(%s::uuid[]) "
        "AND manager_user_id IS NOT NULL UNION SELECT u.manager_user_id, up.lvl + 1 FROM users u JOIN up ON u.id = up.id "
        "WHERE u.manager_user_id IS NOT NULL AND up.lvl < %s) SELECT DISTINCT id FROM up",
        (sorted(users), depth),
    ).fetchall()
    return {str(r["id"]) for r in rows}


def conflict(conn: Conn, cluster_id: str, user_id: str) -> str | None:
    """Why this person may not see or act on the cluster's committee work, or None (§3.1). Checked live:
    `own_idea` (a contributor or joiner), `recused` (stepped aside on any round of the cluster), `flagged` (a flag
    not yet cleared), `manager` (a contributor's manager, unless an admin cleared it; off at launch, see
    `manager_levels`)."""
    contributors = _contributor_users(conn, cluster_id)
    if user_id in contributors:
        return "own_idea"
    statuses = {
        r["status"]
        for r in conn.execute(
            "SELECT f.status FROM coi_flags f JOIN scoring_rounds r ON r.id = f.round_id "
            "WHERE r.cluster_id = %s AND f.member_id = %s",
            (cluster_id, user_id),
        ).fetchall()
    }
    if "recused" in statuses:
        return "recused"
    if "flagged" in statuses:
        return "flagged"
    if "cleared" not in statuses and user_id in _managers_of(conn, contributors, manager_levels()):
        return "manager"
    return None


def is_chair(conn: Conn, user_id: str) -> bool:
    return bool(
        conn.execute(
            "SELECT 1 FROM role_grants WHERE user_id = %s AND role = 'core_chair' AND valid_to IS NULL",
            (user_id,),
        ).fetchone()
    )


# ---- open ------------------------------------------------------------------------------------------------------


def open_cycle(
    conn: Conn, chair: str, body: dict[str, Any], now: dt.datetime | None = None
) -> dict[str, Any]:
    """The chair opens this month's cycle; every ready cluster joins a round for its committee."""
    now = now or dt.datetime.now(dt.UTC)
    with audited(conn), conn.transaction():
        if not is_chair(conn, chair):
            raise ActionRefused(403, "chair_only")
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (CYCLE_LOCK,))  # two chairs at once get distinct ids
        rev = staff_code(conn, chair)
        base = f"CYC-{now.year}-{now.month:02d}"
        taken = {r["id"] for r in conn.execute("SELECT id FROM cycles WHERE id LIKE %s", (base + "%",))}
        cycle_id = base if base not in taken else f"{base}-{len(taken) + 1}"
        slots = body.get("presentation_slots", 8)
        if not isinstance(slots, int) or not 0 <= slots <= 50:
            raise ActionRefused(422, "bad_presentation_slots")
        sla_wd = int(load_rule(get_settings().company_repo_path, "sla").data["scoring_round"]["limit_wd"])
        closes = add_working_days(now, sla_wd)
        conn.execute(
            "INSERT INTO cycles (id, opened_by, shortlist_by) VALUES (%s, %s, %s)", (cycle_id, rev, closes)
        )
        conn.execute(
            "INSERT INTO capacity (cycle_id, presentation_slots, declared_by, declared_at) VALUES (%s, %s, %s, %s)",
            (cycle_id, slots, rev, now),
        )
        rounds = [
            open_round(conn, c["id"], cycle_id, now, closes)
            for c in conn.execute(
                "SELECT id FROM clusters WHERE stage = 'ready_for_scoring' AND state = 'approved' ORDER BY id"
            ).fetchall()
        ]
        conn.execute(
            "INSERT INTO audit_log (actor, action, entity, after) VALUES (%s, 'cycle.opened', %s, %s)",
            (rev, f"cycle:{cycle_id}", Jsonb({"rounds": len(rounds), "presentation_slots": slots})),
        )
    return {"cycle_id": cycle_id, "rounds": [r for r in rounds if r]}


def open_round(
    conn: Conn, cluster_id: str, cycle_id: str | None, now: dt.datetime, closes: dt.datetime
) -> str | None:
    c = conn.execute(
        "SELECT route_to, route_lob FROM clusters WHERE id = %s FOR UPDATE", (cluster_id,)
    ).fetchone()
    if c is None or c["route_to"] not in ("core", "lob"):
        return None
    body = str(c["route_to"])
    roster = _roster(conn, body, c["route_lob"])
    if body == "lob" and not roster:
        # No LOB committee for this LOB yet: the core committee reviews it, so the group never waits on an empty
        # roster (BLD-221).
        body, roster = "core", _roster(conn, "core", None)
        conn.execute("UPDATE clusters SET route_to = 'core' WHERE id = %s", (cluster_id,))
        log.info("round.no_lob_committee", cluster_id=cluster_id, lob_id=c["route_lob"])
    if conn.execute(
        "SELECT 1 FROM scoring_rounds WHERE cluster_id = %s AND body = %s AND state IN ('open', 'revealed')",
        (cluster_id, body),
    ).fetchone():
        return None
    sc = scorecard()
    impact = conn.execute(
        "SELECT fields, annual_net_benefit FROM impact_estimates WHERE cluster_id = %s", (cluster_id,)
    ).fetchone()
    evidence = ((impact or {}).get("fields") or {}).get("evidence_type") or "anecdote"
    multiplier = float(sc["confidence_multiplier"].get(evidence, 1.0))
    band = band_for(
        float(impact["annual_net_benefit"]) if impact and impact["annual_net_benefit"] is not None else None,
        sc,
    )
    n = conn.execute("SELECT next_number('RND', %s) AS n", (str(now.year),)).fetchone()
    assert n is not None
    round_id = f"RND-{now.year}-{int(n['n']):04d}"
    conn.execute(
        "INSERT INTO scoring_rounds (id, cluster_id, cycle_id, body, lob_id, scorecard_version, roster, quorum, "
        "evidence_type, suggested_band, confidence_multiplier, opens_at, closes_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (round_id, cluster_id, cycle_id, body, c["route_lob"] if body == "lob" else None, str(sc["version"]), roster,
         float(routing()["presentation"]["quorum"]), evidence, band, multiplier, now, closes),
    )  # fmt: skip
    contributors = _contributor_users(conn, cluster_id)
    managers = _managers_of(conn, contributors, manager_levels())
    for member in sorted(set(roster) & (contributors | managers)):
        conn.execute(
            "INSERT INTO coi_flags (round_id, member_id, reason, status) VALUES (%s, %s, %s, 'flagged')",
            (round_id, member, "contributor" if member in contributors else "manager"),
        )
    conn.execute("UPDATE clusters SET stage = 'ready_for_scoring' WHERE id = %s", (cluster_id,))
    engine.start(conn, "scoring_round", round_id, "scoring_round", now=now)
    from jobs.runner import enqueue

    # After commit, so the model call never holds the cycle's transaction or the cluster's lock (BLD-221).
    enqueue(conn, "round.prescore", {"round_id": round_id}, dedupe_key=f"prescore:{round_id}")
    emit(conn, "round.opened", {"round_id": round_id, "cluster_id": cluster_id, "member_ids": roster})
    log.info("round.opened", round_id=round_id, cluster_id=cluster_id, member_count=len(roster))
    return round_id


def _cluster_card(conn: Conn, cluster_id: str, mode: Any) -> dict[str, Any]:
    """The cluster as the committee reads it, in the given restore mode. Contributors become "Contributor n",
    numbered by first idea, consistently within the cluster (§3.1 blind mode)."""
    c = conn.execute(
        "SELECT id, title, summary, tag_scope, lobs, scope, member_count FROM clusters WHERE id = %s",
        (cluster_id,),
    ).fetchone()
    assert c is not None
    mapping = vault.mapping(conn, c["tag_scope"]) if c["tag_scope"] else {}
    summary = dict(c["summary"] or {})
    refs: dict[str, str] = summary.pop("refs", {}) or {}
    members = conn.execute(
        "SELECT idea_id, contributor_code, kind, category, play, canvas->>'one_line' AS one_line, "
        "canvas->>'details' AS details FROM ideas WHERE cluster_id = %s ORDER BY idea_id",
        (cluster_id,),
    ).fetchall()
    order: dict[str, int] = {}
    for m in members:
        order.setdefault(m["contributor_code"], len(order) + 1)
    by_idea = {m["idea_id"]: f"Contributor {order[m['contributor_code']]}" for m in members}
    for v in summary.get("variations") or []:
        v["member"] = by_idea.get(refs.get(v.get("member"), ""), "A contributor")
    for part in summary.get("solution") or []:
        part["credit"] = sorted(
            {by_idea.get(refs.get(r, ""), "A contributor") for r in part.get("credit") or []}
        )
    return {
        "id": c["id"],
        "name": restore(c["title"], mapping, mode),
        "summary": restore(summary, mapping, mode),
        "lobs": list(c["lobs"] or []),
        "scope": c["scope"],
        "ideas": [
            {
                "contributor": by_idea[m["idea_id"]],
                "kind": m["kind"],
                "category": m["category"],
                "play": m["play"],
                "one_line": restore(m["one_line"], vault.mapping(conn, m["idea_id"]), mode),
                "details": restore(m["details"], vault.mapping(conn, m["idea_id"]), mode),
            }
            for m in members
        ],
        "contributors": len(order),
    }


def prescore_round(conn: Conn, round_id: str) -> bool:
    """The `round.prescore` job: `prescore` for an open round that has none yet."""
    r = conn.execute(
        "SELECT cluster_id, state, suggested_band FROM scoring_rounds WHERE id = %s", (round_id,)
    ).fetchone()
    if r is None or r["state"] != "open":
        return False
    if conn.execute("SELECT 1 FROM ai_prescores WHERE round_id = %s LIMIT 1", (round_id,)).fetchone():
        return True
    with conn.transaction():
        return _prescore(conn, round_id, str(r["cluster_id"]), scorecard(), r["suggested_band"])


def _prescore(conn: Conn, round_id: str, cluster_id: str, sc: dict[str, Any], band: int | None) -> bool:
    """`prescore`, stored tagged under the cluster's scope and hidden until reveal."""
    from gateway import AgentFailed, run_agent

    row = conn.execute("SELECT tag_scope FROM clusters WHERE id = %s", (cluster_id,)).fetchone()
    scope = (row or {}).get("tag_scope") or cluster_id
    card = _cluster_card(conn, cluster_id, "real")  # real values in, so the gateway tags them consistently
    impact = conn.execute(
        "SELECT fields, annual_net_benefit, payback_months FROM impact_estimates WHERE cluster_id = %s",
        (cluster_id,),
    ).fetchone()
    try:
        out = run_agent(
            "prescore",
            {
                "cluster": {k: card[k] for k in ("name", "summary", "lobs", "scope", "ideas")},
                "impact": {
                    "fields": (impact or {}).get("fields") or {},
                    "annual_net_benefit_inr": float(impact["annual_net_benefit"])
                    if impact and impact["annual_net_benefit"] is not None
                    else None,
                    "suggested_financial_band": band,
                },
                "scorecard": {
                    name: {
                        "weight": d["weight"],
                        "label": d.get("label", name),
                        "anchors": d.get("anchors", {}),
                    }
                    for name, d in sc["dimensions"].items()
                },
            },
            scope,
            conn=conn,
        )
    except AgentFailed as exc:
        log.warning("round.prescore_unavailable", round_id=round_id, error_code=exc.code)
        return False
    for s in out.data["scores"]:
        conn.execute(
            "INSERT INTO ai_prescores (round_id, dimension, value, rationale, evidence_refs, generated_by) "
            "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
            (
                round_id,
                s["dimension"],
                s["value"],
                s["rationale"],
                Jsonb(s["evidence"]),
                f"prescore/{out.version}",
            ),
        )
    return True


# ---- views ------------------------------------------------------------------------------------------------------


def _eligible(conn: Conn, r: dict[str, Any]) -> list[str]:
    """Roster members who may score: no conflict (live, so later joiners and recusals count)."""
    return [str(m) for m in r["roster"] if conflict(conn, r["cluster_id"], str(m)) is None]


def _quorum_met(conn: Conn, r: dict[str, Any]) -> tuple[bool, int, int]:
    voting = len(_eligible(conn, r))
    scored = conn.execute(
        "SELECT count(DISTINCT member_id) AS n FROM sealed_scores WHERE round_id = %s AND member_id = ANY(%s::uuid[])",
        (r["id"], _eligible(conn, r)),
    ).fetchone()
    done = int(scored["n"] if scored else 0)
    return voting > 0 and done >= float(r["quorum"]) * voting, done, voting


def rounds_for(conn: Conn, user_id: str) -> list[dict[str, Any]]:
    """Rounds where this person is on the roster (or chairs the core committee), newest first. Counts only."""
    chair = is_chair(conn, user_id)
    rows = conn.execute(
        "SELECT r.*, c.title FROM scoring_rounds r JOIN clusters c ON c.id = r.cluster_id "
        "WHERE %s::uuid = ANY(r.roster) OR (r.body = 'core' AND %s) ORDER BY r.opens_at DESC LIMIT 100",
        (user_id, chair),
    ).fetchall()
    out = []
    for r in rows:
        mine = conn.execute(
            "SELECT 1 FROM sealed_scores WHERE round_id = %s AND member_id = %s LIMIT 1", (r["id"], user_id)
        ).fetchone()
        met, done, voting = _quorum_met(conn, dict(r))
        out.append({"id": r["id"], "cluster_id": r["cluster_id"], "body": r["body"], "lob_id": r["lob_id"],
                    "state": r["state"], "closes_at": r["closes_at"].isoformat(), "scored": done, "voting": voting,
                    "quorum_met": met, "i_scored": mine is not None, "outcome": r["outcome"],
                    "final_score": float(r["final_score"]) if r["final_score"] is not None else None})  # fmt: skip
    return out


def presentations_for(conn: Conn, user_id: str) -> list[dict[str, Any]]:
    """Presentations for the core committee's list (IDs, groups and states only)."""
    on_core = conn.execute(
        "SELECT 1 FROM role_grants WHERE user_id = %s AND role IN ('core_committee', 'core_chair') AND valid_to IS NULL",
        (user_id,),
    ).fetchone()
    if not on_core:
        return []
    return [
        {
            "id": r["id"],
            "cluster_id": r["cluster_id"],
            "state": r["state"],
            "slot_at": r["slot_at"].isoformat() if r["slot_at"] else None,
        }
        for r in conn.execute(
            "SELECT id, cluster_id, state, slot_at FROM presentations ORDER BY created_at DESC LIMIT 50"
        ).fetchall()
    ]


def direction_for(conn: Conn, cluster_id: str) -> str | None:
    from committee.appeals import direction_for as note

    return note(conn, cluster_id)


def round_view(conn: Conn, round_id: str, user_id: str) -> dict[str, Any] | None:
    r = conn.execute("SELECT * FROM scoring_rounds WHERE id = %s", (round_id,)).fetchone()
    if r is None:
        return None
    r = dict(r)
    if user_id not in {str(m) for m in r["roster"]} and not (r["body"] == "core" and is_chair(conn, user_id)):
        return None
    why = conflict(conn, r["cluster_id"], user_id)
    if why is not None:
        # A conflicted member sees that they are out of this review, never the group, the scores or the AI.
        flag = conn.execute(
            "SELECT reason, status FROM coi_flags WHERE round_id = %s AND member_id = %s", (round_id, user_id)
        ).fetchone()
        return {"id": round_id, "body": r["body"], "lob_id": r["lob_id"], "state": r["state"],
                "closes_at": r["closes_at"].isoformat(), "conflict": why, "my_flag": dict(flag) if flag else None,
                "chair": is_chair(conn, user_id), "outcome": r["outcome"]}  # fmt: skip
    sc = scorecard()
    revealed = r["state"] in ("revealed", "decided")
    mine = {
        s["dimension"]: s
        for s in conn.execute(
            "SELECT dimension, value, revised_value, comment FROM sealed_scores WHERE round_id = %s AND member_id = %s",
            (round_id, user_id),
        ).fetchall()
    }
    flag = conn.execute(
        "SELECT reason, status FROM coi_flags WHERE round_id = %s AND member_id = %s", (round_id, user_id)
    ).fetchone()
    met, done, voting = _quorum_met(conn, r)
    scope = conn.execute("SELECT tag_scope FROM clusters WHERE id = %s", (r["cluster_id"],)).fetchone()
    mapping = vault.mapping(conn, scope["tag_scope"]) if scope and scope["tag_scope"] else {}
    impact = conn.execute(
        "SELECT fields, annual_net_benefit, payback_months FROM impact_estimates WHERE cluster_id = %s",
        (r["cluster_id"],),
    ).fetchone()
    view: dict[str, Any] = {
        "id": round_id, "body": r["body"], "lob_id": r["lob_id"], "state": r["state"], "cycle_id": r["cycle_id"],
        "closes_at": r["closes_at"].isoformat(), "scorecard_version": r["scorecard_version"],
        "cluster": _cluster_card(conn, r["cluster_id"], "blind"),
        "impact": {"fields": (impact or {}).get("fields") or {},
                   "annual_net_benefit": float(impact["annual_net_benefit"]) if impact and impact["annual_net_benefit"] is not None else None,
                   "payback_months": float(impact["payback_months"]) if impact and impact["payback_months"] is not None else None},
        "suggested_band": r["suggested_band"], "evidence_type": r["evidence_type"],
        "confidence_multiplier": float(r["confidence_multiplier"]),
        "dimensions": [{"name": n, "label": d.get("label", n), "weight": d["weight"], "anchors": d.get("anchors", {})}
                       for n, d in sc["dimensions"].items()],
        "my_scores": {d: {"value": s["revised_value"] or s["value"], "first": s["value"], "revised": s["revised_value"] is not None,
                          "comment": restore(s["comment"], mapping, "blind")} for d, s in mine.items()},
        "my_flag": dict(flag) if flag else None,
        "conflict": None,
        "progress": {"scored": done, "voting": voting, "quorum_met": met},
        "chair": is_chair(conn, user_id),
        "outcome": r["outcome"], "reason_code": r["reason_code"],
        "appeal_direction": restore(direction_for(conn, r["cluster_id"]), mapping, "blind"),
    }  # fmt: skip
    if revealed:
        ai = conn.execute(
            "SELECT dimension, value, rationale FROM ai_prescores WHERE round_id = %s", (round_id,)
        ).fetchall()
        view["revealed"] = {
            "medians": r["medians"], "ranges": r["ranges"], "flags": r["flags"],
            "final_score": float(r["final_score"]) if r["final_score"] is not None else None,
            "ai": {a["dimension"]: {"value": a["value"], "rationale": restore(a["rationale"], mapping, "blind")} for a in ai},
            "thresholds": {"shortlist": routing()["shortlist_threshold"], "nomination": routing()["nomination_threshold"]},
        }  # fmt: skip
    return view


# ---- member actions ------------------------------------------------------------------------------------------


def on_roster_ids(r: dict[str, Any]) -> set[str]:
    return {str(m) for m in r["roster"]}


def open_flags(conn: Conn, admin: str) -> list[dict[str, Any]] | None:
    """For admins: conflict flags waiting on open rounds, with the member's name (admins see people, §3.1).
    Contributors' own flags are left out: they step aside and are never cleared."""
    if not conn.execute(
        "SELECT 1 FROM role_grants WHERE user_id = %s AND role = 'admin' AND valid_to IS NULL", (admin,)
    ).fetchone():
        return None
    rows = conn.execute(
        "SELECT f.round_id, r.cluster_id, f.member_id, u.name, f.reason, f.created_at FROM coi_flags f "
        "JOIN scoring_rounds r ON r.id = f.round_id JOIN users u ON u.id = f.member_id "
        "WHERE f.status = 'flagged' AND f.reason = 'manager' AND r.state = 'open' ORDER BY f.created_at LIMIT 200"
    ).fetchall()
    return [{"round_id": x["round_id"], "cluster_id": x["cluster_id"], "member_id": str(x["member_id"]),
             "name": x["name"], "reason": x["reason"], "flagged_at": x["created_at"].isoformat()} for x in rows]  # fmt: skip


def _load(conn: Conn, round_id: str) -> dict[str, Any]:
    r = conn.execute("SELECT * FROM scoring_rounds WHERE id = %s FOR UPDATE", (round_id,)).fetchone()
    if r is None:
        raise ActionRefused(404, "not_found")
    return dict(r)


def _tagged(conn: Conn, cluster_id: str, text: Any, min_chars: int = 0) -> str | None:
    t = str(text or "").strip()
    if not t:
        if min_chars:
            raise ActionRefused(422, "reason_required")
        return None
    if len(t) < min_chars:
        raise ActionRefused(422, "reason_too_short")
    if len(t) > 1000:
        raise ActionRefused(422, "text_too_long")
    if any(m.action == "block" for m in scan(t, kfin_domains=get_settings().kfin_domains)):
        raise ActionRefused(422, "personal_data")
    scope = conn.execute("SELECT tag_scope FROM clusters WHERE id = %s", (cluster_id,)).fetchone()
    return str(tag_payload(conn, (scope or {}).get("tag_scope") or cluster_id, {"t": t}).payload["t"])


def act(
    conn: Conn, round_id: str, user_id: str, body: dict[str, Any], now: dt.datetime | None = None
) -> dict[str, Any]:
    now = now or dt.datetime.now(dt.UTC)
    action = body.get("action")
    with audited(conn), conn.transaction():
        r = _load(conn, round_id)
        on_roster = user_id in {str(m) for m in r["roster"]}
        if action == "declare_conflict":
            if not on_roster or r["state"] != "open":
                raise ActionRefused(409, "not_open_to_you")
            conn.execute(
                "INSERT INTO coi_flags (round_id, member_id, reason, status) VALUES (%s, %s, 'declared', 'recused') "
                "ON CONFLICT (round_id, member_id) DO UPDATE SET status = 'recused', updated_at = now()",
                (round_id, user_id),
            )
            conn.execute(
                "DELETE FROM sealed_scores WHERE round_id = %s AND member_id = %s", (round_id, user_id)
            )
            conn.execute(
                "INSERT INTO audit_log (actor, action, entity) VALUES (%s, 'round.recused', %s)",
                (f"user:{user_id}", f"round:{round_id}"),
            )
            return {"recused": True}
        if action == "clear_conflict":  # admin only; the web app checks the role, the handler re-checks
            admin = conn.execute(
                "SELECT 1 FROM role_grants WHERE user_id = %s AND role = 'admin' AND valid_to IS NULL",
                (user_id,),
            ).fetchone()
            if not admin:
                raise ActionRefused(403, "admin_only")
            member = str(body.get("member_id") or "")
            reason = _tagged(conn, r["cluster_id"], body.get("reason"), min_chars=10)
            if member in _contributor_users(conn, r["cluster_id"]):
                raise ActionRefused(409, "contributors_recuse")  # never cleared to score their own group
            row = conn.execute(
                "UPDATE coi_flags SET status = 'cleared', cleared_by = %s, clear_reason = %s, updated_at = now() "
                "WHERE round_id = %s AND member_id = %s AND status = 'flagged' RETURNING 1",
                (f"user:{user_id}", reason, round_id, member),
            ).fetchone()
            if (
                row is None
                and member in on_roster_ids(r)
                and conflict(conn, r["cluster_id"], member) == "manager"
            ):
                # A manager of a colleague who joined after the round opened has no flag row yet.
                row = conn.execute(
                    "INSERT INTO coi_flags (round_id, member_id, reason, status, cleared_by, clear_reason) "
                    "VALUES (%s, %s, 'manager', 'cleared', %s, %s) RETURNING 1",
                    (round_id, member, f"user:{user_id}", reason),
                ).fetchone()
            if row is None:
                raise ActionRefused(409, "no_flag_to_clear")
            conn.execute(
                "INSERT INTO audit_log (actor, action, entity, after) VALUES (%s, 'round.conflict_cleared', %s, %s)",
                (f"user:{user_id}", f"round:{round_id}", Jsonb({"member": member})),
            )
            return {"cleared": True}
        if action == "score":
            return _score(conn, r, user_id, body, now)
        if action == "revise":
            return _revise(conn, r, user_id, body, now)
        if action == "reveal":
            if not (r["body"] == "core" and is_chair(conn, user_id)) and not (
                r["body"] == "lob" and on_roster
            ):
                raise ActionRefused(403, "chair_only")
            if r["state"] != "open":
                raise ActionRefused(409, "not_open")
            _refuse_conflicted(conn, r, user_id)
            met, done, voting = _quorum_met(conn, r)
            everyone = done >= voting and done > 0
            if not everyone and not (now >= r["closes_at"] and met):
                raise ActionRefused(409, "not_ready_to_reveal")
            return _reveal(conn, r, now)
        if action == "decide":
            return _decide(conn, r, user_id, body, now)
        raise ActionRefused(400, "unknown_action")


def _refuse_conflicted(conn: Conn, r: dict[str, Any], user_id: str) -> None:
    why = conflict(conn, r["cluster_id"], user_id)
    if why == "own_idea":
        raise ActionRefused(
            409, "own_idea", (f"user:{user_id}", "review.own_idea_refused", f"round:{r['id']}", {})
        )
    if why is not None:
        raise ActionRefused(409, "conflict_of_interest")


def _score(
    conn: Conn, r: dict[str, Any], user_id: str, body: dict[str, Any], now: dt.datetime
) -> dict[str, Any]:
    if r["state"] != "open":
        raise ActionRefused(409, "not_open")
    if user_id not in _eligible(conn, r):
        raise ActionRefused(409, "not_eligible")  # not on the roster, recused, or flagged and not cleared
    if conn.execute(
        "SELECT 1 FROM sealed_scores WHERE round_id = %s AND member_id = %s LIMIT 1", (r["id"], user_id)
    ).fetchone():
        raise ActionRefused(409, "already_scored")
    sc = scorecard()
    scores = body.get("scores") or {}
    comments = body.get("comments") or {}
    if not isinstance(scores, dict) or set(scores) != set(sc["dimensions"]):
        raise ActionRefused(422, "every_dimension_required")
    for v in scores.values():
        if not isinstance(v, int) or isinstance(v, bool) or not 1 <= v <= 5:
            raise ActionRefused(422, "scores_are_1_to_5")
    band = r["suggested_band"]
    fin = scores.get("financial_value")
    move_reason = None
    if band is not None and fin != band:
        if abs(int(scores["financial_value"]) - int(band)) > 1:
            raise ActionRefused(422, "financial_within_one_level")
        move_reason = _tagged(conn, r["cluster_id"], body.get("financial_reason"), min_chars=10)
    for dim, v in scores.items():
        comment = _tagged(conn, r["cluster_id"], comments.get(dim)) if isinstance(comments, dict) else None
        if dim == "financial_value" and move_reason:
            comment = (comment + " " if comment else "") + f"(moved from the suggested level: {move_reason})"
        conn.execute(
            "INSERT INTO sealed_scores (round_id, member_id, dimension, value, comment, submitted_at) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (r["id"], user_id, dim, v, comment, now),
        )
    log.info("round.scored", round_id=r["id"])
    _met, done, voting = _quorum_met(conn, r)
    if done >= voting:
        _reveal(conn, r, now)  # everyone eligible has scored
        return {"scored": True, "revealed": True}
    return {"scored": True, "revealed": False}


def _aggregate(
    conn: Conn, r: dict[str, Any]
) -> tuple[dict[str, float], dict[str, int], dict[str, list[str]]]:
    rows = conn.execute(  # a member who joined the group after scoring no longer counts
        "SELECT dimension, coalesce(revised_value, value) AS v FROM sealed_scores WHERE round_id = %s "
        "AND member_id = ANY(%s::uuid[])",
        (r["id"], _eligible(conn, r)),
    ).fetchall()
    by: dict[str, list[int]] = {}
    for row in rows:
        by.setdefault(row["dimension"], []).append(int(row["v"]))
    ai = {
        a["dimension"]: int(a["value"])
        for a in conn.execute(
            "SELECT dimension, value FROM ai_prescores WHERE round_id = %s", (r["id"],)
        ).fetchall()
    }
    medians = {d: float(statistics.median(v)) for d, v in by.items()}
    ranges = {d: max(v) - min(v) for d, v in by.items()}
    flags: dict[str, list[str]] = {}
    for d in medians:
        f = []
        if ranges[d] >= FLAG_POINTS:
            f.append("members_disagree")
        if d in ai and abs(ai[d] - medians[d]) >= FLAG_POINTS:
            f.append("ai_differs")
        if f:
            flags[d] = f
    return medians, ranges, flags


def _reveal(conn: Conn, r: dict[str, Any], now: dt.datetime) -> dict[str, Any]:
    medians, ranges, flags = _aggregate(conn, r)
    score = final_score(medians, scorecard(), float(r["confidence_multiplier"]))
    conn.execute(
        "UPDATE scoring_rounds SET state = 'revealed', revealed_at = %s, medians = %s, ranges = %s, flags = %s, "
        "final_score = %s WHERE id = %s",
        (now, Jsonb(medians), Jsonb(ranges), Jsonb(flags), score, r["id"]),
    )
    conn.execute("UPDATE clusters SET stage = 'scored' WHERE id = %s", (r["cluster_id"],))
    conn.execute("UPDATE ideas SET stage = 'scored' WHERE cluster_id = %s", (r["cluster_id"],))
    conn.execute(
        "INSERT INTO audit_log (actor, action, entity, after) VALUES ('process:rounds', 'round.revealed', %s, %s)",
        (f"round:{r['id']}", Jsonb({"final_score": score})),
    )
    return {"revealed": True, "final_score": score}


def _revise(
    conn: Conn, r: dict[str, Any], user_id: str, body: dict[str, Any], now: dt.datetime
) -> dict[str, Any]:
    if r["state"] != "revealed":
        raise ActionRefused(409, "not_revealed")
    mine = conn.execute(
        "SELECT dimension, revised_value FROM sealed_scores WHERE round_id = %s AND member_id = %s",
        (r["id"], user_id),
    ).fetchall()
    if not mine:
        raise ActionRefused(409, "not_scored")
    if any(m["revised_value"] is not None for m in mine):
        raise ActionRefused(409, "already_revised")  # once after reveal; both values are kept
    scores = body.get("scores") or {}
    if not isinstance(scores, dict) or not scores or not set(scores) <= {m["dimension"] for m in mine}:
        raise ActionRefused(422, "bad_scores")
    for dim, v in scores.items():
        if not isinstance(v, int) or isinstance(v, bool) or not 1 <= v <= 5:
            raise ActionRefused(422, "scores_are_1_to_5")
        conn.execute(
            "UPDATE sealed_scores SET revised_value = %s, revised_at = %s WHERE round_id = %s AND member_id = %s "
            "AND dimension = %s",
            (v, now, r["id"], user_id, dim),
        )
    medians, ranges, flags = _aggregate(conn, r)
    score = final_score(medians, scorecard(), float(r["confidence_multiplier"]))
    conn.execute(
        "UPDATE scoring_rounds SET medians = %s, ranges = %s, flags = %s, final_score = %s WHERE id = %s",
        (Jsonb(medians), Jsonb(ranges), Jsonb(flags), score, r["id"]),
    )
    return {"revised": True, "final_score": score}


# ---- the outcome (§4.6 steps 8–10) ------------------------------------------------------------------------------

OUTCOME_STAGE = {
    "shortlisted": "shortlisted",
    "parked": "parked",
    "declined": "declined",
    "nominated": "ready_for_scoring",
}
REASONS = {"parked": {"NOT_FEASIBLE_NOW", "INSUFFICIENT_EVIDENCE", "CAPACITY"}, "declined": {"LOW_VALUE", "NOT_FEASIBLE_NOW", "REG_CONFLICT", "OUT_OF_SCOPE"}}  # fmt: skip


def _record_preliminary(
    conn: Conn,
    r: dict[str, Any],
    outcome: str,
    reason_code: str | None,
    note: str | None,
    rev: str,
    now: dt.datetime,
) -> str:
    """A preliminary review's park or decline is a decision on record (§4.6 step 9): a decision file, and the
    15-working-day appeal window when it can be appealed (§4.12, BLD-222). It has no votes: members scored."""
    from committee.appeals import WINDOW_WD, appealable

    n = conn.execute("SELECT next_number('DEC', %s) AS n", (str(now.year),)).fetchone()
    assert n is not None
    did = f"DEC-{now.year}-{int(n['n']):04d}"
    scored = conn.execute(
        "SELECT count(DISTINCT member_id) AS n FROM sealed_scores WHERE round_id = %s", (r["id"],)
    ).fetchone()
    window = add_working_days(now, WINDOW_WD) if appealable(conn, r["cluster_id"], outcome) else None
    conn.execute(
        "INSERT INTO decisions (id, cluster_id, round_id, cycle_id, body, outcome, reason_code, plain_reason, votes, "
        "members_present, recused, decided_by, decided_at, appeal_window_closes) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (did, r["cluster_id"], r["id"], r["cycle_id"], r["body"], outcome, reason_code, note, Jsonb({}),
         int(scored["n"] if scored else 0), len(r["roster"]) - len(_eligible(conn, r)), rev, now, window),
    )  # fmt: skip
    if window:
        engine.start(conn, "decision", did, "appeal_window", now=now)
    conn.execute(
        "INSERT INTO outbox (event_type, aggregate_id, actor, payload) VALUES ('decision.recorded', %s, %s, %s)",
        (did, rev, Jsonb({"decision_id": did, "verified_by": rev})),
    )
    return did


def _decide(
    conn: Conn, r: dict[str, Any], user_id: str, body: dict[str, Any], now: dt.datetime
) -> dict[str, Any]:
    if r["state"] != "revealed":
        raise ActionRefused(409, "not_revealed")
    outcome = body.get("outcome")
    rules = routing()
    if r["body"] == "core":
        if not is_chair(conn, user_id):
            raise ActionRefused(403, "chair_only")
        if outcome not in ("shortlisted", "parked", "declined"):
            raise ActionRefused(400, "bad_outcome")
    else:
        if user_id not in {str(m) for m in r["roster"]}:
            raise ActionRefused(403, "committee_only")
        if outcome not in ("parked", "declined", "nominated"):
            raise ActionRefused(
                400, "bad_outcome"
            )  # a LOB committee parks, declines or nominates (§4.6 step 8)
    _refuse_conflicted(conn, r, user_id)
    rev = staff_code(conn, user_id)
    score = float(r["final_score"] or 0)
    reason_code, note, below = None, None, None
    if outcome in ("parked", "declined"):
        reason_code = body.get("reason_code")
        if reason_code not in REASONS[str(outcome)]:
            raise ActionRefused(422, "reason_code_required")
        note = _tagged(conn, r["cluster_id"], body.get("note"), min_chars=20)
    if outcome == "shortlisted" and score < float(rules["shortlist_threshold"]):
        below = _tagged(conn, r["cluster_id"], body.get("below_threshold_reason"), min_chars=30)
    if outcome == "nominated" and score < float(rules["nomination_threshold"]):
        raise ActionRefused(409, "below_nomination_threshold")
    queue = None
    if outcome == "shortlisted" and r["cycle_id"]:
        slots = conn.execute(
            "SELECT presentation_slots FROM capacity WHERE cycle_id = %s", (r["cycle_id"],)
        ).fetchone()
        taken = conn.execute(
            "SELECT count(*) AS n FROM scoring_rounds WHERE cycle_id = %s AND outcome = 'shortlisted' "
            "AND queue_position IS NULL",
            (r["cycle_id"],),
        ).fetchone()
        if slots and taken and int(taken["n"]) >= int(slots["presentation_slots"]):
            waiting = conn.execute(
                "SELECT count(*) AS n FROM scoring_rounds WHERE cycle_id = %s AND queue_position IS NOT NULL",
                (r["cycle_id"],),
            ).fetchone()
            queue = int(waiting["n"] if waiting else 0) + 1  # waits for the next session, in score order
    conn.execute(
        "UPDATE scoring_rounds SET state = 'decided', outcome = %s, reason_code = %s, outcome_note = %s, "
        "below_threshold_reason = %s, queue_position = %s, decided_by = %s, decided_at = %s WHERE id = %s",
        (outcome, reason_code, note, below, queue, rev, now, r["id"]),
    )
    stage = OUTCOME_STAGE[str(outcome)]
    conn.execute(
        "UPDATE clusters SET stage = %s, reason_code = %s, route_to = CASE WHEN %s THEN 'core' ELSE route_to END "
        "WHERE id = %s",
        (stage, reason_code, outcome == "nominated", r["cluster_id"]),
    )
    conn.execute("UPDATE ideas SET stage = %s WHERE cluster_id = %s", (stage, r["cluster_id"]))
    engine.stop(conn, "scoring_round", r["id"], "scoring_round")
    outbox = "INSERT INTO outbox (event_type, aggregate_id, actor, payload) VALUES (%s, %s, %s, %s)"
    conn.execute(
        outbox, ("cluster.updated", r["cluster_id"], rev, Jsonb({"note": f"preliminary review {outcome}"}))
    )
    for m in conn.execute("SELECT idea_id FROM ideas WHERE cluster_id = %s", (r["cluster_id"],)).fetchall():
        conn.execute(outbox, ("idea.stage_changed", m["idea_id"], rev, Jsonb({"history": [{"event": stage, "by": rev, "note": reason_code or ""}]})))  # fmt: skip
    if outcome == "shortlisted":
        from committee.decide import invite

        pid = invite(conn, r["cluster_id"], r["id"], r["cycle_id"], now)
        emit(
            conn,
            "shortlist.invited",
            {"cluster_id": r["cluster_id"], "round_id": r["id"], "presentation_id": pid},
        )
    elif outcome in ("parked", "declined"):
        did = _record_preliminary(conn, r, str(outcome), reason_code, note, rev, now)
        emit(
            conn,
            "round.not_shortlisted",
            {
                "cluster_id": r["cluster_id"],
                "round_id": r["id"],
                "reason_code": reason_code,
                "decision_id": did,
            },
        )
    conn.execute(
        "INSERT INTO audit_log (actor, action, entity, after) VALUES (%s, 'round.decided', %s, %s)",
        (rev, f"round:{r['id']}", Jsonb({"outcome": outcome, "reason_code": reason_code, "below_threshold": below is not None, "queue_position": queue})),
    )  # fmt: skip
    return {"state": "decided", "outcome": outcome, "queue_position": queue}
