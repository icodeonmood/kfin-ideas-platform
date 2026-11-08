"""The judge through the gateway (B5, AT-B5-04 harness): one result per candidate, cids copied, input order,
reasons of 25 words or fewer, best_same consistent; anything else is sent back once, then refused."""

from __future__ import annotations

from typing import Any

import pytest

from core import killswitch
from gateway import core, limits
from gateway.routes import FAKE_SCRIPT
from pii.detect import build_directory

pytestmark = pytest.mark.stack
SCOPE = "IDEA-2026-000555"
CARD = {
    "kind": "problem",
    "one_line": "Ops re-check SIP mandates by hand",
    "details": "Bank fields are often blank.",
}
CANDS = [
    {
        "cid": "CL-0012",
        "type": "cluster",
        "title": "Manual checks on SIP forms",
        "summary": "Ops re-check SIP mandates by hand",
    },
    {"cid": "IDEA-2026-000201", "type": "idea", "title": "Canteen seating", "summary": "Cramped at lunch"},
]


@pytest.fixture
def ctx(db: Any, company_repo: Any) -> Any:
    killswitch.clear_cache()
    limits.reset()
    FAKE_SCRIPT.clear()
    yield db, build_directory(db, company_repo)
    FAKE_SCRIPT.clear()


def run(db: Any, d: Any) -> Any:
    return core.run_agent(
        "judge", {"card": CARD, "candidates": CANDS, "past_corrections": []}, SCOPE, conn=db, d=d
    )


def test_every_candidate_labelled_in_order(ctx: Any) -> None:
    db, d = ctx
    out = run(db, d)
    assert [r["cid"] for r in out.data["results"]] == ["CL-0012", "IDEA-2026-000201"]
    assert out.data["results"][0]["label"] == "same" and out.data["best_same"] == "CL-0012"
    assert out.data["results"][1]["label"] == "different"


def test_wrong_order_or_long_reasons_are_sent_back_then_refused(ctx: Any) -> None:
    db, d = ctx
    good = {"cid": "CL-0012", "label": "same", "reason": "Same cause.", "confidence": 0.9}
    other = {"cid": "IDEA-2026-000201", "label": "different", "reason": "Other topic.", "confidence": 0.9}
    FAKE_SCRIPT.extend(
        [
            {"results": [other, good], "best_same": "CL-0012"},
            {"results": [good, other], "best_same": "CL-0012"},
        ]
    )
    assert run(db, d).outcome == "ok_after_retry"
    long = {**good, "reason": " ".join(["word"] * 30)}
    FAKE_SCRIPT.extend([{"results": [long, other], "best_same": None}] * 2)
    with pytest.raises(core.AgentFailed):
        core.run_agent(
            "judge",
            {"card": {**CARD, "details": "x"}, "candidates": CANDS, "past_corrections": []},
            SCOPE,
            conn=db,
            d=d,
        )
    FAKE_SCRIPT.extend(
        [{"results": [good, other], "best_same": "IDEA-2026-000201"}] * 2
    )  # best_same not 'same'
    with pytest.raises(core.AgentFailed):
        core.run_agent(
            "judge",
            {"card": {**CARD, "details": "y"}, "candidates": CANDS, "past_corrections": []},
            SCOPE,
            conn=db,
            d=d,
        )
