"""Learning from core committee decisions (BLD-149) and scoring-band proposals (BLD-150). No database or stack:
the pure functions that turn the committee's records into readable findings."""

from __future__ import annotations

import numpy as np

from learning import decisions
from learning.proposals import APPROVER, COMMITTEE_KINDS

DIMS = ["customer_experience", "effort", "financial_value", "reach", "risk_compliance", "time_to_value"]


def test_the_fit_finds_the_dimension_that_drives_picks() -> None:
    rng = np.random.default_rng(7)
    x = rng.integers(1, 6, size=(200, len(DIMS))).astype(float)
    y = (x[:, DIMS.index("financial_value")] >= 4).astype(float)  # the committee picks on money alone
    coefs = decisions.fit_logistic(x, y)
    assert int(np.argmax(coefs)) == DIMS.index("financial_value")
    weights = decisions.implied_weights(coefs, DIMS)
    assert sum(weights.values()) == 100
    assert weights["financial_value"] == max(weights.values()) and weights["financial_value"] >= 60


def test_implied_weights_drop_negative_pulls_and_handle_nothing() -> None:
    assert decisions.implied_weights(np.array([2.0, -1.0, 2.0]), ["a", "b", "c"]) == {
        "a": 50,
        "b": 0,
        "c": 50,
    }
    assert decisions.implied_weights(np.array([-1.0, 0.0]), ["a", "b"]) == {"a": 0, "b": 0}
    out = decisions.implied_weights(np.array([1.0, 1.0, 1.0]), ["a", "b", "c"])
    assert sum(out.values()) == 100  # 33 + 33 + 33, the remainder goes to one of them
    assert decisions.fit_logistic(np.zeros((0, 0)), np.zeros(0)).size == 0


def test_only_material_differences_count() -> None:
    current = {"financial_value": 30, "reach": 15, "effort": 10}
    implied = {"financial_value": 45, "reach": 6, "effort": 10}
    assert decisions.material_weights(current, implied) == [
        "financial_value"
    ]  # reach is 9 apart: not material
    assert decisions.material_weights(current, current) == []


def test_best_line_finds_where_the_committee_draws_it() -> None:
    scores = [50.0, 55.0, 58.0, 59.0, 62.0, 64.0, 66.0, 70.0, 75.0, 80.0]
    above = [s >= 60 for s in scores]  # the committee shortlists from 60, the rule says 65
    line, rate, now = decisions.best_line(scores, above, 65.0)
    assert 60 <= line <= 62 and rate == 1.0
    assert now == 0.8
    assert decisions.best_line([], [], 65.0) == (65.0, 0.0, 0.0)


def test_best_line_keeps_the_current_line_when_nothing_is_better() -> None:
    scores = [40.0, 50.0, 70.0, 80.0]
    above = [False, False, True, True]
    assert decisions.best_line(scores, above, 65.0)[0] == 65.0  # ties go to the line nearest the current one


def test_observed_multiplier_is_the_median_capped_and_rounded() -> None:
    assert decisions.observed_multiplier([0.4, 0.5, 0.62, 0.7, 0.9]) == 0.6
    assert decisions.observed_multiplier([1.4, 1.2, 1.1]) == 1.0  # never above face value
    assert decisions.observed_multiplier([0.5, 0.6]) == 0.55
    assert decisions.observed_multiplier([]) == 0.0


def test_ai_score_uses_the_scorecard_weights() -> None:
    weights = {"financial_value": 30, "reach": 70}
    assert decisions.ai_score({"financial_value": 5.0, "reach": 5.0}, weights) == 100.0
    assert decisions.ai_score({"financial_value": 1.0, "reach": 1.0}, weights) == 0.0
    assert decisions.ai_score({"financial_value": 5.0}, weights) == 30.0  # a missing rating counts as 1


def test_fairness_holds_on_a_sharp_gap_and_ignores_suppressed_groups() -> None:
    report = {
        "by_lob": [
            {"group": "LOB-mf", "shortlist_rate": 0.5, "pick_rate": 0.2},
            {"group": "LOB-nps", "shortlist_rate": 0.2, "pick_rate": 0.15},
            {"group": "LOB-other", "shortlist_rate": "fewer than 5", "pick_rate": "fewer than 5"},
        ],
        "by_location": [{"group": "Hyderabad", "shortlist_rate": 0.4, "pick_rate": 0.1}],
    }
    assert decisions.fairness_reasons(report) == [
        "The shortlist rate differs by 30 points across lines of business"
    ]
    assert decisions.fairness_reasons({"by_lob": [], "by_location": []}) == []


def test_committee_proposals_wait_for_the_chair_or_the_committee_never_an_admin() -> None:
    assert set(COMMITTEE_KINDS) == {"scorecard_weights", "scoring_band"}
    assert APPROVER["scorecard_weights"] == {"core_chair"}
    assert "admin" not in APPROVER["scoring_band"] and "core_committee" in APPROVER["scoring_band"]
    assert APPROVER["glossary_term"] == {"admin"}
    assert (
        "apply_rule_version" in decisions.COMING_SOON
    )  # approval records the decision; nothing applies itself
