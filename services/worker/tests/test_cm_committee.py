"""The committee flow (§4.5–§4.7), host-side against a test database: qualify gates and the impact form; a
cycle with a blind round, conflict flags, sealed scores, reveal, revise and the shortlist; the invitation, the
session, sealed assessments, collation, reasons and the decision; the working group. Sealed tables are out of the
web app's reach. Built on the clustering fixtures so the cluster is real."""

from __future__ import annotations

import json
from typing import Any

import pytest

from cluster import batch, proposals
from committee import decide, qualify, rounds
from core import killswitch
from okf.frontmatter import parse
from okf.validate import check_concept_meta
from repo_writer.writer import RepoWriter
from review.service import ActionRefused
from tests import helpers
from tests.test_rd_clustering import _items, _user, pool  # noqa: F401 - the pool fixture

pytestmark = pytest.mark.stack


def _grant(db: Any, user: str, role: str, scope: str | None = None) -> None:
    db.execute("INSERT INTO role_grants (user_id, role, scope_id) VALUES (%s, %s, %s)", (user, role, scope))


@pytest.fixture
def qualified(pool: Any) -> Any:  # noqa: F811
    db = pool["db"]
    db.execute(
        "TRUNCATE cycles, capacity, scoring_rounds, sealed_scores, ai_prescores, coi_flags, presentations, "
        "assessments, decision_sheets, decisions, working_groups, cluster_gates, impact_estimates CASCADE"
    )
    killswitch.set_switch(db, "committee.flow", "on", reason="test: committee flow on", actor="test")
    killswitch.clear_cache()
    batch.run_batch(db)
    prop = next(p for p in _items(db) if p["members"] == pool["a"])
    cid = proposals.act(db, prop["review_item_id"], pool["reviewer"], {"action": "approve"})["cluster_id"]
    # Qualify starts in a job after the approval commits (BLD-221); run it here as the worker would.
    assert db.execute(
        "SELECT 1 FROM jobs WHERE type = 'qualify.start' AND dedupe_key = %s", (f"qualify:{cid}",)
    ).fetchone()
    qualify.start_job(db, cid)
    item = db.execute(
        "SELECT id FROM review_items WHERE item_type = 'qualify' AND ref_id = %s", (cid,)
    ).fetchone()
    chair, _ = _user(db, "core_committee")
    _grant(db, chair, "core_chair")
    members = [_user(db, "core_committee")[0] for _ in range(3)]
    return pool | {"cid": cid, "qualify_item": int(item["id"]), "chair": chair, "members": members}


def _qualify(q: Any, impact: dict[str, Any] | None = None) -> dict[str, Any]:
    db, item, rev = q["db"], q["qualify_item"], q["reviewer2"]
    for gate in qualify.GATES:
        body = {"action": "confirm_gate", "gate": gate, "result": "pass"}
        if gate == "no_conflict":
            body["detail"] = "clear"
        qualify.act(db, item, rev, body)
    qualify.act(db, item, rev, {"action": "save_impact",
                                "fields": impact or {"recurring_saving_inr_per_year": 1_800_000, "evidence_type": "estimate"}})  # fmt: skip
    return qualify.act(db, item, rev, {"action": "complete"})


def test_approval_opens_a_qualify_item_with_the_rules_pre_check(qualified: Any) -> None:
    db = qualified["db"]
    gates = {
        r["gate"]: r
        for r in db.execute("SELECT * FROM cluster_gates WHERE cluster_id = %s", (qualified["cid"],))
    }
    assert set(gates) == set(qualify.GATES)
    assert gates["evidence"]["proposed"] == "pass" and gates["evidence"]["evidence"]["contributors"] == 3
    assert gates["not_planned"]["evidence"] == {"roadmap_connected": False}
    impact = db.execute(
        "SELECT fields FROM impact_estimates WHERE cluster_id = %s", (qualified["cid"],)
    ).fetchone()
    assert impact["fields"]["evidence_type"] in ("data_backed", "estimate", "anecdote")
    timer = db.execute(
        "SELECT state FROM sla_timers WHERE entity_id = %s AND stage = 'qualify'",
        (str(qualified["qualify_item"]),),
    ).fetchone()
    assert timer["state"] == "running"


def test_all_gates_pass_routes_to_a_committee(qualified: Any) -> None:
    out = _qualify(qualified)
    assert out["stage"] == "ready_for_scoring" and out["route_to"] == "core"  # two LOBs: the core committee
    stages = {
        r["stage"]
        for r in qualified["db"].execute("SELECT stage FROM ideas WHERE cluster_id = %s", (qualified["cid"],))
    }
    assert stages == {"ready_for_scoring"}


def test_a_stopped_gate_ends_qualify_with_its_outcome_and_tells_the_contributors(qualified: Any) -> None:
    db, item, rev = qualified["db"], qualified["qualify_item"], qualified["reviewer2"]
    for gate in qualify.GATES:
        body: dict[str, Any] = {"action": "confirm_gate", "gate": gate, "result": "pass"}
        if gate == "no_conflict":
            body = body | {"detail": "conflict", "note": "Conflicts with the distributor agreement terms."}
        qualify.act(db, item, rev, body)
    out = qualify.act(db, item, rev, {"action": "complete"})
    assert out["stage"] == "declined" and out["reason_code"] == "REG_CONFLICT"
    jobs = db.execute("SELECT payload FROM jobs WHERE type = 'comms.route'").fetchall()
    assert any(j["payload"]["event"] == "cluster.gate_outcome" for j in jobs)


def test_big_numbers_wait_for_finance(qualified: Any) -> None:
    with pytest.raises(ActionRefused) as refused:
        _qualify(qualified, {"recurring_saving_inr_per_year": 60_000_000, "evidence_type": "data_backed"})
    assert refused.value.code == "finance_check_pending"
    qualify.act(
        qualified["db"], qualified["qualify_item"], qualified["reviewer2"], {"action": "finance_validated"}
    )
    assert (
        qualify.act(
            qualified["db"], qualified["qualify_item"], qualified["reviewer2"], {"action": "complete"}
        )["stage"]
        == "ready_for_scoring"
    )


def test_the_impact_arithmetic() -> None:
    annual, payback = qualify.computed({"recurring_saving_inr_per_year": 1_200_000, "opex_inr_per_year": 200_000,
                                        "capex_inr": 1_000_000})  # fmt: skip
    assert annual == 800_000 and payback == 12.0  # 1,000,000 ÷ (1,000,000 ÷ 12)


def _round(q: Any) -> str:
    _qualify(q)
    out = rounds.open_cycle(q["db"], q["chair"], {"presentation_slots": 8})
    assert len(out["rounds"]) == 1
    rid = str(out["rounds"][0])
    rounds.prescore_round(q["db"], rid)  # the `round.prescore` job
    return rid


def _score_all(q: Any, rid: str, value: int = 4) -> None:
    sc = rounds.scorecard()
    r = q["db"].execute("SELECT suggested_band FROM scoring_rounds WHERE id = %s", (rid,)).fetchone()
    for m in [q["chair"], *q["members"]]:
        scores = {d: value for d in sc["dimensions"]}
        if r["suggested_band"]:
            scores["financial_value"] = r["suggested_band"]
        rounds.act(q["db"], rid, m, {"action": "score", "scores": scores})


def test_a_blind_round_reveals_when_everyone_has_scored(qualified: Any) -> None:
    db = qualified["db"]
    rid = _round(qualified)
    view = rounds.round_view(db, rid, qualified["members"][0])
    assert view is not None and "revealed" not in view
    assert all(i["contributor"].startswith("Contributor ") for i in view["cluster"]["ideas"])
    assert (
        db.execute("SELECT count(*) AS n FROM ai_prescores WHERE round_id = %s", (rid,)).fetchone()["n"] == 6
    )
    with pytest.raises(ActionRefused) as early:
        rounds.act(db, rid, qualified["chair"], {"action": "reveal"})
    assert early.value.code == "not_ready_to_reveal"
    _score_all(qualified, rid)
    r = db.execute("SELECT * FROM scoring_rounds WHERE id = %s", (rid,)).fetchone()
    assert r["state"] == "revealed" and r["final_score"] is not None
    revealed = rounds.round_view(db, rid, qualified["members"][0])
    assert revealed is not None and set(revealed["revealed"]["ai"]) == set(rounds.scorecard()["dimensions"])
    # Once after reveal; both values kept.
    rounds.act(db, rid, qualified["members"][0], {"action": "revise", "scores": {"reach": 2}})
    with pytest.raises(ActionRefused):
        rounds.act(db, rid, qualified["members"][0], {"action": "revise", "scores": {"reach": 3}})
    row = db.execute(
        "SELECT value, revised_value FROM sealed_scores WHERE round_id = %s AND member_id = %s AND dimension = 'reach'",
        (rid, qualified["members"][0]),
    ).fetchone()
    assert (row["value"], row["revised_value"]) == (4, 2)


def test_a_contributor_on_the_committee_is_flagged_and_cannot_score(qualified: Any) -> None:
    db = qualified["db"]
    owner = db.execute(
        "SELECT user_id FROM contributor_map WHERE contributor_code = (SELECT contributor_code FROM ideas WHERE idea_id = %s)",
        (qualified["a"][0],),
    ).fetchone()["user_id"]
    _grant(db, str(owner), "core_committee")
    rid = _round(qualified)
    flag = db.execute(
        "SELECT status FROM coi_flags WHERE round_id = %s AND member_id = %s", (rid, owner)
    ).fetchone()
    assert flag["status"] == "flagged"
    with pytest.raises(ActionRefused) as refused:
        rounds.act(
            db,
            rid,
            str(owner),
            {"action": "score", "scores": {d: 3 for d in rounds.scorecard()["dimensions"]}},
        )
    assert refused.value.code == "not_eligible"
    rounds.act(db, rid, str(owner), {"action": "declare_conflict"})
    _score_all(qualified, rid)  # everyone else: the recused member does not hold up the reveal
    assert (
        db.execute("SELECT state FROM scoring_rounds WHERE id = %s", (rid,)).fetchone()["state"] == "revealed"
    )


def test_financial_value_moves_one_level_at_most_with_a_reason(qualified: Any) -> None:
    db = qualified["db"]
    rid = _round(qualified)
    band = db.execute("SELECT suggested_band FROM scoring_rounds WHERE id = %s", (rid,)).fetchone()[
        "suggested_band"
    ]
    scores = {d: 3 for d in rounds.scorecard()["dimensions"]}
    scores["financial_value"] = min(5, band + 2)
    with pytest.raises(ActionRefused) as refused:
        rounds.act(db, rid, qualified["members"][1], {"action": "score", "scores": scores})
    assert refused.value.code == "financial_within_one_level"


def _shortlist(q: Any) -> str:
    rid = _round(q)
    _score_all(q, rid, value=5)
    out = rounds.act(q["db"], rid, q["chair"], {"action": "decide", "outcome": "shortlisted",
                                                  "below_threshold_reason": "Worth hearing in person: strong pain at every branch."})  # fmt: skip
    assert out["outcome"] == "shortlisted"
    pres = q["db"].execute("SELECT id FROM presentations WHERE round_id = %s", (rid,)).fetchone()
    decide.write_outline(q["db"], str(pres["id"]))  # the `presentation.outline` job
    return str(pres["id"])


def test_the_whole_way_to_picked_and_a_working_group(qualified: Any) -> None:
    db = qualified["db"]
    pid = _shortlist(qualified)
    p = db.execute("SELECT * FROM presentations WHERE id = %s", (pid,)).fetchone()
    assert p["state"] == "invited" and p["outline"] and len(p["outline"]["slides"]) == 8
    owner = db.execute(
        "SELECT user_id, i.contributor_code FROM ideas i JOIN contributor_map m ON m.contributor_code = i.contributor_code "
        "WHERE i.idea_id = %s",
        (qualified["a"][0],),
    ).fetchone()
    view = decide.contributor_view(db, pid, str(owner["user_id"]))
    assert view is not None and view["state"] == "invited"
    decide.contributor_act(db, pid, str(owner["user_id"]),
                           {"action": "accept", "presenters": [owner["contributor_code"]], "slot": view["slot_options"][0]})  # fmt: skip
    assert (
        db.execute("SELECT stage FROM clusters WHERE id = %s", (qualified["cid"],)).fetchone()["stage"]
        == "presenting"
    )
    decide.committee_act(
        db, pid, qualified["chair"], {"action": "held", "qna_notes": "Asked about AMC forms."}
    )
    for m in [qualified["chair"], *qualified["members"]]:
        decide.committee_act(db, pid, m, {"action": "assess", "scores": {d: 4 for d in rounds.scorecard()["dimensions"]},
                                          "vote": "accept", "route_pref": "build", "strengths": ["Every branch feels it"],
                                          "concerns": ["AMC forms differ"], "will_sponsor": True})  # fmt: skip
    # Sealed: a member's own assessment only.
    other = decide.committee_view(db, pid, qualified["members"][1])
    assert other is not None and other["my_assessment"]["vote"] == "accept" and other["sheet"] is None
    decide.committee_act(db, pid, qualified["chair"], {"action": "collate"})
    sheet = db.execute("SELECT * FROM decision_sheets WHERE presentation_id = %s", (pid,)).fetchone()
    assert sheet["tallies"]["accept"] == 4 and sheet["themes"] is not None
    json.dumps(decide.committee_view(db, pid, qualified["chair"]))  # the API serialises it as plain JSON
    draft = decide.committee_act(
        db, pid, qualified["chair"], {"action": "draft_reasons", "outcome": "picked"}
    )
    assert draft["draft"]["reason"]
    out = decide.committee_act(db, pid, qualified["chair"], {"action": "decide", "outcome": "picked", "route": "build",
                                                              "sponsor_id": qualified["members"][0],
                                                              "plain_reason": draft["draft"]["reason"]})  # fmt: skip
    assert out["outcome"] == "picked" and out["working_group"].startswith("WG-")
    assert (
        db.execute("SELECT stage FROM clusters WHERE id = %s", (qualified["cid"],)).fetchone()["stage"]
        == "picked"
    )
    wg = db.execute(
        "SELECT members, sponsor_id FROM working_groups WHERE id = %s", (out["working_group"],)
    ).fetchone()
    assert {m["contributor_code"] for m in wg["members"]} >= {owner["contributor_code"]}
    assert str(wg["sponsor_id"]) == qualified["members"][0]
    # The repo gets the decision with counts only, and the cluster file its medians; never who voted what.
    writer = RepoWriter(helpers.settings_for(qualified["repo"], qualified["database"]))
    assert writer.acquire()
    try:
        writer.run_once()
    finally:
        writer.release()
    files = list((qualified["repo"] / "decisions").rglob("DEC-*.md"))
    assert len(files) == 1
    doc = parse(files[0].read_text(encoding="utf-8"))
    rel = str(files[0].relative_to(qualified["repo"]))
    assert not [i for i in check_concept_meta(doc.meta or {}, rel) if i.level == "error"]
    assert doc.meta["kfin"]["outcome"] == "picked" and "| accept | 4 |" in files[0].read_text(
        encoding="utf-8"
    )
    names = [r["name"] for r in db.execute("SELECT name FROM users").fetchall()]
    text = files[0].read_text(encoding="utf-8") + (
        qualified["repo"] / "clusters" / f"{qualified['cid']}.md"
    ).read_text(encoding="utf-8")
    assert not any(n in text for n in names)
    assert "## Preliminary review" in text


def test_park_needs_a_reason_and_opens_the_appeal_window(qualified: Any) -> None:
    db = qualified["db"]
    pid = _shortlist(qualified)
    owner = db.execute(
        "SELECT user_id, i.contributor_code FROM ideas i JOIN contributor_map m ON m.contributor_code = i.contributor_code "
        "WHERE i.idea_id = %s",
        (qualified["a"][0],),
    ).fetchone()
    view = decide.contributor_view(db, pid, str(owner["user_id"]))
    assert view is not None
    decide.contributor_act(db, pid, str(owner["user_id"]),
                           {"action": "accept", "presenters": [owner["contributor_code"]], "slot": view["slot_options"][0]})  # fmt: skip
    decide.committee_act(db, pid, qualified["chair"], {"action": "held"})
    for m in [qualified["chair"], *qualified["members"]]:
        decide.committee_act(db, pid, m, {"action": "assess", "scores": {d: 2 for d in rounds.scorecard()["dimensions"]},
                                          "vote": "park"})  # fmt: skip
    decide.committee_act(db, pid, qualified["chair"], {"action": "collate"})
    with pytest.raises(ActionRefused) as refused:
        decide.committee_act(db, pid, qualified["chair"], {"action": "decide", "outcome": "picked", "route": "build",
                                                            "sponsor_id": qualified["members"][0]})  # fmt: skip
    assert refused.value.code == "no_majority"
    out = decide.committee_act(db, pid, qualified["chair"], {
        "action": "decide", "outcome": "parked", "reason_code": "INSUFFICIENT_EVIDENCE",
        "plain_reason": "The committee wants one month of NIGO counts by branch before it decides.",
        "what_would_change": "A month of counts and a two-branch pilot plan."})  # fmt: skip
    timer = db.execute(
        "SELECT state FROM sla_timers WHERE entity_type = 'decision' AND entity_id = %s AND stage = 'appeal_window'",
        (out["decision_id"],),
    ).fetchone()
    assert timer["state"] == "running"


def test_sealed_tables_are_out_of_the_web_apps_reach(test_database: str) -> None:
    import psycopg

    from core.config import get_settings

    port = get_settings().postgres_port
    url = f"postgres://ideas_web:dev-web-only@localhost:{port}/{test_database}?sslmode=disable"
    with psycopg.connect(url, autocommit=True) as web:
        for table in ("sealed_scores", "ai_prescores", "assessments", "decision_sheets"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                web.execute(f"SELECT 1 FROM {table} LIMIT 1")  # noqa: S608 - fixed table names


def test_nobody_else_sees_a_round(qualified: Any) -> None:
    rid = _round(qualified)
    stranger, _ = _user(qualified["db"])
    assert rounds.round_view(qualified["db"], rid, stranger) is None


# ---- review fixes (BLD-221) -----------------------------------------------------------------------------------


def _owner_of(q: Any) -> dict[str, Any]:
    return dict(
        q["db"]
        .execute(
            "SELECT user_id, i.contributor_code FROM ideas i JOIN contributor_map m ON m.contributor_code = i.contributor_code "
            "WHERE i.idea_id = %s",
            (q["a"][0],),
        )
        .fetchone()
    )


def _held(q: Any) -> str:
    db = q["db"]
    pid = _shortlist(q)
    owner = _owner_of(q)
    view = decide.contributor_view(db, pid, str(owner["user_id"]))
    assert view is not None
    decide.contributor_act(db, pid, str(owner["user_id"]),
                           {"action": "accept", "presenters": [owner["contributor_code"]], "slot": view["slot_options"][0]})  # fmt: skip
    decide.committee_act(db, pid, q["chair"], {"action": "held"})
    return pid


def _assess(q: Any, pid: str, member: str, vote: str = "accept") -> dict[str, Any]:
    return decide.committee_act(q["db"], pid, member, {"action": "assess", "vote": vote,
                                                       "scores": {d: 4 for d in rounds.scorecard()["dimensions"]}})  # fmt: skip


def test_a_recusal_carries_into_the_presentation_and_hides_the_group(qualified: Any) -> None:
    db = qualified["db"]
    rid = _round(qualified)
    stepped_aside = qualified["members"][2]
    rounds.act(db, rid, stepped_aside, {"action": "declare_conflict"})
    view = rounds.round_view(db, rid, stepped_aside)
    assert view is not None and view["conflict"] == "recused" and "cluster" not in view
    others = [qualified["chair"], *qualified["members"][:2]]
    sc = rounds.scorecard()
    band = db.execute("SELECT suggested_band FROM scoring_rounds WHERE id = %s", (rid,)).fetchone()[
        "suggested_band"
    ]
    for m in others:
        rounds.act(
            db,
            rid,
            m,
            {
                "action": "score",
                "scores": {d: (band if d == "financial_value" and band else 5) for d in sc["dimensions"]},
            },
        )
    with pytest.raises(ActionRefused) as reveal:
        rounds.act(db, rid, stepped_aside, {"action": "reveal"})
    assert reveal.value.code in ("conflict_of_interest", "chair_only")
    rounds.act(db, rid, qualified["chair"], {"action": "decide", "outcome": "shortlisted",
                                               "below_threshold_reason": "Worth hearing in person: strong pain at every branch."})  # fmt: skip
    pid = str(db.execute("SELECT id FROM presentations WHERE round_id = %s", (rid,)).fetchone()["id"])
    owner = _owner_of(qualified)
    slot = decide.contributor_view(db, pid, str(owner["user_id"]))["slot_options"][0]
    decide.contributor_act(
        db,
        pid,
        str(owner["user_id"]),
        {"action": "accept", "presenters": [owner["contributor_code"]], "slot": slot},
    )
    decide.committee_act(db, pid, qualified["chair"], {"action": "held"})
    stripped = decide.committee_view(db, pid, stepped_aside)
    assert stripped is not None and stripped["conflict"] == "recused" and "cluster" not in stripped
    with pytest.raises(ActionRefused) as vote:
        _assess(qualified, pid, stepped_aside)
    assert vote.value.code == "conflict_of_interest"
    for m in others:
        _assess(qualified, pid, m)
    # Everyone without a conflict has assessed, so the chair can collate before the deadline.
    decide.committee_act(db, pid, qualified["chair"], {"action": "collate"})
    with pytest.raises(ActionRefused) as late:
        _assess(qualified, pid, qualified["members"][1])
    assert late.value.code in ("already_assessed", "already_collated")
    with pytest.raises(ActionRefused) as again:
        decide.committee_act(db, pid, qualified["chair"], {"action": "collate"})
    assert again.value.code == "already_collated"
    chair_view = decide.committee_view(db, pid, qualified["chair"])
    assert chair_view is not None and stepped_aside not in {o["id"] for o in chair_view["sponsor_options"]}


def test_a_manager_of_a_contributor_is_flagged_and_an_admin_can_clear_it(qualified: Any) -> None:
    db = qualified["db"]
    owner = str(_owner_of(qualified)["user_id"])
    manager = qualified["members"][0]
    db.execute("UPDATE users SET manager_user_id = %s WHERE id = %s", (manager, owner))
    rid = _round(qualified)
    flag = db.execute(
        "SELECT reason, status FROM coi_flags WHERE round_id = %s AND member_id = %s", (rid, manager)
    ).fetchone()
    assert (flag["reason"], flag["status"]) == ("manager", "flagged")
    view = rounds.round_view(db, rid, manager)
    assert view is not None and view["conflict"] == "flagged" and "cluster" not in view
    admin, _ = _user(db, "admin")
    rounds.act(
        db,
        rid,
        admin,
        {"action": "clear_conflict", "member_id": manager, "reason": "Manages a different team now."},
    )
    assert rounds.round_view(db, rid, manager)["conflict"] is None
    # A contributor's flag is never cleared: they step aside.
    _grant(db, owner, "core_committee")
    db.execute(
        "INSERT INTO coi_flags (round_id, member_id, reason, status) VALUES (%s, %s, 'contributor', 'flagged')",
        (rid, owner),
    )
    with pytest.raises(ActionRefused) as refused:
        rounds.act(
            db,
            rid,
            admin,
            {"action": "clear_conflict", "member_id": owner, "reason": "Should not be possible."},
        )
    assert refused.value.code == "contributors_recuse"


def test_a_no_show_parks_with_its_own_message(qualified: Any) -> None:
    db = qualified["db"]
    pid = _shortlist(qualified)
    out = decide.committee_act(db, pid, qualified["chair"], {"action": "not_presented"})
    assert out["outcome"] == "parked"
    events = [
        j["payload"]["event"]
        for j in db.execute("SELECT payload FROM jobs WHERE type = 'comms.route'").fetchall()
    ]
    assert "decision.not_presented" in events and "decision.not_accepted" not in events


def test_picked_needs_a_plain_reason(qualified: Any) -> None:
    db = qualified["db"]
    pid = _held(qualified)
    for m in [qualified["chair"], *qualified["members"]]:
        _assess(qualified, pid, m)
    decide.committee_act(db, pid, qualified["chair"], {"action": "collate"})
    with pytest.raises(ActionRefused) as refused:
        decide.committee_act(db, pid, qualified["chair"], {"action": "decide", "outcome": "picked", "route": "build",
                                                            "sponsor_id": qualified["members"][0]})  # fmt: skip
    assert refused.value.code == "reason_required"


def test_a_pass_over_the_rules_fail_needs_a_note(qualified: Any) -> None:
    db, item, rev = qualified["db"], qualified["qualify_item"], qualified["reviewer2"]
    db.execute(
        "UPDATE cluster_gates SET proposed = 'fail' WHERE cluster_id = %s AND gate = 'evidence'",
        (qualified["cid"],),
    )
    with pytest.raises(ActionRefused) as refused:
        qualify.act(db, item, rev, {"action": "confirm_gate", "gate": "evidence", "result": "pass"})
    assert refused.value.code == "note_required"
    qualify.act(db, item, rev, {"action": "confirm_gate", "gate": "evidence", "result": "pass",
                                "note": "Branch counts attached by two contributors."})  # fmt: skip


def test_groups_approved_while_the_switch_is_off_are_picked_up_later(qualified: Any) -> None:
    db = qualified["db"]
    db.execute("DELETE FROM review_items WHERE item_type = 'qualify' AND ref_id = %s", (qualified["cid"],))
    killswitch.set_switch(db, "committee.flow", "off", reason="test: committee flow off", actor="test")
    killswitch.clear_cache()
    assert qualify.backfill(db) == 0
    killswitch.set_switch(db, "committee.flow", "on", reason="test: committee flow on again", actor="test")
    killswitch.clear_cache()
    assert qualify.backfill(db) == 1
    assert db.execute(
        "SELECT 1 FROM review_items WHERE item_type = 'qualify' AND ref_id = %s", (qualified["cid"],)
    ).fetchone()


def test_a_lob_without_a_committee_goes_to_the_core_committee(qualified: Any) -> None:
    db = qualified["db"]
    _qualify(qualified)
    db.execute(
        "UPDATE clusters SET route_to = 'lob', route_lob = 'LOB-no-committee' WHERE id = %s",
        (qualified["cid"],),
    )
    rid = str(rounds.open_cycle(db, qualified["chair"], {"presentation_slots": 8})["rounds"][0])
    r = db.execute("SELECT body, lob_id, roster FROM scoring_rounds WHERE id = %s", (rid,)).fetchone()
    assert r["body"] == "core" and r["lob_id"] is None and qualified["chair"] in {str(m) for m in r["roster"]}
    assert (
        db.execute("SELECT route_to FROM clusters WHERE id = %s", (qualified["cid"],)).fetchone()["route_to"]
        == "core"
    )


def test_every_committee_message_renders(qualified: Any) -> None:
    from comms.route import route
    from comms.send import message_for

    db = qualified["db"]
    db.execute("TRUNCATE notifications CASCADE")
    pid = _held(qualified)
    for m in [qualified["chair"], *qualified["members"]]:
        _assess(qualified, pid, m, vote="park")
    decide.committee_act(db, pid, qualified["chair"], {"action": "collate"})
    decide.committee_act(db, pid, qualified["chair"], {
        "action": "decide", "outcome": "parked", "reason_code": "INSUFFICIENT_EVIDENCE",
        "plain_reason": "The committee wants one month of counts by branch before it decides.",
        "what_would_change": "A month of counts and a two-branch pilot plan."})  # fmt: skip
    jobs = db.execute("SELECT payload FROM jobs WHERE type = 'comms.route' ORDER BY id").fetchall()
    events = {j["payload"]["event"] for j in jobs}
    assert {"round.opened", "shortlist.invited", "presentation.confirmed", "decision.not_accepted"} <= events
    for j in jobs:
        route(db, j["payload"]["event"], dict(j["payload"].get("refs") or {}))
    rows = db.execute("SELECT * FROM notifications WHERE channel = 'email'").fetchall()
    assert {r["event"] for r in rows} >= {"round.opened", "shortlist.invited", "decision.not_accepted"}
    for n in rows:
        subject, body, _ = message_for(db, str(n["user_id"]), n["event"], n["template"], n["payload"])
        assert "{{" not in subject + body, n["event"]
