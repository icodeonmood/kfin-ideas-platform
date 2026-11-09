"""Delivery, lenses and learning: the pure parts, without the stack (BLD-115 to BLD-122)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import pytest
import yaml

from delivery.phases import GATE_STATUS, PHASES
from delivery.service import missing, target_met
from learning.proposals import candidate_terms
from learning.reports import HIGH_BAND, WINDOW, acceptance, quarter_of
from learning.run import due
from lenses import STAGE_GROUPS, group_counts

REPO = Path(__file__).resolve().parents[3]


def test_phases_match_the_garage_contract() -> None:
    path = REPO / "contracts" / "garage" / "phases.yaml"
    if not path.exists():
        pytest.skip("contracts folder not in this checkout")
    contract = yaml.safe_load(path.read_text())
    assert [(p["id"], p["shown_as"]) for p in contract["phases"]] == list(PHASES)
    assert tuple(contract["gate_status"]) == GATE_STATUS


def test_phase_words_never_name_the_pipeline() -> None:
    for _, words in PHASES:
        assert "garage" not in words.lower()


@pytest.mark.parametrize(
    ("baseline", "target", "actual", "met"),
    [
        (40, 10, 9, True),  # down is better: 40 minutes to 10, reached 9
        (40, 10, 12, False),
        (5, 20, 20, True),  # up is better: reached exactly
        (5, 20, 19.5, False),
        (5, 5, 5, True),
        (None, 5, 5, None),
        ("x", 5, 5, None),
    ],
)
def test_target_met_follows_the_direction_of_the_target(
    baseline: Any, target: Any, actual: Any, met: Any
) -> None:
    assert target_met(baseline, target, actual) is met


def _pack(track: str = "build", **over: Any) -> dict[str, Any]:
    d: dict[str, Any] = {
        "track": track,
        "owner_user_id": "u1",
        "sponsor_user_id": "u2",
        "pm_user_id": "u3",
        "metric_encrypted": b"x",
        "objective_encrypted": b"y",
        "pack": {
            "baseline": 40,
            "target": 10,
            "unit": "minutes per case",
            "spend": "CC-OPS/2026",
            "feature_type": "kfintech-product",
            "checklist": {
                "working_group_formed": True,
                "baseline_captured": True,
                "build_slot_confirmed": True,
                "dev_slot_confirmed": True,
            },
        },
    }
    d.update(over)
    return d


def test_a_complete_pack_misses_nothing() -> None:
    assert missing(_pack()) == []
    assert missing(_pack("fix", pm_user_id=None)) == []


def test_missing_lists_every_gap_in_codes() -> None:
    d = _pack(owner_user_id=None, metric_encrypted=None, pm_user_id=None)
    d["pack"] = {"feature_type": "kfintech-product", "checklist": {}}
    gaps = missing(d)
    assert gaps == [
        "owner_user_id", "metric", "baseline", "target", "unit", "spend", "working_group_formed",
        "baseline_captured", "pm_user_id", "build_slot_confirmed", "dev_slot_confirmed",
    ]  # fmt: skip


def test_fix_track_needs_an_objective_not_a_build_slot() -> None:
    d = _pack("fix", objective_encrypted=None, pm_user_id=None)
    d["pack"]["checklist"] = {"working_group_formed": True, "baseline_captured": True}
    assert missing(d) == ["objective"]


def test_ai_tooling_needs_no_dev_slot() -> None:
    d = _pack()
    d["pack"]["feature_type"] = "ai-tooling"
    d["pack"]["checklist"]["dev_slot_confirmed"] = False
    assert missing(d) == []


def test_glossary_candidates_need_three_distinct_ideas() -> None:
    texts = {
        "IDEA-2026-000001": ["The NCTO report is late", "NCTO again"],
        "IDEA-2026-000002": ["NCTO and FolioSync"],
        "IDEA-2026-000003": ["Waiting on NCTO", "FolioSync"],
        "IDEA-2026-000004": ["The CEO and IT asked", "CEO"],
        "IDEA-2026-000005": ["CEO", "SIP pause"],
        "IDEA-2026-000006": ["CEO", "SIP"],
    }
    found = candidate_terms(texts, known={"sip"})
    assert set(found) == {"NCTO"}  # FolioSync is in two ideas, CEO is common, SIP is known
    assert found["NCTO"] == {"IDEA-2026-000001", "IDEA-2026-000002", "IDEA-2026-000003"}


def test_glossary_candidates_ignore_tags() -> None:
    texts = {f"IDEA-2026-00000{i}": ["Ask [[KFIN_EMPLOYEE_1]] about it"] for i in range(1, 5)}
    assert candidate_terms(texts, known=set()) == {}


def _item(
    proposal: dict[str, Any], corrected: list[str] | None = None, conf: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {"proposal": proposal, "corrected": corrected or [], "confidence": conf or {}}


def test_acceptance_counts_only_unchanged_high_confidence_proposals() -> None:
    items = [
        _item({"system": {"areas": ["AREA-ops"]}}, conf={"system.areas": 0.9}),
        _item({"system": {"areas": ["AREA-ops"]}}, ["system.areas"], {"system.areas": 0.95}),
        _item(
            {"system": {"areas": ["AREA-ops"]}}, conf={"system.areas": HIGH_BAND - 0.1}
        ),  # low band: left out
        _item({"best_same": "IDEA-2026-000009"}, conf={"match": 0.9}),
        _item({}, ["match"]),
    ]
    out = acceptance(items)
    assert out["accept_area_tags"] == {"window": 2, "accepted": 1, "rate": 0.5, "eligible": False}
    assert out["attach_to_cluster"]["rate"] == 1.0
    # every idea proposal without a closest match proposes "new": four here, and the desk changed the match once
    assert (out["mark_as_new"]["window"], out["mark_as_new"]["rate"]) == (4, 0.75)
    assert out["accept_scope"]["window"] == 0 and out["accept_scope"]["rate"] is None


def test_acceptance_window_stops_at_200_and_eligibility_needs_a_full_window() -> None:
    good = [_item({"system": {"areas": ["AREA-ops"]}}) for _ in range(WINDOW + 50)]
    out = acceptance(good)["accept_area_tags"]
    assert out["window"] == WINDOW and out["rate"] == 1.0 and out["eligible"] is True
    assert acceptance(good[:150])["accept_area_tags"]["eligible"] is False


@pytest.mark.parametrize(
    ("day", "kinds"),
    [
        (dt.date(2026, 11, 20), ["autonomy"]),  # a Friday
        (dt.date(2026, 11, 23), ["autonomy", "drift", "glossary"]),  # a Monday
        (dt.date(2026, 12, 1), ["autonomy", "canvas", "area_tags"]),
        (dt.date(2027, 1, 1), ["autonomy", "canvas", "area_tags", "calibration"]),
        (
            dt.date(2027, 3, 1),
            ["autonomy", "drift", "glossary", "canvas", "area_tags"],
        ),  # a Monday and the 1st
    ],
)
def test_learning_loops_due(day: dt.date, kinds: list[str]) -> None:
    assert due(day) == kinds


@pytest.mark.parametrize(
    ("day", "period", "start", "end"),
    [
        (dt.date(2026, 11, 20), "2026-Q4", dt.date(2026, 10, 1), dt.date(2027, 1, 1)),
        (dt.date(2027, 1, 1), "2027-Q1", dt.date(2027, 1, 1), dt.date(2027, 4, 1)),
        (dt.date(2027, 6, 30), "2027-Q2", dt.date(2027, 4, 1), dt.date(2027, 7, 1)),
    ],
)
def test_quarter_of(day: dt.date, period: str, start: dt.date, end: dt.date) -> None:
    assert quarter_of(day) == (period, start, end)


def test_lens_groups_are_plain_words_in_a_fixed_order() -> None:
    counts = group_counts(["scanned", "scanned", "picked", "in_garage", "closed", "declined", "draft"])
    assert list(counts) == [label for label, _ in STAGE_GROUPS]
    assert counts["With the review desk"] == 2 and counts["Picked"] == 1 and counts["Being built"] == 1
    assert counts["Shipped"] == 1 and counts["Parked or not taken up"] == 1
    assert sum(counts.values()) == 6  # drafts are never counted
    for label, _ in STAGE_GROUPS:
        for word in ("garage", "duplicate", "rejected", "already solved"):
            assert word not in label.lower()
