"""DEC-143 (h), BLD-F111: the `ai.all` guard. On a server (any `APP_ENV` but dev and test) the worker reads `ai.all`
as off while no real model route is set, whatever the table says, so the fake route never answers people. The rule
is the deploy's own (`bootstrap.preflight ai-route-ready`). The table keeps its state for `list`, which upgrade.sh
reads. The Admin page asks `/internal/model-route` before it switches `ai.all` on. No database here: the table is a
stub (the gateway's refusal is in test_1pc_f_ai_all_guard_db.py, CI only)."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

import api.app as app_module
from core import killswitch
from core.config import get_settings

TOKEN = {"X-Internal-Token": "t" * 32}
ROUTE_NAMES = ("LLM_MODE", "ANTHROPIC_API_KEY", "AWS_REGION")
NO_ROUTE: list[dict[str, str]] = [
    {},  # LLM_MODE unset: the fake route
    {"LLM_MODE": "fake"},
    {"LLM_MODE": "anthropic"},  # no key
    {"LLM_MODE": "anthropic", "ANTHROPIC_API_KEY": "   "},
    {"LLM_MODE": "something-else"},
]
ROUTE: list[dict[str, str]] = [
    {"LLM_MODE": "anthropic", "ANTHROPIC_API_KEY": "test-key-not-real"},
    {"LLM_MODE": "bedrock"},
]

Env = Callable[..., None]


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> Iterator[Env]:
    monkeypatch.setenv("INTERNAL_API_TOKEN", "t" * 32)
    monkeypatch.setenv("SPEECH_ENGINE_URL", "")

    def set_env(app_env: str, route: dict[str, str]) -> None:
        for name in ROUTE_NAMES:
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv("APP_ENV", app_env)
        for name, value in route.items():
            monkeypatch.setenv(name, value)
        get_settings.cache_clear()

    yield set_env
    get_settings.cache_clear()
    killswitch.clear_cache()


def _table(monkeypatch: pytest.MonkeyPatch, **switches: str) -> None:
    """The switch table as the 10-second cache holds it, so nothing reads a database."""
    states = {name.replace("_", "."): state for name, state in switches.items()}
    monkeypatch.setitem(killswitch._cache, "states", states)
    monkeypatch.setitem(killswitch._cache, "at", time.monotonic())


class _Conn:
    """One switch row, for `is_on_fresh`; it records whether it was asked."""

    def __init__(self, state: str) -> None:
        self.state, self.asked = state, 0

    def execute(self, sql: str, params: Any = None) -> _Conn:
        self.asked += 1
        return self

    def fetchone(self) -> dict[str, str]:
        return {"state": self.state}


@pytest.mark.parametrize("app_env", ["uat", "prod", "staging", ""])
@pytest.mark.parametrize("route", NO_ROUTE)
def test_BLD_F111_on_a_server_with_no_model_route_ai_all_reads_off_and_the_table_keeps_its_state(
    env: Env, monkeypatch: pytest.MonkeyPatch, app_env: str, route: dict[str, str]
) -> None:
    env(app_env, route)
    _table(monkeypatch, ai_all="on", agent_gatekeeper="on", comms_email="on")
    assert killswitch.model_route_missing()
    assert not killswitch.is_on("ai.all")
    # Only `ai.all` is guarded: every other switch still reads the table.
    assert killswitch.is_on("agent.gatekeeper") and killswitch.is_on("comms.email")
    # The table's own state is kept: `list` and upgrade.sh's check read `states()`.
    assert killswitch.states()["ai.all"] == "on"
    fresh = _Conn("on")
    assert not killswitch.is_on_fresh("ai.all", fresh)  # type: ignore[arg-type]
    assert fresh.asked == 0  # refused before the table is read
    assert killswitch.is_on_fresh("agent.gatekeeper", _Conn("on"))  # type: ignore[arg-type]


@pytest.mark.parametrize("app_env", ["uat", "prod"])
@pytest.mark.parametrize("route", ROUTE)
def test_BLD_F111_with_a_model_route_ai_all_follows_the_table(
    env: Env, monkeypatch: pytest.MonkeyPatch, app_env: str, route: dict[str, str]
) -> None:
    env(app_env, route)
    assert not killswitch.model_route_missing()
    _table(monkeypatch, ai_all="on")
    assert killswitch.is_on("ai.all")
    assert killswitch.is_on_fresh("ai.all", _Conn("on"))  # type: ignore[arg-type]
    _table(monkeypatch, ai_all="off")
    assert not killswitch.is_on("ai.all")
    assert not killswitch.is_on_fresh("ai.all", _Conn("off"))  # type: ignore[arg-type]


@pytest.mark.parametrize("app_env", ["dev", "test"])
def test_BLD_F111_dev_and_test_keep_the_fake_route(
    env: Env, monkeypatch: pytest.MonkeyPatch, app_env: str
) -> None:
    env(app_env, {"LLM_MODE": "fake"})
    assert not killswitch.model_route_missing()
    _table(monkeypatch, ai_all="on")
    assert killswitch.is_on("ai.all")
    assert killswitch.is_on_fresh("ai.all", _Conn("on"))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("app_env", "route", "ready"),
    [
        ("uat", {"LLM_MODE": "fake"}, False),
        ("prod", {"LLM_MODE": "anthropic"}, False),
        ("prod", {"LLM_MODE": "anthropic", "ANTHROPIC_API_KEY": "test-key-not-real"}, True),
        ("uat", {"LLM_MODE": "bedrock"}, True),
        ("dev", {"LLM_MODE": "fake"}, True),
    ],
)
def test_BLD_F111_the_worker_tells_the_admin_page_whether_ai_all_may_go_on(
    env: Env, app_env: str, route: dict[str, str], ready: bool
) -> None:
    env(app_env, route)
    res = TestClient(app_module.app).get("/internal/model-route", headers=TOKEN)
    assert res.status_code == 200
    assert res.json() == {"ready": ready}


def test_BLD_F111_the_model_route_answer_needs_the_internal_token(env: Env) -> None:
    env("uat", {"LLM_MODE": "fake"})
    client = TestClient(app_module.app)
    wrong = {"X-Internal-Token": "x" * 32}
    assert client.get("/internal/model-route").status_code in (401, 403)
    assert client.get("/internal/model-route", headers=wrong).status_code in (401, 403)
