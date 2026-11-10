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


def test_the_chair_decides_weights_the_committee_decides_bands_and_admins_neither(learned: Any) -> None:
    db, chair, member, admin = learned["db"], learned["chair"], learned["members"][0], learned["admin"]
    weights = _proposal(db, "scorecard_weights", "scorecard_weights:2026-12", current={"reach": 15})
    band = _proposal(db, "scoring_band", "scoring_band:line:2026-12", rule="routing", current=65, proposed=58)
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
