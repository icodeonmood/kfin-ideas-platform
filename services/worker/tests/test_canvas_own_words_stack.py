"""DEC-095, BLD-C020, on the stack: through `run_agent` with a scripted model. A suggestion the person's words do not
back is sent back once (BLD-158's single re-ask), then dropped; the call is logged by code only and not cached."""

from __future__ import annotations

import copy
from typing import Any

import pytest

from core import killswitch
from gateway import core, limits
from gateway.routes import FAKE_SCRIPT, FakeRoute
from pii.detect import build_directory
from tests.helpers import tables_containing
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
