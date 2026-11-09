"""Appeals (§4.12), minimal version (DEC-057, BLD-222).

- **What can be appealed:** a committee's decision to decline, or to park a group that was parked before ("parked
  twice"), within 15 working days, once per decision. Appeals against the review desk's own decisions (redirect,
  merge, withdrawal) and against a missed time limit keep the day-one "Disagree with this?" route for now
  ("Coming soon" here).
- **Filing:** the submitter or any co-contributor of the group. Grounds (process not followed, misunderstood or
  wrongly grouped, new evidence), a statement of up to 500 words and up to five evidence links (stored as given,
  never fetched). Both personal-data checks run on the statement, before anything is stored; it is stored tagged.
  The colleagues may ask for a 10-minute hearing (the panel arranges it; calendar invitations are "Coming soon").
- **Who hears it:** a LOB committee's decision goes to the core committee, minus anyone with a conflict. A core
  committee decision goes to a panel of three core committee members by rotation (fewest appeals heard first):
  never anyone with a conflict on the group (§3.1, the same live check as the committee) or the person who recorded
  the decision, and at least one member who did not vote for the outcome. The most senior member chairs (longest
  on the committee: the HR export has no grade yet). If fewer than three qualify, every eligible member sits; the
  full committee re-hearing with the colleagues presenting is "Coming soon". The outside seat
  (`appeals.outside_seat`) stays off.
- **The panel** reads the blind materials, the decision with its medians and spread (never individual scores) and
  the appeal, and the chair records within 15 working days: **upheld** (fuller reasons), **re-score** (back to a
  scoring round with a direction note the next round shows) or **overturned** (a preliminary decision goes straight
  to an invitation to present, above the line; a decision after the presentation goes back to the chair to decide
  again, picked if capacity allows).
- The appeal file (`appeals/YYYY/APL-….md`) is written and linked from the decision file; the colleagues are told.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from psycopg.types.json import Jsonb

from committee.rounds import _cluster_card, _tagged, conflict
from comms.route import emit
from core.config import get_settings
from core.db import Conn
from core.logging import get_logger
from pii import vault
from pii.patterns import scan
from pii.restore import restore
from pii.tagger import tag_payload
from review.service import ActionRefused, audited, staff_code
from sla import engine
from sla.calendar import add_working_days

log = get_logger("committee.appeals")
GROUNDS = ("process_not_followed", "misunderstood_or_wrongly_merged", "new_evidence")
OUTCOMES = ("upheld", "re_score", "overturned")
MAX_WORDS = 500
MAX_CHARS = 4000
PANEL = 3
WINDOW_WD = 15


# ---- who may appeal what ---------------------------------------------------------------------------------------


def appealable(conn: Conn, cluster_id: str, outcome: str, decision_id: str | None = None) -> bool:
    """A decline, or a park when the group was parked before (§4.12 "parked twice")."""
    if outcome == "declined":
        return True
    if outcome != "parked":
        return False
    before = conn.execute(
        "SELECT count(*) AS n FROM decisions WHERE cluster_id = %s AND outcome = 'parked' AND id IS DISTINCT FROM %s",
        (cluster_id, decision_id),
    ).fetchone()
    return int(before["n"] if before else 0) >= 1


def _codes(conn: Conn, user_id: str) -> set[str]:
    return {
        r["contributor_code"]
        for r in conn.execute(
            "SELECT contributor_code FROM contributor_map WHERE user_id = %s", (user_id,)
        ).fetchall()
    }


def _cluster_codes(conn: Conn, cluster_id: str) -> set[str]:
    return {
        r["contributor_code"]
        for r in conn.execute(
            "SELECT contributor_code FROM ideas WHERE cluster_id = %s UNION SELECT contributor_code FROM idea_links "
            "WHERE cluster_id = %s AND link_type IN ('originator', 'joiner')",
            (cluster_id, cluster_id),
        ).fetchall()
    }


def _statement_checked(conn: Conn, cluster_id: str, statement: str) -> None:
    """Both personal-data checks (§4.12): the patterns, then the gatekeeper. Run before any transaction opens, so
    the model call never holds a lock. If the assistant is unavailable the appeal waits: it is never stored
    unchecked."""
    from gateway import AgentFailed, run_agent
    from scan.pipeline import decide as gate
    from scan.pipeline import thresholds

    if any(m.action == "block" for m in scan(statement, kfin_domains=get_settings().kfin_domains)):
        raise ActionRefused(422, "personal_data")
    scope = conn.execute("SELECT tag_scope FROM clusters WHERE id = %s", (cluster_id,)).fetchone()
    try:
        gk = run_agent(
            "gatekeeper",
            {"mode": "submission", "submission": {"details": statement}},
            (scope or {}).get("tag_scope") or cluster_id,
            conn=conn,
        )
    except AgentFailed:
        raise ActionRefused(503, "checks_unavailable") from None
    if gate(gk.data, thresholds()) == "blocked":
        raise ActionRefused(422, "personal_data")


# ---- filing ------------------------------------------------------------------------------------------------------


def file(conn: Conn, user_id: str, body: dict[str, Any], now: dt.datetime | None = None) -> dict[str, Any]:
    now = now or dt.datetime.now(dt.UTC)
    did = str(body.get("decision_id") or "")
    grounds = body.get("grounds") or []
    if not isinstance(grounds, list) or not grounds or not set(grounds) <= set(GROUNDS):
        raise ActionRefused(422, "grounds_required")
    statement = str(body.get("statement") or "").strip()
    if len(statement.split()) > MAX_WORDS or len(statement) > MAX_CHARS:
        raise ActionRefused(422, "statement_too_long")
    if len(statement) < 30:
        raise ActionRefused(422, "statement_too_short")
    raw_links = body.get("links") or []
    if not isinstance(raw_links, list) or len(raw_links) > 5:
        raise ActionRefused(422, "links_at_most_5")
    links = [str(x).strip()[:500] for x in raw_links if str(x).strip()]
    if any(not link.startswith(("https://", "http://")) for link in links):
        raise ActionRefused(422, "links_must_be_web_addresses")
    d = conn.execute("SELECT cluster_id FROM decisions WHERE id = %s", (did,)).fetchone()
    if d is None or not (_codes(conn, user_id) & _cluster_codes(conn, d["cluster_id"])):
        raise ActionRefused(404, "not_found")
    _statement_checked(conn, d["cluster_id"], statement)

    with audited(conn), conn.transaction():
        d = conn.execute("SELECT * FROM decisions WHERE id = %s FOR UPDATE", (did,)).fetchone()
        assert d is not None
        cid = str(d["cluster_id"])
        if not appealable(conn, cid, d["outcome"], did):
            raise ActionRefused(409, "not_appealable")
        if d["appeal_window_closes"] is None or now > d["appeal_window_closes"]:
            raise ActionRefused(409, "window_closed")
        if conn.execute("SELECT 1 FROM appeals WHERE decision_id = %s", (did,)).fetchone():
            raise ActionRefused(409, "already_appealed")  # one appeal per decision
        scope = conn.execute("SELECT tag_scope FROM clusters WHERE id = %s", (cid,)).fetchone()
        tagged = str(tag_payload(conn, (scope or {}).get("tag_scope") or cid, {"t": statement}).payload["t"])
        heard_by, panel = _panel(conn, dict(d))
        if not panel:
            raise ActionRefused(409, "no_panel_available")
        n = conn.execute("SELECT next_number('APL', %s) AS n", (str(now.year),)).fetchone()
        assert n is not None
        aid = f"APL-{now.year}-{int(n['n']):04d}"
        appellant = sorted(_codes(conn, user_id) & _cluster_codes(conn, cid))[0]
        conn.execute(
            "INSERT INTO appeals (id, decision_id, cluster_id, appellant_code, grounds, statement, links, "
            "hearing_requested, heard_by, panel, state, due_at, filed_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'open', %s, %s)",
            (aid, did, cid, appellant, sorted(set(grounds)), tagged, Jsonb(links), bool(body.get("hearing")),
             heard_by, panel, add_working_days(now, WINDOW_WD), now),
        )  # fmt: skip
        conn.execute("UPDATE clusters SET stage = 'appealed' WHERE id = %s", (cid,))
        conn.execute("UPDATE ideas SET stage = 'appealed' WHERE cluster_id = %s", (cid,))
        engine.stop(conn, "decision", did, "appeal_window")
        engine.start(conn, "appeal", aid, "appeal_decision", now=now)
        outbox = "INSERT INTO outbox (event_type, aggregate_id, actor, payload) VALUES (%s, %s, %s, %s)"
        conn.execute(outbox, ("appeal.filed", aid, appellant, Jsonb({"appeal_id": aid})))
        conn.execute(
            outbox, ("decision.recorded", did, appellant, Jsonb({"decision_id": did}))
        )  # links the appeal
        emit(conn, "appeal.filed", {"appeal_id": aid, "cluster_id": cid, "member_ids": panel})
        conn.execute(
            "INSERT INTO audit_log (actor, action, entity, after) VALUES (%s, 'appeal.filed', %s, %s)",
            (appellant, f"appeal:{aid}", Jsonb({"decision": did, "grounds": sorted(set(grounds)), "panel": len(panel),
                                                 "heard_by": heard_by})),
        )  # fmt: skip
    log.info("appeal.filed", appeal_id=aid, decision_id=did)
    return {"appeal_id": aid, "state": "open", "heard_by": heard_by}


def _core_members(conn: Conn) -> list[dict[str, Any]]:
    """Active core committee members, most senior first (the earliest grant: the HR export has no grade yet), with
    how many appeals each has heard."""
    rows = conn.execute(
        "SELECT g.user_id, min(g.valid_from) AS since, "
        "(SELECT count(*) FROM appeals a WHERE g.user_id = ANY(a.panel)) AS heard "
        "FROM role_grants g JOIN users u ON u.id = g.user_id "
        "WHERE g.role IN ('core_committee', 'core_chair') AND g.valid_to IS NULL AND u.active "
        "GROUP BY g.user_id ORDER BY since, g.user_id"
    ).fetchall()
    return [{"id": str(r["user_id"]), "since": r["since"], "heard": int(r["heard"])} for r in rows]


def _panel(conn: Conn, d: dict[str, Any]) -> tuple[str, list[str]]:
    """Who hears the appeal (§4.12 table), most senior first: the first member chairs."""
    decider = conn.execute("SELECT id FROM users WHERE staff_code = %s", (d["decided_by"],)).fetchone()
    excluded = {str(decider["id"])} if decider else set()
    eligible = [
        m
        for m in _core_members(conn)
        if m["id"] not in excluded and conflict(conn, d["cluster_id"], m["id"]) is None
    ]
    if d["body"] == "lob":
        return "core_committee", [m["id"] for m in eligible]
    if len(eligible) <= PANEL:
        return "panel", [m["id"] for m in eligible]
    # Rotation: fewest appeals heard first, then seniority. At least one member who did not vote for the outcome
    # (votes come from the sealed assessments, read only here; a preliminary decision has no votes).
    agreed = {"parked": "park", "declined": "decline"}.get(d["outcome"], "")
    voted_for = (
        {
            str(r["member_id"])
            for r in conn.execute(
                "SELECT member_id FROM assessments WHERE presentation_id = %s AND vote = %s",
                (d["presentation_id"], agreed),
            ).fetchall()
        }
        if d.get("presentation_id")
        else set()
    )
    by_turn = sorted(eligible, key=lambda m: (m["heard"], m["since"], m["id"]))
    chosen = by_turn[:PANEL]
    if voted_for and all(m["id"] in voted_for for m in chosen):
        outsider = next((m for m in by_turn[PANEL:] if m["id"] not in voted_for), None)
        if outsider:
            chosen[-1] = outsider
    chosen.sort(key=lambda m: (m["since"], m["id"]))  # the most senior chairs
    return "panel", [m["id"] for m in chosen]


# ---- the panel ---------------------------------------------------------------------------------------------------


def _decision_scores(conn: Conn, d: dict[str, Any]) -> dict[str, Any]:
    """Medians and spread, never individual scores: from the decision sheet, or the round for a preliminary one."""
    sheet = (
        conn.execute(
            "SELECT medians, spread, final_score FROM decision_sheets WHERE presentation_id = %s",
            (d["presentation_id"],),
        ).fetchone()
        if d.get("presentation_id")
        else None
    )
    if sheet:
        return {"medians": sheet["medians"], "spread": sheet["spread"],
                "final_score": float(sheet["final_score"]) if sheet["final_score"] is not None else None}  # fmt: skip
    r = (
        conn.execute(
            "SELECT medians, ranges, final_score FROM scoring_rounds WHERE id = %s", (d["round_id"],)
        ).fetchone()
        if d.get("round_id")
        else None
    )
    if r:
        return {"medians": r["medians"], "spread": r["ranges"],
                "final_score": float(r["final_score"]) if r["final_score"] is not None else None}  # fmt: skip
    return {"medians": None, "spread": None, "final_score": None}


def panel_view(conn: Conn, aid: str, user_id: str) -> dict[str, Any] | None:
    a = conn.execute("SELECT * FROM appeals WHERE id = %s", (aid,)).fetchone()
    if a is None or user_id not in {str(p) for p in a["panel"]}:
        return None
    if conflict(conn, a["cluster_id"], user_id) is not None:
        return None  # joined the group after the panel was formed: no longer sees it
    d = conn.execute("SELECT * FROM decisions WHERE id = %s", (a["decision_id"],)).fetchone()
    assert d is not None
    scope = conn.execute("SELECT tag_scope FROM clusters WHERE id = %s", (a["cluster_id"],)).fetchone()
    mapping = vault.mapping(conn, scope["tag_scope"]) if scope and scope["tag_scope"] else {}
    return {
        "id": aid, "state": a["state"], "due_at": a["due_at"].isoformat(), "grounds": list(a["grounds"]),
        "statement": restore(a["statement"], mapping, "blind"), "links": a["links"],
        "hearing_requested": a["hearing_requested"], "heard_by": a["heard_by"],
        "cluster": _cluster_card(conn, a["cluster_id"], "blind"),
        "decision": {"id": d["id"], "body": d["body"], "outcome": d["outcome"], "reason_code": d["reason_code"],
                     "reason": restore(d["plain_reason"], mapping, "blind"),
                     "what_would_change": restore(d["what_would_change"], mapping, "blind"),
                     "votes": d["votes"], "decided_at": d["decided_at"].isoformat(),
                     **_decision_scores(conn, dict(d))},
        "panel_size": len(a["panel"]), "i_chair": str(a["panel"][0]) == user_id,
        "outcome": a["outcome"], "reasons": restore(a["reasons"], mapping, "blind"),
    }  # fmt: skip


def panel_list(conn: Conn, user_id: str) -> list[dict[str, Any]]:
    """Appeals this person hears (IDs, groups and states only)."""
    return [
        {
            "id": r["id"],
            "cluster_id": r["cluster_id"],
            "state": r["state"],
            "due_at": r["due_at"].isoformat(),
            "outcome": r["outcome"],
        }
        for r in conn.execute(
            "SELECT id, cluster_id, state, due_at, outcome FROM appeals WHERE %s::uuid = ANY(panel) "
            "ORDER BY filed_at DESC LIMIT 100",
            (user_id,),
        ).fetchall()
    ]


def decide(
    conn: Conn, aid: str, user_id: str, body: dict[str, Any], now: dt.datetime | None = None
) -> dict[str, Any]:
    now = now or dt.datetime.now(dt.UTC)
    with audited(conn), conn.transaction():
        a = conn.execute("SELECT * FROM appeals WHERE id = %s FOR UPDATE", (aid,)).fetchone()
        if a is None or user_id not in {str(p) for p in a["panel"]}:
            raise ActionRefused(404, "not_found")
        if str(a["panel"][0]) != user_id:
            raise ActionRefused(403, "panel_chair_only")
        if conflict(conn, a["cluster_id"], user_id) is not None:
            raise ActionRefused(409, "conflict_of_interest")
        if a["state"] != "open":
            raise ActionRefused(409, "already_decided")
        outcome = body.get("outcome")
        if outcome not in OUTCOMES:
            raise ActionRefused(422, "outcome_required")
        cid = str(a["cluster_id"])
        reasons = _tagged(conn, cid, body.get("reasons"), min_chars=40)
        rev = staff_code(conn, user_id)
        d = conn.execute("SELECT * FROM decisions WHERE id = %s", (a["decision_id"],)).fetchone()
        assert d is not None
        conn.execute(
            "UPDATE appeals SET state = 'decided', outcome = %s, reasons = %s, decided_by = %s, decided_at = %s "
            "WHERE id = %s",
            (outcome, reasons, rev, now, aid),
        )
        stage = _apply(conn, dict(d), str(outcome), now)
        conn.execute("UPDATE clusters SET stage = %s WHERE id = %s", (stage, cid))
        conn.execute("UPDATE ideas SET stage = %s WHERE cluster_id = %s", (stage, cid))
        engine.stop(conn, "appeal", aid, "appeal_decision")
        outbox = "INSERT INTO outbox (event_type, aggregate_id, actor, payload) VALUES (%s, %s, %s, %s)"
        conn.execute(outbox, ("appeal.decided", aid, rev, Jsonb({"appeal_id": aid, "verified_by": rev})))
        conn.execute(outbox, ("decision.recorded", d["id"], rev, Jsonb({"decision_id": d["id"]})))
        conn.execute(outbox, ("cluster.updated", cid, rev, Jsonb({"note": f"appeal {aid} {outcome}"})))
        for m in conn.execute("SELECT idea_id FROM ideas WHERE cluster_id = %s", (cid,)).fetchall():
            conn.execute(outbox, ("idea.stage_changed", m["idea_id"], rev,
                                  Jsonb({"history": [{"event": stage, "by": rev, "note": aid}]})))  # fmt: skip
        emit(conn, "appeal.decided", {"appeal_id": aid, "cluster_id": cid, "outcome": outcome})
        conn.execute(
            "INSERT INTO audit_log (actor, action, entity, after) VALUES (%s, 'appeal.decided', %s, %s)",
            (rev, f"appeal:{aid}", Jsonb({"outcome": outcome, "decision": d["id"]})),
        )
    log.info("appeal.decided", appeal_id=aid)
    return {"appeal_id": aid, "outcome": outcome, "stage": stage}


def _apply(conn: Conn, d: dict[str, Any], outcome: str, now: dt.datetime) -> str:
    """What the outcome does to the group; returns its new stage."""
    if outcome == "upheld":
        return str(d["outcome"])
    if outcome == "re_score":
        return "ready_for_scoring"  # the next cycle opens a round; it shows the panel's direction note
    # Overturned.
    if d.get("presentation_id"):
        # After a presentation: back to the chair to decide again (picked if capacity allows, §4.12 step 4).
        conn.execute("UPDATE presentations SET state = 'held' WHERE id = %s", (d["presentation_id"],))
        engine.start(conn, "presentation", d["presentation_id"], "final_decision", now=now)
        return "presenting"
    # A preliminary decision: straight to an invitation to present, above the line.
    from committee.decide import invite

    pid = invite(conn, d["cluster_id"], d["round_id"], d["cycle_id"], now)
    emit(
        conn,
        "shortlist.invited",
        {"cluster_id": d["cluster_id"], "round_id": d["round_id"], "presentation_id": pid},
    )
    return "shortlisted"


def direction_for(conn: Conn, cluster_id: str) -> str | None:
    """The latest re-score direction note for a group (tagged), for the next round's view."""
    row = conn.execute(
        "SELECT reasons FROM appeals WHERE cluster_id = %s AND outcome = 're_score' ORDER BY decided_at DESC LIMIT 1",
        (cluster_id,),
    ).fetchone()
    return str(row["reasons"]) if row and row["reasons"] else None


# ---- the colleagues' side ------------------------------------------------------------------------------------------


def mine(conn: Conn, user_id: str, now: dt.datetime | None = None) -> list[dict[str, Any]]:
    """Committee decisions on groups this person contributed to, with whether they can appeal and any appeal."""
    now = now or dt.datetime.now(dt.UTC)
    codes = sorted(_codes(conn, user_id))
    if not codes:
        return []
    rows = conn.execute(
        "SELECT d.id, d.cluster_id, d.outcome, d.reason_code, d.appeal_window_closes, d.decided_at, "
        "a.id AS appeal_id, a.state, a.outcome AS appeal_outcome, c.title "
        "FROM decisions d JOIN clusters c ON c.id = d.cluster_id LEFT JOIN appeals a ON a.decision_id = d.id "
        "WHERE d.outcome IN ('parked', 'declined') AND d.cluster_id IN ("
        "SELECT cluster_id FROM ideas WHERE contributor_code = ANY(%s) AND cluster_id IS NOT NULL UNION "
        "SELECT cluster_id FROM idea_links WHERE contributor_code = ANY(%s) AND link_type IN ('originator', 'joiner') "
        "AND cluster_id IS NOT NULL) ORDER BY d.decided_at DESC LIMIT 50",
        (codes, codes),
    ).fetchall()
    out = []
    for r in rows:
        scope = conn.execute("SELECT tag_scope FROM clusters WHERE id = %s", (r["cluster_id"],)).fetchone()
        mapping = vault.mapping(conn, scope["tag_scope"]) if scope and scope["tag_scope"] else {}
        open_ = (
            r["appeal_id"] is None
            and r["appeal_window_closes"] is not None
            and now <= r["appeal_window_closes"]
            and appealable(conn, r["cluster_id"], r["outcome"], r["id"])
        )
        out.append({"decision_id": r["id"], "cluster_id": r["cluster_id"],
                    "name": restore(r["title"], mapping, "neutral"), "outcome": r["outcome"],
                    "reason_code": r["reason_code"], "decided_at": r["decided_at"].isoformat(),
                    "window_closes": r["appeal_window_closes"].isoformat() if r["appeal_window_closes"] else None,
                    "can_appeal": open_, "appeal_id": r["appeal_id"], "appeal_state": r["state"],
                    "appeal_outcome": r["appeal_outcome"]})  # fmt: skip
    return out
