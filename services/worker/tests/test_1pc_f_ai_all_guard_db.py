"""DEC-143 (h), BLD-F111: on a server with no model route, the gateway refuses every agent with its own
`switched_off`, even with `ai.all` left on in the table, so the fake route never answers people. The call is logged as
a kill-switch refusal, as any switched-off call is, and the table's "on" is left for upgrade.sh to name. Once the
route is set, `ai.all` follows the same table. Synthetic text only; the route is a spy."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from core import killswitch
from core.config import get_settings
from gateway import core, limits
from gateway.routes import FAKE_SCRIPT, FakeRoute
from pii.detect import build_directory

SCOPE = "IDEA-2026-000412"
INPUTS = {
    "mode": "submission",
    "submission": {"one_line": "Nominee details keyed twice", "details": "Ops re-key the same details twice"},
}


class Spy(FakeRoute):
    def __init__(self) -> None:
        self.calls = 0

    def call(self, spec: Any, system: str, messages: list[dict[str, Any]], inputs: dict[str, Any]) -> Any:
        self.calls += 1
        return super().call(spec, system, messages, inputs)


@pytest.fixture
def gw(db: Any, company_repo: Any, monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[Any, Spy, Any]]:
    killswitch.clear_cache()
    limits.reset()
    FAKE_SCRIPT.clear()
    spy = Spy()
    monkeypatch.setattr(core, "get_route", lambda: spy)
    d = build_directory(db, company_repo)
    for name in ("LLM_MODE", "ANTHROPIC_API_KEY", "AWS_REGION"):
        monkeypatch.delenv(name, raising=False)
    yield db, spy, d
    FAKE_SCRIPT.clear()
    killswitch.clear_cache()
    get_settings.cache_clear()


def _server(monkeypatch: pytest.MonkeyPatch, **route: str) -> None:
    monkeypatch.setenv("APP_ENV", "uat")
    for name, value in route.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    killswitch.clear_cache()


def test_BLD_F111_the_gateway_refuses_on_a_server_with_no_model_route(
    gw: tuple[Any, Spy, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    db, spy, d = gw
    assert db.execute("SELECT state FROM kill_switches WHERE name = 'ai.all'").fetchone()["state"] == "on"
    _server(monkeypatch, LLM_MODE="fake")
    with pytest.raises(core.AgentSwitchedOff):
        core.run_agent("gatekeeper", INPUTS, SCOPE, conn=db, d=d)
    assert spy.calls == 0
    row = db.execute("SELECT outcome, error_code FROM llm_calls ORDER BY id DESC LIMIT 1").fetchone()
    assert (row["outcome"], row["error_code"]) == ("switched_off", "kill_switch")
    # The table is untouched: upgrade.sh reads it to say "ai.all is on but the app env file has no model route".
    assert db.execute("SELECT state FROM kill_switches WHERE name = 'ai.all'").fetchone()["state"] == "on"
    assert dict(killswitch.states(db, now=float("inf")))["ai.all"] == "on"


def test_BLD_F111_with_the_route_set_the_same_table_reads_on(
    gw: tuple[Any, Spy, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The guard lets `ai.all` follow the table once a route is set. Only the switch read is checked here: past it, a
    server's own rules apply (its vault refuses CI's placeholder key), and a full call is the dev and test path that
    test_b4_gateway.py already covers."""
    db, _spy, _d = gw
    _server(monkeypatch, LLM_MODE="bedrock")
    assert killswitch.is_on("ai.all", db) and killswitch.is_on_fresh("ai.all", db)
    killswitch.set_switch(db, "ai.all", "off", reason="Testing the route guard here", actor="REV-0001")
    assert not killswitch.is_on("ai.all", db) and not killswitch.is_on_fresh("ai.all", db)
    _server(monkeypatch, LLM_MODE="fake")
    killswitch.set_switch(db, "ai.all", "on", reason="Testing the route guard here", actor="REV-0001")
    assert not killswitch.is_on("ai.all", db) and not killswitch.is_on_fresh("ai.all", db)
    assert db.execute("SELECT state FROM kill_switches WHERE name = 'ai.all'").fetchone()["state"] == "on"
