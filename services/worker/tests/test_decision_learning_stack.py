"""Learning from core committee decisions (BLD-149) and scoring-band proposals (BLD-150), host-side against a test
database, on a real committee decision from lane B's flow. Who may decide which proposal, the fairness hold, and the
reports that count without naming anyone."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from typing import Any

import pytest
from psycopg.types.json import Jsonb

from learning import decisions, proposals
from learning import run as learning_run
from ones.text import OnesRefused
from tests.test_cm_appeals import _round_decision
from tests.test_cm_committee import _grant, _held, _owner_of, _qualify, _score_all, qualified  # noqa: F401
from tests.test_rd_clustering import _user, pool  # noqa: F401 - fixtures

pytestmark = pytest.mark.stack


@pytest.fixture
def learned(qualified: Any, monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:  # noqa: F811
    """The rules come from this run's seeded repo; the learning tables start empty."""
    from core.config import get_settings

    monkeypatch.setenv("COMPANY_REPO_PATH", str(qualified["repo"]))
    get_settings.cache_clear()
    db = qualified["db"]
    db.execute("DELETE FROM learning_proposals WHERE kind IN ('scorecard_weights', 'scoring_band')")
    db.execute(
        "DELETE FROM learning_reports WHERE kind IN ('agreement', 'committee_rewards', 'scoring_band')"
    )
    admin, _ = _user(db, "admin")
    yield qualified | {"admin": admin}
    monkeypatch.undo()
    get_settings.cache_clear()


def _proposal(db: Any, kind: str, key: str, **payload: Any) -> int:
    row = db.execute(
        "INSERT INTO learning_proposals (kind, period, payload) VALUES (%s, '2026-12', %s) RETURNING id",
        (kind, Jsonb({"key": key, "fairness": [], **payload})),
    ).fetchone()
    return int(row["id"])


def _refused(code: str, fn: Any, *args: Any) -> None:
    with pytest.raises(OnesRefused) as err:
        fn(*args)
    assert err.value.code == code


def test_the_chair_decides_weights_the_committee_decides_bands_and_admins_neither(
    learned: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    db, chair, member, admin = learned["db"], learned["chair"], learned["members"][0], learned["admin"]
    weights = _proposal(db, "scorecard_weights", "scorecard_weights:2026-12", current={"reach": 15})
    band = _proposal(db, "scoring_band", "scoring_band:line:2026-12", rule="routing", current=65, proposed=58)
    # The test database has too few people in each group to check fairness: approving waits, in plain words.
    _refused("fairness_unknown", proposals.decide, db, member, band, {"verdict": "approve"})
    monkeypatch.setattr(decisions, "hold_reasons", lambda conn, now: [])
    _refused("forbidden", proposals.decide, db, admin, weights, {"verdict": "approve"})
    _refused("forbidden", proposals.decide, db, admin, band, {"verdict": "approve"})
    _refused("forbidden", proposals.decide, db, member, weights, {"verdict": "approve"})  # the chair's call
    assert proposals.decide(db, member, band, {"verdict": "approve"})["state"] == "approved"
    assert proposals.decide(db, chair, weights, {"verdict": "decline"})["state"] == "declined"
    audit = db.execute(
        "SELECT count(*) AS n FROM audit_log WHERE entity = ANY(%s)",
        ([f"learning_proposal:{weights}", f"learning_proposal:{band}"],),
    ).fetchone()
    assert audit["n"] == 2
    # Approval records the decision; nothing is written to the repo, and the admin's publish step refuses it.
    _refused("not_found", proposals.publish, db, admin, band, {})
    assert all(p["kind"] in ("glossary_term", "area_tag") for p in proposals.listing(db))


def test_a_sharp_fairness_gap_holds_an_approval_but_not_a_decline(
    learned: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    db, member = learned["db"], learned["members"][0]
    monkeypatch.setattr(decisions, "hold_reasons", lambda conn, now: ["The pick rate differs by 30 points"])
    band = _proposal(db, "scoring_band", "scoring_band:multiplier:estimate:2026-12", rule="scorecard",
                     field="confidence_multiplier.estimate", current=0.8, proposed=0.6)  # fmt: skip
    _refused("fairness_hold", proposals.decide, db, member, band, {"verdict": "approve"})
    assert (
        db.execute("SELECT state FROM learning_proposals WHERE id = %s", (band,)).fetchone()["state"]
        == "proposed"
    )
    assert proposals.decide(db, member, band, {"verdict": "decline"})["state"] == "declined"


def test_reports_count_a_real_decision_without_naming_anyone(learned: Any) -> None:
    db, member = learned["db"], learned["members"][0]
    _round_decision(learned, "declined", "LOW_VALUE")
    now = dt.datetime.now(dt.UTC) + dt.timedelta(minutes=1)
    agree = decisions.agreement(db, now, "2026-W51")
    assert agree["rounds"] == "fewer than 5" and agree["agreement"] == "too few to show"
    assert set(agree["dimension_gap"]) == set(decisions._scorecard())
    rewards = decisions.rewards(db, now, "2026-12")
    assert "implied" not in rewards  # far fewer than 30 decisions: no comparison, no proposal
    bands = decisions.bands(db, now, "2026-12")
    assert "observed" not in bands["line"] and set(bands["multipliers"]) == {
        "data_backed",
        "estimate",
        "anecdote",
    }
    assert (
        db.execute("SELECT count(*) AS n FROM learning_proposals WHERE kind = 'scoring_band'").fetchone()["n"]
        == 0
    )
    seen = decisions.view(db, member)
    assert set(seen["reports"]) == {"agreement", "committee_rewards", "scoring_band"}
    assert "apply_rule_version" in seen["coming_soon"]
    text = str(seen)
    assert learned["cid"] not in text and "@" not in text  # no cluster, idea or person in the aggregates
    _refused("forbidden", decisions.view, db, learned["admin"])


def test_the_new_loops_run_by_hand_and_on_schedule(learned: Any) -> None:
    db, admin = learned["db"], learned["admin"]
    assert learning_run.run_now(db, admin, {"kind": "scoring_band"}) == {"ran": "scoring_band"}
    assert "committee_rewards" in learning_run.due(dt.date(2027, 1, 1))
    assert "agreement" in learning_run.due(dt.date(2026, 12, 14))  # a Monday


# ---- review fixes (BLD-151) --------------------------------------------------------------------------------------


def _clusters(db: Any, n: int) -> list[str]:
    taken = {r["id"] for r in db.execute("SELECT id FROM clusters").fetchall()}
    free = [f"CL-{k}" for k in range(9200, 9999) if f"CL-{k}" not in taken][:n]
    for cl in free:
        db.execute("INSERT INTO clusters (id, stage, distinct_contributors) VALUES (%s, 'scored', 3)", (cl,))
    return free


def _rounds(db: Any, rows: list[tuple[str, Any, float, str]], when: dt.datetime) -> list[str]:
    """Synthetic decided rounds: (body, lob_id, final score, outcome)."""
    ids = []
    taken = {r["id"] for r in db.execute("SELECT id FROM scoring_rounds").fetchall()}
    numbers = (f"RND-2099-{k:04d}" for k in range(1, 9999) if f"RND-2099-{k:04d}" not in taken)
    for cl, (body, lob, score, outcome) in zip(_clusters(db, len(rows)), rows, strict=True):
        rid = next(numbers)
        db.execute(
            "INSERT INTO scoring_rounds (id, cluster_id, body, lob_id, scorecard_version, roster, closes_at, state, "
            "final_score, outcome, decided_at, medians) VALUES (%s, %s, %s, %s, '1.0', ARRAY[]::uuid[], %s, 'decided', "
            "%s, %s, %s, %s)",
            (rid, cl, body, lob, when, score, outcome, when, Jsonb({})),
        )
        ids.append(rid)
    return ids


def test_the_core_line_ignores_lob_nominations_and_overturned_rounds(learned: Any) -> None:
    db = learned["db"]
    db.execute("TRUNCATE scoring_rounds CASCADE")
    when = dt.datetime.now(dt.UTC) - dt.timedelta(days=10)
    Row = tuple[str, Any, float, str]
    core: list[Row] = [("core", None, 66.0 + k % 10, "shortlisted") for k in range(16)] + [
        ("core", None, 40.0 + k, "declined") for k in range(16)
    ]
    # A LOB committee nominates at 70 and above and declines just under it: above the core line, never part of it.
    lob: list[Row] = [("lob", "LOB-mf", 70.0 + k, "nominated") for k in range(10)] + [
        ("lob", "LOB-mf", 66.0 + k % 4, "declined") for k in range(20)
    ]
    _rounds(db, core + lob, when)
    # A declined core round at 85 whose decision an appeal overturned: not what the committee decided in the end.
    overturned = _rounds(db, [("core", None, 85.0, "declined")] * 6, when)
    uid = learned["members"][0]
    for k, rid in enumerate(overturned):
        cl = db.execute("SELECT cluster_id FROM scoring_rounds WHERE id = %s", (rid,)).fetchone()[
            "cluster_id"
        ]
        did = f"DEC-2099-{k + 9000}"
        db.execute(
            "INSERT INTO decisions (id, cluster_id, round_id, body, outcome, votes, members_present, decided_by) "
            "VALUES (%s, %s, %s, 'core', 'declined', '{}'::jsonb, 3, 'REV-0001')",
            (did, cl, rid),
        )
        db.execute(
            "INSERT INTO appeals (id, decision_id, cluster_id, appellant_code, grounds, statement, heard_by, panel, "
            "state, outcome, due_at, decided_at) VALUES (%s, %s, %s, 'CTR-0a1b2c', ARRAY['new_evidence'], "
            "'Synthetic statement', 'panel', ARRAY[%s::uuid], 'decided', 'overturned', now(), now())",
            (f"APL-2099-{k + 9000}", did, cl, uid),
        )
    out = decisions.bands(db, dt.datetime.now(dt.UTC), "2026-12")
    assert out["line"]["rounds"] == 32
    assert 56 <= out["line"]["observed"] <= 66 and out["line"]["agreement_at_observed"] == 1.0
    assert (
        db.execute("SELECT count(*) AS n FROM learning_proposals WHERE kind = 'scoring_band'").fetchone()["n"]
        == 0
    )


def test_a_closed_delivery_with_no_baseline_does_not_stop_the_loops(learned: Any) -> None:
    db, admin = learned["db"], learned["admin"]
    _round_decision(learned, "declined", "LOW_VALUE")
    db.execute(
        "INSERT INTO deliveries (subject_type, subject_id, state, closed_at) VALUES ('cluster', %s, 'closed', now()) "
        "ON CONFLICT (subject_type, subject_id) DO UPDATE SET state = 'closed', closed_at = now()",
        (learned["cid"],),
    )
    db.execute(
        "INSERT INTO delivery_measurements (delivery_id, mark, due_at, results) "
        "SELECT id, 'day_90', now(), '{\"actual_vs_target\": null}'::jsonb FROM deliveries "
        "WHERE subject_type = 'cluster' AND subject_id = %s "
        "ON CONFLICT (delivery_id, mark) DO UPDATE SET results = EXCLUDED.results",
        (learned["cid"],),
    )
    out = decisions.bands(db, dt.datetime.now(dt.UTC) + dt.timedelta(minutes=1), "2026-12")
    assert all(m["deliveries"] == 0 for m in out["multipliers"].values())
    assert learning_run.run_now(db, admin, {"kind": "scoring_band"}) == {"ran": "scoring_band"}


def test_open_proposals_stay_on_the_page_and_admins_never_see_committee_reports(learned: Any) -> None:
    db, member, admin = learned["db"], learned["members"][0], learned["admin"]
    old = _proposal(db, "scoring_band", "scoring_band:line:2026-01", rule="routing", current=65, proposed=58)
    db.execute("UPDATE learning_proposals SET created_at = now() - interval '300 days' WHERE id = %s", (old,))
    for k in range(25):
        done = _proposal(
            db, "scoring_band", f"scoring_band:multiplier:x{k}:2026-12", current=0.8, proposed=0.6
        )
        db.execute("UPDATE learning_proposals SET state = 'declined' WHERE id = %s", (done,))
    seen = decisions.view(db, member)
    assert seen["proposals"][0]["id"] == old and len(seen["proposals"]) == 20

    decisions.bands(db, dt.datetime.now(dt.UTC), "2026-12")
    decisions.agreement(db, dt.datetime.now(dt.UTC), "2026-W51")
    reports_for_admin = learning_run.view(db, admin)["reports"]
    assert "scoring_band" not in reports_for_admin and "committee_rewards" not in reports_for_admin
    assert "agreement" in reports_for_admin  # the product lead acts on persistent gaps through the prompts
