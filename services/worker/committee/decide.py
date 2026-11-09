"""Present and decide (§4.7), minimal version (DEC-057, BLD-219).

1. **Invitation** when the chair shortlists: a presentation with slot options (from the cycle, or the next working
   days at 15:00 IST), a 3-working-day reply window and a `pitch-prep` outline (tagged under the cluster's scope).
2. **Accept** (a contributor of the cluster): up to 3 presenters from the cluster's contributors and a slot. The
   outline is theirs to edit. Deck upload is "Coming soon" (presenters bring the deck to the session).
3. **Session** (the chair): mark it held and record the Q&A; blind mode ends here. "Not presented" parks the
   cluster with `NOT_PRESENTED` and its own message (moving to the next session automatically is "Coming soon").
   Members with a conflict on the cluster (§3.1, checked live) see neither the group nor the sheet and take no
   part; the counts below are of the members without one.
4. **Sealed assessments** within 2 working days: the six dimensions, a vote, the preferred route, up to three
   strengths and concerns, conditions, unanswered questions, willingness to sponsor. Nobody sees another's, and
   none are taken once the sheet is collated.
5. **Collation** (the chair, when everyone has assessed or at the deadline with quorum): the rules count votes,
   take medians and spreads, the change from the preliminary review, route preferences and divergence flags; the
   `collation` agent groups strengths and concerns into themes with counts and merges conditions. Precedents
   (plan P4) and the core brief's route are "Coming soon".
6. **Decide** (the chair): accept needs a simple majority of the members who assessed and a named sponsor (the
   chair's casting vote breaks a tie); moving past the cycle's Garage slots needs a 50-character reason; park and
   decline need a reason code, and `reason-writer` drafts the plain-language reason and "what would change this
   decision" for the chair to edit. The decision file holds counts, themes and reasons, never who voted what.
7. **On acceptance**: stage `picked`, a working group (`WG-`) with the presenters, the originators and the
   sponsor, and the delivery handover (§4.8: build, or procurement to buy or partner). Induction into the 1% Club, protected time and handover are "Coming soon" here (the Ones module and
   handover own them). Park and decline start the 15-working-day appeal window.
"""

from __future__ import annotations

import datetime as dt
import statistics
from typing import Any
from zoneinfo import ZoneInfo

from psycopg.types.json import Jsonb

from committee.rounds import _cluster_card, _tagged, conflict, is_chair, scorecard
from comms.route import emit
from core.db import Conn
from core.logging import get_logger
from pii import vault
from pii.restore import restore
from review.service import ActionRefused, audited, staff_code
from sla import engine
from sla.calendar import add_working_days

log = get_logger("committee.decide")
IST = ZoneInfo("Asia/Kolkata")
VOTES = ("accept", "accept_with_conditions", "park", "decline")
ROUTES = ("reuse", "build", "buy", "partner")
PARK = {"NOT_FEASIBLE_NOW", "INSUFFICIENT_EVIDENCE", "CAPACITY", "NOT_PRESENTED"}
DECLINE = {"LOW_VALUE", "NOT_FEASIBLE_NOW", "REG_CONFLICT", "OUT_OF_SCOPE"}
OVERRIDE_MIN = 50
DELIVERY_TRACK = {"build": "build", "reuse": "build", "buy": "procurement", "partner": "procurement"}


def _scope(conn: Conn, cluster_id: str) -> str:
    row = conn.execute("SELECT tag_scope FROM clusters WHERE id = %s", (cluster_id,)).fetchone()
    return str((row or {}).get("tag_scope") or cluster_id)


def _codes_of(conn: Conn, user_id: str) -> set[str]:
    return {
        r["contributor_code"]
        for r in conn.execute(
            "SELECT contributor_code FROM contributor_map WHERE user_id = %s", (user_id,)
        ).fetchall()
    }


def _cluster_codes(conn: Conn, cluster_id: str) -> set[str]:
    rows = conn.execute(
        "SELECT contributor_code FROM ideas WHERE cluster_id = %s UNION SELECT contributor_code FROM idea_links "
        "WHERE cluster_id = %s AND link_type IN ('originator', 'joiner')",
        (cluster_id, cluster_id),
    ).fetchall()
    return {r["contributor_code"] for r in rows}


def _roster(conn: Conn) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT g.user_id FROM role_grants g JOIN users u ON u.id = g.user_id "
        "WHERE g.role IN ('core_committee', 'core_chair') AND g.valid_to IS NULL AND u.active ORDER BY 1"
    ).fetchall()
    return [str(r["user_id"]) for r in rows]


def _voting(conn: Conn, cluster_id: str) -> list[str]:
    """Core committee members without a conflict on this cluster: the ones who assess and count."""
    return [m for m in _roster(conn) if conflict(conn, cluster_id, m) is None]


# ---- 1. invitation ----------------------------------------------------------------------------------------------


def slot_options(now: dt.datetime, start_wd: int = 5, count: int = 3) -> list[dt.datetime]:
    """Default slots: 15:00 IST on the working days after `start_wd` working days (the cycle can set its own)."""
    out: list[dt.datetime] = []
    day = add_working_days(now, start_wd)
    while len(out) < count:
        local = day.astimezone(IST).replace(hour=15, minute=0, second=0, microsecond=0)
        out.append(local.astimezone(dt.UTC))
        day = add_working_days(day, 1)
    return out


def invite(conn: Conn, cluster_id: str, round_id: str, cycle_id: str | None, now: dt.datetime) -> str:
    n = conn.execute("SELECT next_number('PRS', %s) AS n", (str(now.year),)).fetchone()
    assert n is not None
    pid = f"PRS-{now.year}-{int(n['n']):04d}"
    due = add_working_days(now, 3)
    conn.execute(
        "INSERT INTO presentations (id, cluster_id, round_id, cycle_id, slot_options, reply_due) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (pid, cluster_id, round_id, cycle_id, slot_options(now), due),
    )
    engine.start(conn, "presentation", pid, "invitation_reply", now=now)
    from jobs.runner import enqueue

    # After commit, so the model call never holds the shortlist's transaction (BLD-221).
    enqueue(conn, "presentation.outline", {"presentation_id": pid}, dedupe_key=f"outline:{pid}")
    return pid


def write_outline(conn: Conn, pid: str) -> bool:
    """The `presentation.outline` job: a draft outline while the invitation is open and nobody has written one."""
    row = conn.execute(
        "SELECT cluster_id, state, outline FROM presentations WHERE id = %s", (pid,)
    ).fetchone()
    if row is None or row["state"] != "invited" or row["outline"]:
        return False
    with conn.transaction():
        return _outline(conn, pid, str(row["cluster_id"]))


def _outline(conn: Conn, pid: str, cluster_id: str) -> bool:
    """`pitch-prep` drafts an outline for the 8-slide deck from the cluster; the presenters own and edit it."""
    from gateway import AgentFailed, run_agent

    card = _cluster_card(conn, cluster_id, "real")
    try:
        out = run_agent(
            "pitch-prep",
            {"cluster": {k: card[k] for k in ("name", "summary", "lobs", "scope", "ideas")}},
            _scope(conn, cluster_id),
            conn=conn,
        )
    except AgentFailed as exc:
        log.warning("presentation.outline_unavailable", presentation_id=pid, error_code=exc.code)
        return False
    conn.execute(
        "UPDATE presentations SET outline = %s, outline_by = %s WHERE id = %s AND outline IS NULL",
        (Jsonb(out.data), f"pitch-prep/{out.version}", pid),
    )
    return True


# ---- views -------------------------------------------------------------------------------------------------------


def _pres(conn: Conn, pid: str, lock: bool = False) -> dict[str, Any]:
    sql = (
        "SELECT * FROM presentations WHERE id = %s FOR UPDATE"
        if lock
        else "SELECT * FROM presentations WHERE id = %s"
    )
    row = conn.execute(sql, (pid,)).fetchone()
    if row is None:
        raise ActionRefused(404, "not_found")
    return dict(row)


def contributor_view(conn: Conn, pid: str, user_id: str) -> dict[str, Any] | None:
    """What a contributor of the cluster sees: the invitation, the slots, the presenters (as codes they chose)
    and the outline. The outline is drawn from every idea in the group, so it comes back in neutral mode: no
    contributor sees another's names or values (non-negotiable 7, BLD-221)."""
    try:
        p = _pres(conn, pid)
    except ActionRefused:
        return None
    if not (_codes_of(conn, user_id) & _cluster_codes(conn, p["cluster_id"])):
        return None
    mapping = vault.mapping(conn, _scope(conn, p["cluster_id"]))
    title = conn.execute("SELECT title FROM clusters WHERE id = %s", (p["cluster_id"],)).fetchone()
    mine = sorted(_codes_of(conn, user_id) & _cluster_codes(conn, p["cluster_id"]))
    return {
        "id": pid, "cluster_id": p["cluster_id"], "name": restore((title or {}).get("title"), mapping, "neutral"),
        "state": p["state"], "reply_due": p["reply_due"].isoformat() if p["reply_due"] else None,
        "slot_options": [s.isoformat() for s in p["slot_options"] or []],
        "slot_at": p["slot_at"].isoformat() if p["slot_at"] else None,
        "presenters": list(p["presenters"] or []), "my_codes": mine,
        "contributors": sorted(_cluster_codes(conn, p["cluster_id"])),
        "outline": restore(p["outline"], mapping, "neutral"), "outline_by": p["outline_by"],
    }  # fmt: skip


def committee_view(conn: Conn, pid: str, user_id: str) -> dict[str, Any] | None:
    """The core committee's view: the cluster (blind until the session, real after), the state, the user's own
    sealed assessment, and the decision sheet once collated. A member with a conflict sees only that."""
    if user_id not in _roster(conn) and not is_chair(conn, user_id):
        return None
    try:
        p = _pres(conn, pid)
    except ActionRefused:
        return None
    why = conflict(conn, p["cluster_id"], user_id)
    if why is not None:
        return {"id": pid, "cluster_id": p["cluster_id"], "state": p["state"], "conflict": why,
                "chair": is_chair(conn, user_id)}  # fmt: skip
    held = p["state"] in ("held", "decided")
    mapping = vault.mapping(conn, _scope(conn, p["cluster_id"]))
    mine = conn.execute(
        "SELECT * FROM assessments WHERE presentation_id = %s AND member_id = %s", (pid, user_id)
    ).fetchone()
    count = conn.execute(
        "SELECT count(*) AS n FROM assessments WHERE presentation_id = %s", (pid,)
    ).fetchone()
    sheet = conn.execute("SELECT * FROM decision_sheets WHERE presentation_id = %s", (pid,)).fetchone()
    decision = conn.execute(
        "SELECT id, outcome, route, reason_code, votes, decided_at FROM decisions WHERE presentation_id = %s "
        "ORDER BY decided_at DESC LIMIT 1",  # an overturned appeal sends it back to the chair: the latest counts
        (pid,),
    ).fetchone()
    sc = scorecard()
    return {
        "id": pid, "cluster_id": p["cluster_id"], "state": p["state"],
        "slot_at": p["slot_at"].isoformat() if p["slot_at"] else None,
        "presenters": len(p["presenters"] or []),
        "cluster": _cluster_card(conn, p["cluster_id"], "real" if held else "blind"),
        "qna_notes": restore(p["qna_notes"], mapping, "real") if held else None,
        "assessments_due": p["assessments_due"].isoformat() if p["assessments_due"] else None,
        "assessed": int(count["n"] if count else 0), "members": len(_voting(conn, p["cluster_id"])), "conflict": None,
        "my_assessment": restore({k: mine[k] for k in ("dimension_scores", "vote", "route_pref", "strengths",
                                  "concerns", "conditions", "open_questions", "will_sponsor")}, mapping, "real")
        if mine else None,
        "dimensions": [{"name": n, "label": d.get("label", n), "weight": d["weight"], "anchors": d.get("anchors", {})}
                       for n, d in sc["dimensions"].items()],
        "sheet": restore({k: sheet[k] for k in ("tallies", "medians", "spread", "change_from_prelim", "route_prefs",
                          "themes", "conditions", "divergence_flags", "sponsors_willing")}, mapping, "real")
        | {"final_score": float(sheet["final_score"]) if sheet["final_score"] is not None else None}
        if sheet else None,
        "decision": dict(decision) | {"decided_at": decision["decided_at"].isoformat()} if decision else None,
        "chair": is_chair(conn, user_id),
        "sponsor_options": _sponsor_options(conn, pid, p["cluster_id"], collated=sheet is not None) if is_chair(conn, user_id) else [],
    }  # fmt: skip


def _sponsor_options(conn: Conn, pid: str, cluster_id: str, *, collated: bool) -> list[dict[str, Any]]:
    """For the chair: core committee members (names are fine inside the committee). Who offered to sponsor is
    part of a sealed assessment, so it shows only once the sheet is collated."""
    willing = (
        {
            str(r["member_id"])
            for r in conn.execute(
                "SELECT member_id FROM assessments WHERE presentation_id = %s AND will_sponsor", (pid,)
            ).fetchall()
        }
        if collated
        else set()
    )
    rows = conn.execute(
        "SELECT id, name FROM users WHERE id = ANY(%s::uuid[]) ORDER BY name", (_voting(conn, cluster_id),)
    ).fetchall()
    out = [{"id": str(r["id"]), "name": r["name"], "willing": str(r["id"]) in willing} for r in rows]
    return sorted(out, key=lambda o: (not o["willing"], o["name"]))


# ---- actions -----------------------------------------------------------------------------------------------------


def contributor_act(
    conn: Conn, pid: str, user_id: str, body: dict[str, Any], now: dt.datetime | None = None
) -> dict[str, Any]:
    now = now or dt.datetime.now(dt.UTC)
    with audited(conn), conn.transaction():
        p = _pres(conn, pid, lock=True)
        mine = _codes_of(conn, user_id) & _cluster_codes(conn, p["cluster_id"])
        if not mine:
            raise ActionRefused(404, "not_found")
        action = body.get("action")
        if action == "accept":
            if p["state"] != "invited":
                raise ActionRefused(409, "not_open")
            presenters = body.get("presenters") or []
            allowed = _cluster_codes(conn, p["cluster_id"])
            if (
                not isinstance(presenters, list)
                or not 1 <= len(presenters) <= 3
                or not set(presenters) <= allowed
            ):
                raise ActionRefused(422, "presenters_from_the_cluster_1_to_3")
            slot = str(body.get("slot") or "")
            options = {s.isoformat(): s for s in p["slot_options"] or []}
            if slot not in options:
                raise ActionRefused(422, "slot_from_the_options")
            conn.execute(
                "UPDATE presentations SET state = 'scheduled', presenters = %s, slot_at = %s, accepted_by = %s, "
                "accepted_at = %s WHERE id = %s",
                (sorted(set(presenters)), options[slot], sorted(mine)[0], now, pid),
            )
            conn.execute("UPDATE clusters SET stage = 'presenting' WHERE id = %s", (p["cluster_id"],))
            conn.execute("UPDATE ideas SET stage = 'presenting' WHERE cluster_id = %s", (p["cluster_id"],))
            engine.stop(conn, "presentation", pid, "invitation_reply")
            emit(conn, "presentation.confirmed", {"presentation_id": pid, "cluster_id": p["cluster_id"]})
            conn.execute(
                "INSERT INTO audit_log (actor, action, entity) VALUES (%s, 'presentation.accepted', %s)",
                (sorted(mine)[0], f"presentation:{pid}"),
            )
            return {"state": "scheduled"}
        if action == "save_outline":
            if p["state"] not in ("invited", "scheduled"):
                raise ActionRefused(409, "not_open")
            slides = body.get("slides")
            if not isinstance(slides, list) or not 1 <= len(slides) <= 8:
                raise ActionRefused(422, "one_to_eight_slides")
            clean = []
            for s in slides:
                if not isinstance(s, dict):
                    raise ActionRefused(422, "bad_slide")
                clean.append({"title": _tagged(conn, p["cluster_id"], s.get("title"), min_chars=3),
                              "points": [_tagged(conn, p["cluster_id"], x, min_chars=2) for x in (s.get("points") or [])[:6]]})  # fmt: skip
            conn.execute(
                "UPDATE presentations SET outline = %s, outline_by = %s WHERE id = %s",
                (Jsonb({"slides": clean}), sorted(mine)[0], pid),
            )
            return {"saved": True}
        raise ActionRefused(400, "unknown_action")


def committee_act(
    conn: Conn, pid: str, user_id: str, body: dict[str, Any], now: dt.datetime | None = None
) -> dict[str, Any]:
    now = now or dt.datetime.now(dt.UTC)
    action = body.get("action")
    with audited(conn), conn.transaction():
        p = _pres(conn, pid, lock=True)
        why = conflict(conn, p["cluster_id"], user_id)
        if why == "own_idea":
            raise ActionRefused(
                409, "own_idea", (f"user:{user_id}", "review.own_idea_refused", f"presentation:{pid}", {})
            )
        if why is not None:
            raise ActionRefused(
                409, "conflict_of_interest"
            )  # a recusal carries into this stage (§4.7 step 3)
        chair = is_chair(conn, user_id)
        if action == "assess":
            return _assess(conn, p, user_id, body, now)
        if not chair:
            raise ActionRefused(403, "chair_only")
        rev = staff_code(conn, user_id)
        if action == "held":
            if p["state"] != "scheduled":
                raise ActionRefused(409, "not_scheduled")
            notes = _tagged(conn, p["cluster_id"], body.get("qna_notes"))
            due = add_working_days(now, 2)
            conn.execute(
                "UPDATE presentations SET state = 'held', held_at = %s, qna_notes = %s, assessments_due = %s "
                "WHERE id = %s",
                (now, notes, due, pid),
            )
            engine.start(conn, "presentation", pid, "individual_assessment", now=now)
            engine.start(conn, "presentation", pid, "final_decision", now=now)
            return {"state": "held"}
        if action == "not_presented":
            if p["state"] not in ("invited", "scheduled"):
                raise ActionRefused(409, "not_open")
            return _record(conn, p, rev, user_id, {"outcome": "parked", "reason_code": "NOT_PRESENTED", "votes": {}}, now)  # fmt: skip
        if action == "collate":
            return _collate(conn, p, now)
        if action == "draft_reasons":
            return _draft_reasons(conn, p, body)
        if action == "decide":
            return _decide(conn, p, rev, user_id, body, now)
        raise ActionRefused(400, "unknown_action")


def _assess(
    conn: Conn, p: dict[str, Any], user_id: str, body: dict[str, Any], now: dt.datetime
) -> dict[str, Any]:
    if p["state"] != "held":
        raise ActionRefused(409, "not_held")
    if user_id not in _roster(conn):
        raise ActionRefused(403, "committee_only")
    if conn.execute("SELECT 1 FROM decision_sheets WHERE presentation_id = %s", (p["id"],)).fetchone():
        raise ActionRefused(409, "already_collated")  # the sheet and the decision use the same assessments
    if conn.execute(
        "SELECT 1 FROM assessments WHERE presentation_id = %s AND member_id = %s", (p["id"], user_id)
    ).fetchone():
        raise ActionRefused(409, "already_assessed")
    sc = scorecard()
    scores = body.get("scores") or {}
    if (
        not isinstance(scores, dict)
        or set(scores) != set(sc["dimensions"])
        or not all(isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 5 for v in scores.values())
    ):
        raise ActionRefused(422, "every_dimension_1_to_5")
    vote = body.get("vote")
    if vote not in VOTES:
        raise ActionRefused(422, "vote_required")
    route = body.get("route_pref")
    if route is not None and route not in ROUTES:
        raise ActionRefused(422, "bad_route")
    cid = p["cluster_id"]

    def items(key: str, most: int) -> list[str]:
        raw = body.get(key) or []
        if not isinstance(raw, list) or len(raw) > most:
            raise ActionRefused(422, f"{key}_at_most_{most}")
        return [t for t in (_tagged(conn, cid, x) for x in raw) if t]

    conditions = items("conditions", 5)
    if vote == "accept_with_conditions" and not conditions:
        raise ActionRefused(422, "conditions_required")
    conn.execute(
        "INSERT INTO assessments (presentation_id, cluster_id, member_id, dimension_scores, vote, route_pref, "
        "strengths, concerns, conditions, open_questions, will_sponsor, submitted_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (p["id"], cid, user_id, Jsonb(scores), vote, route, Jsonb(items("strengths", 3)), Jsonb(items("concerns", 3)),
         Jsonb(conditions), _tagged(conn, cid, body.get("open_questions")), bool(body.get("will_sponsor")), now),
    )  # fmt: skip
    log.info("assessment.sealed", presentation_id=p["id"])
    return {"assessed": True}


def _tally(conn: Conn, p: dict[str, Any]) -> dict[str, Any]:
    rows = [
        dict(r)
        # Ordered by a hash, not by submission, so "Member n" in the collation says nothing about who was first.
        for r in conn.execute(
            "SELECT * FROM assessments WHERE presentation_id = %s ORDER BY md5(member_id::text || presentation_id)",
            (p["id"],),
        ).fetchall()
    ]
    sc = scorecard()
    tallies = {v: sum(1 for r in rows if r["vote"] == v) for v in VOTES}
    by: dict[str, list[int]] = (
        {d: [int(r["dimension_scores"][d]) for r in rows] for d in sc["dimensions"]} if rows else {}
    )
    medians = {d: float(statistics.median(v)) for d, v in by.items()}
    spread = {d: max(v) - min(v) for d, v in by.items()}
    prelim = conn.execute(
        "SELECT medians, final_score FROM scoring_rounds WHERE id = %s", (p["round_id"],)
    ).fetchone()
    change = {
        d: round(medians[d] - float((prelim or {}).get("medians", {}).get(d, medians[d])), 1) for d in medians
    }
    routes = {r: sum(1 for x in rows if x["route_pref"] == r) for r in ROUTES}
    n = len(rows)
    flags = []
    if n and max(tallies.values()) * 2 <= n:
        flags.append("votes_split")  # no option above 50%
    if any(s >= 2 for s in spread.values()):
        flags.append("score_range_2_or_more")
    total = sum(float(d["weight"]) * medians.get(name, 0) for name, d in sc["dimensions"].items())
    mult = conn.execute(
        "SELECT confidence_multiplier FROM scoring_rounds WHERE id = %s", (p["round_id"],)
    ).fetchone()
    final = round(total / 5 * float((mult or {}).get("confidence_multiplier") or 1), 1) if rows else None
    return {"rows": rows, "tallies": tallies, "medians": medians, "spread": spread, "change": change,
            "routes": routes, "flags": flags, "final": final, "sponsors": sum(1 for r in rows if r["will_sponsor"])}  # fmt: skip


def _collate(conn: Conn, p: dict[str, Any], now: dt.datetime) -> dict[str, Any]:
    from gateway import AgentFailed, run_agent

    if p["state"] != "held":
        raise ActionRefused(409, "not_held")
    if conn.execute("SELECT 1 FROM decision_sheets WHERE presentation_id = %s", (p["id"],)).fetchone():
        raise ActionRefused(409, "already_collated")
    t = _tally(conn, p)
    members = len(_voting(conn, p["cluster_id"]))
    everyone = len(t["rows"]) >= members
    quorum = len(t["rows"]) >= 0.6 * members
    late = p["assessments_due"] is not None and now >= p["assessments_due"]
    if not t["rows"] or not (everyone or (late and quorum)):
        raise ActionRefused(409, "not_ready_to_collate")
    cid = p["cluster_id"]
    scope = _scope(conn, cid)
    mapping = vault.mapping(conn, scope)
    themes = conditions = None
    by = None
    try:
        out = run_agent(
            "collation",
            {
                "assessments": [
                    {
                        "member": f"Member {i}",
                        "vote": r["vote"],
                        "route_pref": r["route_pref"],
                        "strengths": restore(r["strengths"], mapping, "real"),
                        "concerns": restore(r["concerns"], mapping, "real"),
                        "conditions": restore(r["conditions"], mapping, "real"),
                    }
                    for i, r in enumerate(t["rows"], start=1)
                ]
            },
            scope,
            conn=conn,
        )
        themes = {"strengths": out.data["strengths"], "concerns": out.data["concerns"]}
        conditions = out.data["conditions"]
        by = f"collation/{out.version}"
    except AgentFailed as exc:
        log.warning("collation.unavailable", presentation_id=p["id"], error_code=exc.code)
    conn.execute(
        "INSERT INTO decision_sheets (presentation_id, cluster_id, cycle_id, tallies, medians, spread, "
        "change_from_prelim, route_prefs, themes, conditions, divergence_flags, sponsors_willing, final_score, "
        "generated_by, generated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
        "ON CONFLICT (presentation_id) DO UPDATE SET tallies = EXCLUDED.tallies, medians = EXCLUDED.medians, "
        "spread = EXCLUDED.spread, change_from_prelim = EXCLUDED.change_from_prelim, route_prefs = EXCLUDED.route_prefs, "
        "themes = EXCLUDED.themes, conditions = EXCLUDED.conditions, divergence_flags = EXCLUDED.divergence_flags, "
        "sponsors_willing = EXCLUDED.sponsors_willing, final_score = EXCLUDED.final_score, "
        "generated_by = EXCLUDED.generated_by, generated_at = EXCLUDED.generated_at",
        (p["id"], cid, p["cycle_id"], Jsonb(t["tallies"]), Jsonb(t["medians"]), Jsonb(t["spread"]), Jsonb(t["change"]),
         Jsonb(t["routes"]), Jsonb(themes) if themes else None, Jsonb(conditions) if conditions is not None else None,
         t["flags"], t["sponsors"], t["final"], by, now),
    )  # fmt: skip
    return {"collated": True, "themes": themes is not None}


def _draft_reasons(conn: Conn, p: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    """`reason-writer` drafts the plain-language reason and "what would change this decision" from the collated
    themes and the reason code; the chair edits and approves them in the decide step (§4.7 step 7)."""
    from core.config import get_settings
    from gateway import AgentFailed, run_agent
    from rules import load_rule

    outcome = body.get("outcome")
    code = body.get("reason_code")
    if outcome not in ("parked", "declined", "picked"):
        raise ActionRefused(400, "bad_outcome")
    sheet = conn.execute(
        "SELECT themes, conditions FROM decision_sheets WHERE presentation_id = %s", (p["id"],)
    ).fetchone()
    if sheet is None:
        raise ActionRefused(409, "collate_first")
    codes = {
        c["code"]: c["plain_words"]
        for c in load_rule(get_settings().company_repo_path, "reason-codes").data["codes"]
    }
    scope = _scope(conn, p["cluster_id"])
    mapping = vault.mapping(conn, scope)
    try:
        out = run_agent(
            "reason-writer",
            {
                "outcome": {"outcome": outcome, "reason_code": code, "reason_words": codes.get(str(code))},
                "themes": restore(sheet["themes"] or {}, mapping, "real"),
                "conditions": restore(sheet["conditions"] or [], mapping, "real"),
            },
            scope,
            conn=conn,
        )
    except AgentFailed:
        raise ActionRefused(503, "assistant_unavailable") from None
    return {"draft": restore(out.data, mapping, "real")}


def _decide(
    conn: Conn, p: dict[str, Any], rev: str, user_id: str, body: dict[str, Any], now: dt.datetime
) -> dict[str, Any]:
    if p["state"] != "held":
        raise ActionRefused(409, "not_held")
    sheet = conn.execute("SELECT * FROM decision_sheets WHERE presentation_id = %s", (p["id"],)).fetchone()
    if sheet is None:
        raise ActionRefused(409, "collate_first")
    outcome = body.get("outcome")
    t = _tally(conn, p)
    n = len(t["rows"])
    yes = t["tallies"]["accept"] + t["tallies"]["accept_with_conditions"]
    cid = p["cluster_id"]
    decision: dict[str, Any] = {"outcome": outcome, "votes": t["tallies"]}
    if outcome == "picked":
        casting = bool(body.get("casting_vote"))
        if yes * 2 < n or (yes * 2 == n and not casting):
            raise ActionRefused(409, "no_majority")  # a tie needs the chair's casting vote
        route = body.get("route")
        if route not in ROUTES:
            raise ActionRefused(422, "route_required")
        sponsor = str(body.get("sponsor_id") or "")
        ok = conn.execute("SELECT 1 FROM users WHERE id::text = %s AND active", (sponsor,)).fetchone()
        if not ok:
            raise ActionRefused(422, "sponsor_required")
        cap = conn.execute(
            "SELECT garage_slots FROM capacity WHERE cycle_id = %s", (p["cycle_id"],)
        ).fetchone()
        used = conn.execute(
            "SELECT count(*) AS n FROM decisions WHERE cycle_id = %s AND outcome = 'picked'", (p["cycle_id"],)
        ).fetchone()
        override = None
        if cap and cap["garage_slots"] is not None and used and int(used["n"]) >= int(cap["garage_slots"]):
            override = _tagged(conn, cid, body.get("override_reason"), min_chars=OVERRIDE_MIN)
        decision |= {"route": route, "sponsor_id": sponsor, "casting_vote": casting and yes * 2 == n,
                     "override_reason": override,
                     "conditions": [c for c in (_tagged(conn, cid, x) for x in (body.get("conditions") or [])[:10]) if c],
                     "plain_reason": _tagged(conn, cid, body.get("plain_reason"), min_chars=30)}  # fmt: skip
    elif outcome in ("parked", "declined"):
        code = body.get("reason_code")
        if code not in (PARK if outcome == "parked" else DECLINE):
            raise ActionRefused(422, "reason_code_required")
        decision |= {"reason_code": code,
                     "plain_reason": _tagged(conn, cid, body.get("plain_reason"), min_chars=30),
                     "what_would_change": _tagged(conn, cid, body.get("what_would_change"), min_chars=20)}  # fmt: skip
    else:
        raise ActionRefused(400, "bad_outcome")
    return _record(conn, p, rev, user_id, decision, now)


def _record(
    conn: Conn, p: dict[str, Any], rev: str, user_id: str, d: dict[str, Any], now: dt.datetime
) -> dict[str, Any]:
    cid = p["cluster_id"]
    n = conn.execute("SELECT next_number('DEC', %s) AS n", (str(now.year),)).fetchone()
    assert n is not None
    did = f"DEC-{now.year}-{int(n['n']):04d}"
    present = sum((d.get("votes") or {}).values())
    conflicted = len(_roster(conn)) - len(_voting(conn, cid))
    from committee.appeals import WINDOW_WD, appealable

    # The appeal window opens only for a decision that can be appealed: a decline, or a second park (§4.12).
    window = add_working_days(now, WINDOW_WD) if appealable(conn, cid, d["outcome"]) else None
    conn.execute(
        "INSERT INTO decisions (id, cluster_id, presentation_id, cycle_id, outcome, route, reason_code, plain_reason, "
        "what_would_change, conditions, votes, members_present, recused, sponsor_id, casting_vote, override_reason, "
        "decided_by, decided_at, appeal_window_closes) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (did, cid, p["id"], p["cycle_id"], d["outcome"], d.get("route"), d.get("reason_code"), d.get("plain_reason"),
         d.get("what_would_change"), Jsonb(d.get("conditions") or []), Jsonb(d.get("votes") or {}), present,
         conflicted, d.get("sponsor_id") or None, bool(d.get("casting_vote")),
         d.get("override_reason"), rev, now, window),
    )  # fmt: skip
    conn.execute("UPDATE presentations SET state = 'decided' WHERE id = %s", (p["id"],))
    conn.execute(
        "UPDATE clusters SET stage = %s, reason_code = %s WHERE id = %s",
        (d["outcome"], d.get("reason_code"), cid),
    )
    conn.execute("UPDATE ideas SET stage = %s WHERE cluster_id = %s", (d["outcome"], cid))
    engine.stop(conn, "presentation", p["id"], "final_decision")
    engine.stop(conn, "presentation", p["id"], "individual_assessment")
    engine.stop(conn, "presentation", p["id"], "invitation_reply")
    wg = None
    if d["outcome"] == "picked":
        wg = _working_group(conn, p, did, d.get("sponsor_id"), user_id, now)
        from delivery.service import start_from_pick

        # The handover opens in the same transaction (§4.8); the owner can change the track in the pack.
        start_from_pick(conn, "cluster", cid, DELIVERY_TRACK.get(str(d.get("route")), "build"))
    elif window:
        engine.start(conn, "decision", did, "appeal_window", now=now)
    outbox = "INSERT INTO outbox (event_type, aggregate_id, actor, payload) VALUES (%s, %s, %s, %s)"
    conn.execute(outbox, ("decision.recorded", did, rev, Jsonb({"decision_id": did, "verified_by": rev})))
    conn.execute(outbox, ("cluster.updated", cid, rev, Jsonb({"note": f"{d['outcome']} {did}"})))
    for m in conn.execute("SELECT idea_id FROM ideas WHERE cluster_id = %s", (cid,)).fetchall():
        conn.execute(outbox, ("idea.stage_changed", m["idea_id"], rev,
                              Jsonb({"history": [{"event": d["outcome"], "by": rev, "note": did}]})))  # fmt: skip
    event = (
        "decision.accepted"
        if d["outcome"] == "picked"
        else "decision.not_presented"
        if d.get("reason_code") == "NOT_PRESENTED"
        else "decision.not_accepted"
    )
    emit(conn, event, {"cluster_id": cid, "decision_id": did})
    conn.execute(
        "INSERT INTO audit_log (actor, action, entity, after) VALUES (%s, 'decision.recorded', %s, %s)",
        (rev, f"decision:{did}", Jsonb({"outcome": d["outcome"], "reason_code": d.get("reason_code"),
                                         "override": d.get("override_reason") is not None, "working_group": wg})),
    )  # fmt: skip
    log.info("decision.recorded", decision_id=did, cluster_id=cid)
    return {"decision_id": did, "outcome": d["outcome"], "working_group": wg}


def _working_group(
    conn: Conn, p: dict[str, Any], did: str, sponsor: str | None, chair: str, now: dt.datetime
) -> str:
    """On acceptance (§4.7 step 8): the presenters and originators join the cluster's working group with the
    sponsor; each gets a `working_group` role grant scoped to the group."""
    n = conn.execute("SELECT next_number('WG', '') AS n").fetchone()
    assert n is not None
    wg = f"WG-{int(n['n']):04d}"
    originators = {
        r["contributor_code"]
        for r in conn.execute(
            "SELECT contributor_code FROM ideas WHERE cluster_id = %s UNION SELECT contributor_code FROM idea_links "
            "WHERE cluster_id = %s AND link_type = 'originator'",
            (p["cluster_id"], p["cluster_id"]),
        ).fetchall()
    }
    presenters = set(p["presenters"] or [])
    members = [{"contributor_code": c, "role": "presenter" if c in presenters else "originator",
                "protected_hours": None, "manager_ack_at": None} for c in sorted(originators | presenters)]  # fmt: skip
    conn.execute(
        "INSERT INTO working_groups (id, cluster_id, decision_id, sponsor_id, members, formed_at) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (wg, p["cluster_id"], did, sponsor, Jsonb(members), now),
    )
    for m in members:
        conn.execute(
            "INSERT INTO role_grants (user_id, role, scope_id, granted_by) SELECT user_id, 'working_group', %s, %s "
            "FROM contributor_map WHERE contributor_code = %s ON CONFLICT DO NOTHING",
            (wg, chair, m["contributor_code"]),
        )
    if sponsor:
        conn.execute(
            "INSERT INTO role_grants (user_id, role, scope_id, granted_by) VALUES (%s, 'sponsor', %s, %s) "
            "ON CONFLICT DO NOTHING",
            (sponsor, p["cluster_id"], chair),
        )
    return wg
