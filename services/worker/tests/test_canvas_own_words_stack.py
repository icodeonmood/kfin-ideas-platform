"""DEC-095, BLD-C020, on the stack: through `run_agent` with a scripted model. A suggestion the person's words do not
back is sent back once (BLD-158's single re-ask), then dropped; the call is logged by code only and not cached."""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from core import killswitch
from gateway import core, limits
from gateway.routes import FAKE_SCRIPT, FakeRoute
from pii.detect import build_directory
from review import service
from review.veto import desk_decisions
from tests.helpers import tables_containing
from tests.test_b6_review import desk  # noqa: F401  (the review desk fixture, shared)
from tests.test_canvas_own_words import answers, output, sent_for

pytestmark = pytest.mark.stack
SCOPE = "IDEA-2026-000977"
DETAILS = (  # plain words only, so tagging leaves the text as it is and the scripted quotes still match
    "Every morning the ops team re-keys about 40 switch requests that arrive by email into two screens. "
    "It takes two hours and the same requests often come back incomplete."
)
INVENTED = "saves us five lakh a year"


class Spy(FakeRoute):
    def __init__(self) -> None:
        self.calls: list[list[dict[str, Any]]] = []

    def call(self, spec: Any, system: str, messages: list[dict[str, Any]], inputs: dict[str, Any]) -> Any:
        self.calls.append(messages)
        return super().call(spec, system, messages, inputs)


@pytest.fixture
def gw(db: Any, company_repo: Any, monkeypatch: Any) -> Any:
    killswitch.clear_cache()
    limits.reset()
    FAKE_SCRIPT.clear()
    spy = Spy()
    monkeypatch.setattr(core, "get_route", lambda: spy)
    yield db, spy, build_directory(db, company_repo)
    FAKE_SCRIPT.clear()
    killswitch.clear_cache()


def _case(**suggest: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    a = answers(details=DETAILS)
    out = output(a, **suggest)
    out["neutral_summary"] = "Switch requests that arrive by email are re-keyed by hand every morning."
    out["evidence"] = {
        k: v for k, v in out["evidence"].items() if k not in ("kind", "one_line", "neutral_summary")
    }
    out["evidence"]["kind"] = ["the same requests often come back incomplete"]
    out["evidence"]["one_line"] = ["re-keys about 40 switch requests that arrive by email"]
    out["evidence"]["neutral_summary"] = ["re-keys about 40 switch requests that arrive by email"]
    return sent_for(a), out


def test_an_unsupported_figure_is_asked_again_once_then_dropped_and_logged_by_code_only(gw: Any) -> None:
    db, spy, d = gw
    sent, bad = _case(value__estimate__inr_saved_per_year=(500000, [INVENTED]))
    FAKE_SCRIPT.extend([bad, copy.deepcopy(bad)])  # the model repeats itself on the re-ask
    out = core.run_agent("canvas-assist", sent, SCOPE, conn=db, d=d)

    assert len(spy.calls) == 2  # one re-ask, no more (BLD-158)
    reask = spy.calls[1][2]["content"]
    assert "value.estimate.inr_saved_per_year" in reask and INVENTED not in reask
    assert out.outcome == "ok_after_retry" and out.dropped == ["value.estimate.inr_saved_per_year"]
    assert out.data["value"]["estimate"]["inr_saved_per_year"] is None
    assert "value.estimate.inr_saved_per_year" not in out.data["evidence"]
    assert out.data["evidence"]["one_line"] == ["re-keys about 40 switch requests that arrive by email"]

    row = db.execute(
        "SELECT * FROM llm_calls WHERE ref_id = %s ORDER BY id DESC LIMIT 1", (SCOPE,)
    ).fetchone()
    assert row["outcome"] == "ok_after_retry" and row["error_code"] == core.DROPPED
    assert tables_containing(db, INVENTED) == [] and tables_containing(db, DETAILS[:60]) == []

    # Not cached: the same input asks the model again.
    FAKE_SCRIPT.extend([bad, copy.deepcopy(bad)])
    core.run_agent("canvas-assist", sent, SCOPE, conn=db, d=d)
    assert len(spy.calls) == 4


def test_a_corrected_second_answer_is_used_as_it_is(gw: Any) -> None:
    db, _spy, d = gw
    sent, bad = _case(value__estimate__inr_saved_per_year=(500000, [INVENTED]))
    _, good = _case()
    FAKE_SCRIPT.extend([bad, good])
    out = core.run_agent("canvas-assist", sent, SCOPE + "1", conn=db, d=d)
    assert out.outcome == "ok_after_retry" and out.dropped == [] and out.data == good


def test_dropping_is_not_enough_when_another_check_fails(gw: Any) -> None:
    db, _spy, d = gw
    sent, bad = _case(value__estimate__inr_saved_per_year=(500000, [INVENTED]))
    bad["system"]["areas"] = ["AREA-not-offered"]
    FAKE_SCRIPT.extend([bad, copy.deepcopy(bad)])
    with pytest.raises(core.AgentFailed) as failed:
        core.run_agent("canvas-assist", sent, SCOPE + "2", conn=db, d=d)
    assert failed.value.code == "invalid_output"


# ---- the review desk writes the short summary (BLD-C027) and nothing falls back to the person's words (C1) --------


SUMMARY = "Mandate checks done by hand slow down SIP registrations for investors."
OWN_WORDS = (
    "Zephyrine ledger drift keeps tripping the quarterly courier reconciliation"  # synthetic, distinctive
)


def test_the_review_desk_writes_the_summary_through_the_checks_and_the_audit_has_no_text(desk: Any) -> None:  # noqa: F811
    db, item = desk["db"], desk["item"]
    out = service.act(db, item, desk["r1"], {"action": "summary", "neutral_summary": SUMMARY})
    assert out["stage"]
    card = db.execute("SELECT canvas FROM ideas WHERE idea_id = %s", (desk["idea_id"],)).fetchone()["canvas"]
    assert card["neutral_summary"] == SUMMARY and card["provenance"]["neutral_summary"] == "reviewer"
    assert "neutral_summary" not in (card.get("evidence") or {})
    audit = db.execute(
        "SELECT actor, before, after, reason FROM audit_log WHERE action = 'review.neutral_summary' "
        "AND entity = %s ORDER BY id DESC LIMIT 1",
        (f"idea:{desk['idea_id']}",),
    ).fetchone()
    assert audit["actor"].startswith("REV-") and audit["after"] == {"length": len(SUMMARY)}
    assert "Mandate" not in json.dumps([audit["before"], audit["after"], audit["reason"]])
    event = db.execute(
        "SELECT payload FROM outbox WHERE aggregate_id = %s AND event_type = 'idea.reviewed' ORDER BY id DESC LIMIT 1",
        (desk["idea_id"],),
    ).fetchone()
    assert event["payload"]["history"][0]["event"] == "summary_written"  # the idea file is written again


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("Too short", "text_too_short"),
        ("Call 9876543210 to hear how mandate checks slow down registrations", "personal_data"),
        ("Northwind Mutual Fund waits two days for every SIP mandate check", "summary_not_neutral"),
        (" ".join(["word"] * 26), "summary_too_long"),
    ],
)
def test_a_summary_with_personal_data_names_or_too_many_words_is_refused(
    desk: Any,  # noqa: F811
    text: str,
    code: str,
) -> None:
    with pytest.raises(service.ActionRefused) as refused:
        service.act(desk["db"], desk["item"], desk["r1"], {"action": "summary", "neutral_summary": text})
    assert refused.value.code == code


def test_with_the_checks_switched_off_no_summary_is_written(desk: Any) -> None:  # noqa: F811
    db = desk["db"]
    killswitch.set_switch(db, "ai.all", "off", reason="test: checks unavailable", actor="process:test")
    killswitch.clear_cache()
    try:
        with pytest.raises(service.ActionRefused) as refused:
            service.act(db, desk["item"], desk["r1"], {"action": "summary", "neutral_summary": SUMMARY})
        assert refused.value.status == 503 and refused.value.code == "checks_unavailable"
    finally:
        killswitch.set_switch(db, "ai.all", "on", reason="test: put back", actor="process:test")
        killswitch.clear_cache()


def test_an_empty_summary_never_shows_the_persons_words_to_anyone_else(desk: Any) -> None:  # noqa: F811
    """Non-negotiable 7: with the short summary left blank, every reader shows a placeholder or nothing, never the
    person's one line, details or another field."""
    from comms.render import _delivery_label
    from okf.frontmatter import parse
    from repo_writer.render import render_idea
    from views.common import SUMMARY_PENDING, public_card, taxonomy_names
    from views.wall import clear_cache, wall

    db, idea_id = desk["db"], desk["idea_id"]
    service.act(db, desk["item"], desk["r1"], {"action": "decide"})  # reviewed: a stage everyone may see
    db.execute(
        "UPDATE ideas SET canvas = canvas || jsonb_build_object('neutral_summary', '', 'one_line', %s::text, "
        "'details', %s::text) WHERE idea_id = %s",
        (OWN_WORDS, OWN_WORDS + " every week.", idea_id),
    )
    idea = dict(db.execute("SELECT * FROM ideas WHERE idea_id = %s", (idea_id,)).fetchone())
    areas, _ = taxonomy_names()
    card = public_card(db, idea, areas)
    assert card is not None and card["summary"] == SUMMARY_PENDING  # still on the wall, with a placeholder
    clear_cache()
    assert "Zephyrine" not in json.dumps(wall(db), default=str)
    decisions = desk_decisions(db)
    mine = [d for d in decisions["decisions"] if d["idea_id"] == idea_id]
    assert mine and mine[0]["summary"] is None  # the screen shows its own placeholder
    assert _delivery_label(db, idea_id) == idea_id
    meta = parse(render_idea(idea, history=[], verified=[], generated_by="test")).meta or {}
    assert meta["description"] == SUMMARY_PENDING  # never the one line, as before (BLD-C027)
    assert not (meta.get("kfin") or {}).get("neutral_summary")  # so the index gives match cards no summary
