"""Matching inside the scan (B5): the card is matched (P3), the judge labels the candidates, and the submitter's
Find your crew list carries only the neutral summary, area, stage, colleague count and, for solutions, the
owning LOB (AT-B5-05); committee-only items appear only as "a related idea is with the review desk" (AT-B5-03);
`matching.show` off hides matches from the submitter but not from the review desk."""

from __future__ import annotations

from typing import Any

import pytest

from core import killswitch
from scan import pipeline
from scan.view import view
from tests.conftest import MATCH_TEXT as TEXT
from tests.test_b4_scan import canvas, scan_row, submitted

pytestmark = pytest.mark.stack

ALLOWED_CARD_KEYS = {
    "ref",
    "kind",
    "label",
    "heading",
    "summary",
    "area",
    "stage",
    "colleagues",
    "owning_lob",
}


def test_find_your_crew_shows_only_what_is_allowed(world: Any) -> None:
    db = world
    idea = submitted(db, canvas(TEXT + "."))
    assert pipeline.run(db, idea) == "done"
    assert scan_row(db, idea)["step"] == "done"
    agents = [r["agent"] for r in db.execute("SELECT agent FROM llm_calls ORDER BY id").fetchall()]
    assert agents == ["gatekeeper", "canvas-assist", "judge"]
    shown = view(db, idea, "real")
    assert shown is not None
    cards = shown["ready"]["matches"]
    real = [c for c in cards if c["kind"] != "with_desk"]
    assert real and all(set(c) == ALLOWED_CARD_KEYS for c in real)
    assert {c["kind"] for c in real} >= {"idea", "solution"}
    solution = next(c for c in real if c["kind"] == "solution")
    assert solution["heading"] == "Already running" and solution["owning_lob"]
    page = str(cards)
    for forbidden in (
        "IDEA-2026-000011",
        "SOL-0004",
        "Committee-only summary text",
        "re-check every SIP mandate",
    ):
        assert forbidden not in page  # no IDs, no other person's text, nothing from committee-only items
    assert {
        "ref": None,
        "kind": "with_desk",
        "label": "related",
        "heading": "A related idea is with the review desk",
    } in cards
    assert all(
        c["kind"] != "idea" or c["summary"] in ("Manual checks on SIP mandates delay registration", None)
        for c in real
    )


def test_matching_show_off_hides_matches_from_the_submitter_only(world: Any) -> None:
    db = world
    idea = submitted(db, canvas(TEXT + " again."))
    pipeline.run(db, idea)
    killswitch.set_switch(db, "matching.show", "off", reason="Testing the matching switch", actor="REV-0001")
    killswitch.clear_cache()
    shown = view(db, idea, "real")
    assert shown and shown["ready"]["matches"] == []
    result = pipeline.load_result(scan_row(db, idea))
    assert result["match"]["candidates"]  # the review desk still has the full list
