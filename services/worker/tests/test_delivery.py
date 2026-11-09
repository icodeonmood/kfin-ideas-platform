"""Delivery (§4.8 to §4.11), lenses (§4.14) and learning (§5): handover packs, manual delivery status, the fix
track, measure and close feeding the Ones, the reminders, the lenses' counts and the learning proposals. Synthetic
people only (BLD-115 to BLD-122)."""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

import pytest

from comms import render, templates
from core import killswitch
from delivery import jobs, service, views
from learning import proposals, reports
from learning import run as learning_run
from ones import service as ones_service
from tests import helpers, test_ones
from tests.test_ones import email, person, refused

# The Ones tests' fixtures: a database with comms pointed at the test repo, and the committee cast.
ones_db = test_ones.ones_db
cast = test_ones.cast

pytestmark = pytest.mark.stack
NOW = dt.datetime(2026, 12, 14, 10, 0, tzinfo=dt.UTC)
D30 = NOW + dt.timedelta(days=30)  # results come at their marks (BLD-127)
D90 = NOW + dt.timedelta(days=90)
METRIC = "Minutes to reconcile one AMC dividend file"


def code_of(db: Any, uid: str) -> str:
    return str(db.execute("SELECT contributor_code FROM contributor_map WHERE user_id = %s", (uid,)).fetchone()[
        "contributor_code"])  # fmt: skip


@pytest.fixture
def crew(
    ones_db: Any, cast: dict[str, str], company_repo: Any, test_database: str, monkeypatch: pytest.MonkeyPatch
) -> dict[str, str]:
    import lenses

    settings = helpers.settings_for(company_repo, test_database)
    for module in (lenses, proposals, reports):  # the taxonomy and the budget come from the test repo
        monkeypatch.setattr(module, "get_settings", lambda: settings)
    db = ones_db
    return {
        **cast,
        "owner": person(db, "working_group"),
        "sponsor": person(db, "sponsor"),
        "pm": person(db),
        "submitter": person(db),
    }


def picked_idea(db: Any, crew: dict[str, str]) -> str:
    return helpers.insert_idea(db, contributor=code_of(db, crew["submitter"]), stage="picked")


def full_pack(db: Any, crew: dict[str, str], **over: Any) -> dict[str, Any]:
    body = {
        "owner_email": email(db, crew["owner"]), "sponsor_email": email(db, crew["sponsor"]),
        "pm_email": email(db, crew["pm"]), "metric": METRIC, "baseline": 40, "target": 10,
        "unit": "minutes per case", "spend": "CC-OPS/2026", "product": "iris", "feature_type": "kfintech-product",
        "checklist": {"working_group_formed": True, "baseline_captured": True, "build_slot_confirmed": True,
                      "dev_slot_confirmed": True},
    }  # fmt: skip
    body.update(over)
    return body


def started(db: Any, crew: dict[str, str], track: str = "build") -> tuple[str, int]:
    idea = picked_idea(db, crew)
    did = service.start(db, crew["member"], {"subject_type": "idea", "subject_id": idea, "track": track})[
        "id"
    ]
    return idea, did


def approved(
    db: Any, crew: dict[str, str], track: str = "build", sponsor: str | None = None, **over: Any
) -> tuple[str, int]:
    idea, did = started(db, crew, track)
    sponsor = sponsor or crew["sponsor"]
    extra = {"objective": "Every AMC dividend file reconciled the same day"} if track == "fix" else {}
    service.save_pack(
        db, crew["member"], did, full_pack(db, crew, sponsor_email=email(db, sponsor), **extra, **over)
    )
    service.submit(db, crew["owner"], did)
    service.approve(db, sponsor, did, now=NOW)
    return idea, did


def stage(db: Any, idea: str) -> str:
    return str(db.execute("SELECT stage FROM ideas WHERE idea_id = %s", (idea,)).fetchone()["stage"])


def events(db: Any, name: str) -> list[dict[str, Any]]:
    rows = db.execute(
        "SELECT payload FROM jobs WHERE type = 'comms.route' AND payload->>'event' = %s ORDER BY id", (name,)
    ).fetchall()
    return [r["payload"]["refs"] for r in rows]


# --- Handover ---------------------------------------------------------------------------------------------------------


def test_only_the_committee_starts_a_handover_and_only_for_a_picked_idea(ones_db: Any, crew: Any) -> None:
    db = ones_db
    idea = picked_idea(db, crew)
    refused("forbidden", service.start, db, crew["employee"], {"subject_type": "idea", "subject_id": idea})
    refused("not_picked", service.start, db, crew["member"],
            {"subject_type": "idea", "subject_id": helpers.insert_idea(db, stage="reviewed")})  # fmt: skip
    refused(
        "subject_required", service.start, db, crew["member"], {"subject_type": "idea", "subject_id": "x1"}
    )
    did = service.start(db, crew["member"], {"subject_type": "idea", "subject_id": idea})["id"]
    assert stage(db, idea) == "handover"
    refused("already_started", service.start, db, crew["admin"], {"subject_type": "idea", "subject_id": idea})
    # The committee flow's hook is idempotent.
    assert service.start_from_pick(db, "idea", idea) == did
    other = picked_idea(db, crew)
    assert service.start_from_pick(db, "idea", other, "fix") != did


def test_the_pack_names_a_real_sponsor_who_is_not_the_owner(ones_db: Any, crew: Any) -> None:
    db = ones_db
    _, did = started(db, crew)
    refused("sponsor_not_a_sponsor", service.save_pack, db, crew["member"], did,
            {"sponsor_email": email(db, crew["pm"])})  # fmt: skip
    both = person(db, "sponsor")
    refused("owner_is_sponsor", service.save_pack, db, crew["member"], did,
            {"owner_email": email(db, both), "sponsor_email": email(db, both)})  # fmt: skip
    refused("spend_not_valid", service.save_pack, db, crew["member"], did, {"spend": "a cost centre"})
    refused("unit_not_valid", service.save_pack, db, crew["member"], did, {"unit": "bananas"})
    # Someone outside the delivery cannot see it, let alone edit it.
    refused("not_found", service.save_pack, db, crew["employee"], did, {"spend": "NONE"})


def test_submit_lists_what_is_missing_and_the_sponsor_approves_with_one_click(
    ones_db: Any, crew: Any
) -> None:
    db = ones_db
    idea, did = started(db, crew)
    service.save_pack(db, crew["member"], did, {"owner_email": email(db, crew["owner"])})
    with pytest.raises(service.Refused) as exc:
        service.submit(db, crew["owner"], did)
    assert exc.value.code.startswith("pack_incomplete:") and "metric" in exc.value.code
    service.save_pack(db, crew["owner"], did, full_pack(db, crew))
    refused("forbidden", service.submit, db, crew["pm"], did)  # only the owner (or an admin) submits
    assert service.submit(db, crew["owner"], did)["state"] == "awaiting_sponsor"
    assert events(db, "delivery.approval_needed")[-1]["current_owner_ids"] == [crew["sponsor"]]
    refused("sponsor_only", service.approve, db, crew["owner"], did)
    refused("sponsor_only", service.approve, db, crew["member"], did)
    service.send_back(db, crew["sponsor"], did)
    service.submit(db, crew["owner"], did)
    assert service.approve(db, crew["sponsor"], did, now=NOW)["state"] == "in_delivery"
    assert stage(db, idea) == "in_garage"
    row = db.execute(
        "SELECT actor, payload FROM outbox WHERE aggregate_id = %s AND event_type = 'idea.stage_changed' "
        "ORDER BY id DESC LIMIT 1",
        (idea,),
    ).fetchone()
    assert row["actor"] == "process:delivery" and row["payload"]["history"][0]["event"] == "in_garage"
    d = views.detail(db, crew["owner"], did)
    assert d is not None and d["metric"] == METRIC and d["phase_words"] == "Discovery"
    assert d["link_state"] == "manual" and d["pipeline_page_id"] is None
    refused("pack_locked", service.save_pack, db, crew["owner"], did, {"spend": "NONE"})


# --- Delivery status, measure and close ----------------------------------------------------------------------------------


def test_build_track_from_phase_to_closed_feeds_the_ones(ones_db: Any, crew: Any) -> None:
    db = ones_db
    idea, did = approved(db, crew)
    pid = ones_service.induct_from_decision(db, idea, crew["chair"], NOW.date(), now=NOW)
    assert pid is not None
    one = ones_service.carry_out(db, crew["admin"], pid, now=NOW)

    refused("not_found", service.set_phase, db, crew["employee"], did, {"phase": "05-build"})
    refused("forbidden", service.set_phase, db, crew["owner"], did, {"phase": "05-build"})
    refused("phase_not_valid", service.set_phase, db, crew["pm"], did, {"phase": "06-garage"})
    service.set_phase(db, crew["pm"], did, {"phase": "05-build", "gate_status": "blocked"}, now=NOW)
    assert events(db, "delivery.phase_changed")[-1]["phase"] == "05-build"
    refused("page_id_not_valid", service.link_page, db, crew["admin"], did, {"page_id": "../x"})
    assert service.link_page(db, crew["admin"], did, {"page_id": "a1b2c3d4e5f6"})["link_state"] == "linked"

    service.set_phase(db, crew["pm"], did, {"phase": "shipped"}, now=NOW)
    assert stage(db, idea) == "shipped"
    marks = db.execute("SELECT mark FROM delivery_measurements WHERE delivery_id = %s ORDER BY mark", (did,))
    assert [r["mark"] for r in marks.fetchall()] == ["day_30", "day_90"]

    refused("forbidden", service.fill, db, crew["sponsor"], did, "day_30", {"metric_actual": 12})
    refused("not_due_yet", service.fill, db, crew["owner"], did, "day_30", {"metric_actual": 12}, now=NOW)
    out = service.fill(db, crew["owner"], did, "day_30", {"metric_actual": 12,
                       "time": {"value": 300, "unit": "hours a month"}}, now=D30)  # fmt: skip
    assert out["target_met"] is False
    refused("sponsor_only", service.confirm, db, crew["owner"], did, "day_30")
    service.confirm(db, crew["sponsor"], did, "day_30", now=D30)
    assert stage(db, idea) == "measuring"
    measures = db.execute("SELECT measures FROM ones WHERE id = %s", (one["one_id"],)).fetchone()["measures"]
    assert measures["time"] == {"value": 300, "unit": "hours a month"}

    service.fill(db, crew["owner"], did, "day_90", {"metric_actual": 9, "capex_inr": 0, "opex_inr": 120000,
                 "money": {"value": 1800000, "unit": "rupees a year"}}, now=D90)  # fmt: skip
    service.confirm(db, crew["sponsor"], did, "day_90", now=D90)
    d = db.execute("SELECT state, outcome FROM deliveries WHERE id = %s", (did,)).fetchone()
    assert (d["state"], d["outcome"]) == ("closed", "target_met") and stage(db, idea) == "closed"
    money = db.execute("SELECT measures FROM ones WHERE id = %s", (one["one_id"],)).fetchone()["measures"][
        "money"
    ]
    assert money["finance_confirmed"] is False  # money shows only after Finance confirms (DEC-071)
    refused("forbidden", service.finance_confirm, db, crew["sponsor"], did, "day_90")
    refused("no_money_figure", service.finance_confirm, db, crew["admin"], did, "day_30")
    service.finance_confirm(db, crew["admin"], did, "day_90", now=D90)
    refused("already_finance_confirmed", service.finance_confirm, db, crew["admin"], did, "day_90")
    money = db.execute("SELECT measures FROM ones WHERE id = %s", (one["one_id"],)).fetchone()["measures"][
        "money"
    ]
    assert money["finance_confirmed"] is True
    assert events(db, "delivery.phase_changed")[-1]["outcome"] == "target_met"


def test_a_sponsor_never_confirms_their_own_entry(ones_db: Any, crew: Any) -> None:
    db = ones_db
    both = person(db, "sponsor", "admin")
    _, did = approved(db, crew, sponsor=both)
    service.set_phase(db, crew["pm"], did, {"phase": "shipped"}, now=NOW)
    service.fill(db, both, did, "day_30", {"metric_actual": 20}, now=D30)  # as an admin
    refused("own_entry", service.confirm, db, both, did, "day_30")
    service.fill(db, crew["owner"], did, "day_30", {"metric_actual": 20}, now=D30)
    assert service.confirm(db, both, did, "day_30", now=D30)["closed"] is False


def test_the_submitter_hears_about_progress_but_is_sent_to_my_ideas(ones_db: Any, crew: Any) -> None:
    db = ones_db
    _, did = approved(db, crew)
    refs = events(db, "delivery.phase_changed")[-1]
    assert refs["phase"] == "started"
    for_submitter = render.variables(db, crew["submitter"], "delivery.phase_changed", refs)
    for_owner = render.variables(db, crew["owner"], "delivery.phase_changed", refs)
    assert for_submitter["links"]["delivery"].endswith("/my-ideas")
    assert for_owner["links"]["delivery"].endswith(f"/delivery/{did}")
    subject_line, body, _ = templates.render("delivery-phase-changed", for_submitter)
    assert subject_line.endswith(": Started") and "has started" in body
    for word in ("Garage", "duplicate", "rejected", "already solved"):
        assert word not in body and word not in subject_line


def test_nobody_approves_their_own_submission_or_completion(ones_db: Any, crew: Any) -> None:
    """BLD-126: an admin who is also the named sponsor can't send a pack and approve it, or submit a fix's numbers
    and approve them."""
    db = ones_db
    both = person(db, "sponsor", "admin")
    _, did = started(db, crew)
    service.save_pack(db, crew["member"], did, full_pack(db, crew, sponsor_email=email(db, both)))
    service.submit(db, both, did)  # as an admin
    refused("own_submission", service.approve, db, both, did)
    service.send_back(db, both, did)
    service.submit(db, crew["owner"], did)
    assert service.approve(db, both, did, now=NOW)["state"] == "in_delivery"

    _, fix = approved(db, crew, "fix", pm_email="", sponsor=both)
    service.complete_fix(db, both, fix, {"before": 40, "after": 15}, now=NOW)  # as an admin
    refused("own_entry", service.approve_completion, db, both, fix)
    service.complete_fix(db, crew["owner"], fix, {"before": 40, "after": 14}, now=NOW)
    assert service.approve_completion(db, both, fix, now=NOW)["state"] == "resolved"


def test_results_follow_their_marks_and_finance_never_rolls_back(ones_db: Any, crew: Any) -> None:
    """BLD-126/127: no 90-day confirmation before the 30-day one; Finance confirming a late 30-day money figure
    doesn't replace the 90-day values the Ones show; the admin who typed a figure never vouches for it."""
    db = ones_db
    idea, did = approved(db, crew)
    pid = ones_service.induct_from_decision(db, idea, crew["chair"], NOW.date(), now=NOW)
    assert pid is not None
    one = ones_service.carry_out(db, crew["admin"], pid, now=NOW)
    service.set_phase(db, crew["pm"], did, {"phase": "shipped"}, now=NOW)
    service.fill(db, crew["admin"], did, "day_30", {"metric_actual": 30,
                 "money": {"value": 100000, "unit": "rupees a year"}}, now=D30)  # fmt: skip
    service.fill(db, crew["owner"], did, "day_90", {"metric_actual": 12,
                 "money": {"value": 900000, "unit": "rupees a year"}}, now=D90)  # fmt: skip
    refused("day_30_first", service.confirm, db, crew["sponsor"], did, "day_90")
    service.confirm(db, crew["sponsor"], did, "day_30", now=D30)
    service.confirm(db, crew["sponsor"], did, "day_90", now=D90)
    refused("own_entry", service.finance_confirm, db, crew["admin"], did, "day_30")  # they typed it
    other = person(db, "admin")
    service.finance_confirm(db, other, did, "day_30", now=D90)
    money = db.execute("SELECT measures FROM ones WHERE id = %s", (one["one_id"],)).fetchone()["measures"][
        "money"
    ]
    assert money["value"] == 900000 and money["finance_confirmed"] is False  # still the 90-day figure
    service.finance_confirm(db, other, did, "day_90", now=D90)
    money = db.execute("SELECT measures FROM ones WHERE id = %s", (one["one_id"],)).fetchone()["measures"][
        "money"
    ]
    assert money == {"value": 900000, "unit": "rupees a year", "finance_confirmed": True}


def test_a_group_delivery_moves_grouped_ideas_but_not_withdrawn_ones(ones_db: Any, crew: Any) -> None:
    """BLD-126: member ideas still `in_cluster` move with their group; withdrawn and parked ones stay put."""
    db = ones_db
    taken = {r["id"] for r in db.execute("SELECT id FROM clusters").fetchall()}
    cl = next(f"CL-{n}" for n in range(9100, 9999) if f"CL-{n}" not in taken)
    db.execute("INSERT INTO clusters (id, stage, distinct_contributors) VALUES (%s, 'picked', 3)", (cl,))
    grouped = helpers.insert_idea(db, contributor=code_of(db, crew["submitter"]), stage="in_cluster")
    left = helpers.insert_idea(db, contributor=code_of(db, crew["owner"]), stage="withdrawn")
    parked = helpers.insert_idea(db, contributor=code_of(db, crew["pm"]), stage="parked")
    db.execute("UPDATE ideas SET cluster_id = %s WHERE idea_id = ANY(%s)", (cl, [grouped, left, parked]))
    did = service.start(db, crew["member"], {"subject_type": "cluster", "subject_id": cl, "track": "build"})[
        "id"
    ]
    service.save_pack(db, crew["member"], did, full_pack(db, crew))
    service.submit(db, crew["owner"], did)
    service.approve(db, crew["sponsor"], did, now=NOW)
    assert stage(db, grouped) == "in_garage"
    assert (stage(db, left), stage(db, parked)) == ("withdrawn", "parked")


def test_progress_ratio_reads_reductions_and_increases_alike() -> None:
    assert service.progress_ratio(40, 10, 10) == 1.0  # a reduction, met
    assert service.progress_ratio(40, 10, 25) == 0.5
    assert service.progress_ratio(10, 40, 40) == 1.0  # an increase, met
    assert service.progress_ratio(10, 10, 12) is None and service.progress_ratio(None, 10, 5) is None


# --- Fix track and reminders -------------------------------------------------------------------------------------------


def test_fix_track_milestones_reminders_and_completion(ones_db: Any, crew: Any) -> None:
    db = ones_db
    idea, did = approved(db, crew, "fix", pm_email="")
    assert stage(db, idea) == "in_fix_track"
    refused("not_in_delivery", service.set_phase, db, crew["admin"], did, {"phase": "05-build"})
    m = service.add_milestone(db, crew["owner"], did, {"title": "Agree the new checklist with MF Ops",
                              "due_on": (NOW.date() - dt.timedelta(days=20)).isoformat()}, now=NOW)  # fmt: skip
    refused("not_found", service.add_milestone, db, crew["pm"], did, {"title": "Something else to do",
            "due_on": NOW.date().isoformat()}, now=NOW)  # fmt: skip

    db.execute("DELETE FROM jobs")
    counts = jobs.tick(db, NOW)
    assert counts["milestones_overdue"] == 1 and counts["plans_escalated"] == 1
    assert {r["reason"] for r in events(db, "delivery.overdue")} == {"milestone", "plan_late"}
    assert jobs.tick(db, NOW + dt.timedelta(days=1))["milestones_overdue"] == 0  # once only

    service.set_milestone(db, crew["owner"], did, m["id"], {"status": "done"}, now=NOW)
    refused("nothing_to_approve", service.approve_completion, db, crew["sponsor"], did)
    service.complete_fix(db, crew["owner"], did, {"before": 40, "after": 15}, now=NOW)
    assert events(db, "delivery.completion_to_approve")[-1]["current_owner_ids"] == [crew["sponsor"]]
    refused(
        "own_entry", service.approve_completion, db, crew["owner"], did
    )  # not a sponsor, and their numbers
    service.approve_completion(db, crew["sponsor"], did, now=NOW)
    assert stage(db, idea) == "resolved"

    db.execute("DELETE FROM jobs")
    later = NOW + dt.timedelta(days=28)
    assert jobs.tick(db, later)["measure_due"] == 1  # the 30-day measurement is due within 3 days
    assert jobs.tick(db, later + dt.timedelta(days=1))["measure_due"] == 0  # at most weekly


def test_blocked_for_ten_working_days_flags_the_sponsor_once(ones_db: Any, crew: Any) -> None:
    db = ones_db
    _, did = approved(db, crew)
    service.set_phase(db, crew["pm"], did, {"phase": "05-build", "gate_status": "blocked"}, now=NOW)
    db.execute("DELETE FROM jobs")
    assert jobs.tick(db, NOW + dt.timedelta(days=5))["blocked_flagged"] == 0
    assert jobs.tick(db, NOW + dt.timedelta(days=20))["blocked_flagged"] == 1
    assert jobs.tick(db, NOW + dt.timedelta(days=21))["blocked_flagged"] == 0
    assert events(db, "delivery.overdue")[-1] == {"delivery_id": did, "subject_id": events(db, "delivery.overdue")[
        -1]["subject_id"], "reason": "blocked", "current_owner_ids": [crew["sponsor"]]}  # fmt: skip


def test_the_console_shows_each_person_only_their_deliveries(ones_db: Any, crew: Any) -> None:
    db = ones_db
    waiting = picked_idea(db, crew)
    _, did = approved(db, crew)
    committee = views.console(db, crew["member"])
    assert committee["can_start"] and any(w["subject_id"] == waiting for w in committee["waiting"])
    assert any(d["id"] == did for d in committee["deliveries"])
    mine = views.console(db, crew["owner"])
    assert [d["id"] for d in mine["deliveries"]] == [did] and mine["waiting"] == [] and not mine["can_start"]
    assert views.console(db, crew["employee"])["deliveries"] == []
    assert views.detail(db, crew["employee"], did) is None
    assert views.detail(db, crew["owner"], "x1") is None


# --- Lenses ------------------------------------------------------------------------------------------------------------


def test_lenses_are_counts_only_for_committees_and_admins(ones_db: Any, crew: Any) -> None:
    from lenses import build, rebuild, view

    db = ones_db
    approved(db, crew)
    named = person(db, name="Kavya Raghunathan")
    helpers.insert_idea(db, contributor=code_of(db, named), stage="scanned")
    assert build(db, NOW)["lobs"] > 0
    refused("forbidden", view, db, crew["employee"])
    refused("forbidden", rebuild, db, crew["member"])
    out = view(db, crew["member"])
    assert out["lobs"] and out["roles"] and not out["can_rebuild"]
    text = json.dumps(out)
    assert "Kavya" not in text and "Raghunathan" not in text and "@" not in text
    assert view(db, crew["admin"])["can_rebuild"] and rebuild(db, crew["admin"])["lobs"] > 0
    assert db.execute("SELECT 1 FROM audit_log WHERE action = 'lenses.rebuilt'").fetchone() is not None


# --- Learning ----------------------------------------------------------------------------------------------------------


def test_glossary_proposals_wait_for_an_admin_and_stop_with_the_switch(ones_db: Any, crew: Any) -> None:
    db = ones_db
    for _ in range(3):
        idea = helpers.insert_idea(db)
        db.execute(
            "UPDATE ideas SET canvas = jsonb_set(canvas, '{neutral_summary}', '\"The NAVRECON report runs late\"'), "
            "submitted_at = %s WHERE idea_id = %s",
            (NOW - dt.timedelta(days=2), idea),
        )
    assert proposals.glossary(db, NOW, "2026-W51") >= 1
    assert proposals.glossary(db, NOW, "2026-W51") == 0  # never proposed twice
    listed = [p for p in proposals.listing(db) if p["term"] == "NAVRECON"]
    assert listed and listed[0]["state"] == "proposed" and listed[0]["ideas"] == 3
    pid = listed[0]["id"]
    refused("forbidden", proposals.decide, db, crew["member"], pid, {"verdict": "approve"})
    refused("verdict_required", proposals.decide, db, crew["admin"], pid, {})
    assert proposals.decide(db, crew["admin"], pid, {"verdict": "approve"}, now=NOW)["state"] == "approved"
    refused("not_open", proposals.decide, db, crew["admin"], pid, {"verdict": "decline"})

    refused("forbidden", learning_run.view, db, crew["member"])
    assert learning_run.view(db, crew["admin"])["switched_on"] is True
    db.execute("UPDATE kill_switches SET state = 'off' WHERE name = 'learning.jobs'")
    killswitch.clear_cache()
    try:
        assert learning_run.run(db, NOW) == []
        refused("learning_paused", learning_run.run_now, db, crew["admin"], {"kind": "autonomy"})
    finally:
        db.execute("UPDATE kill_switches SET state = 'on' WHERE name = 'learning.jobs'")
        killswitch.clear_cache()
    assert learning_run.run_now(db, crew["admin"], {"kind": "autonomy"}) == {"ran": "autonomy"}
    assert learning_run.run(db, dt.datetime(2026, 12, 14, 0, 30, tzinfo=dt.UTC)) == [
        "autonomy",
        "drift",
        "glossary",
    ]  # a Monday
    assert db.execute("SELECT mode FROM autonomy WHERE mode <> 'gated'").fetchone() is None  # still off
