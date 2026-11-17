"""BLD-C115 (DEC-108; non-negotiable 2's voice exception, confirmed with the DPO's approval): voice is on at launch.
The watch switches `capture.voice` and `speech.hosted` off if SARVAM_API_KEY is missing outside dev and test; the
go/no-go rows report the key present or absent (never its value), with a test for each row state; the key is the
worker's alone in compose and deploy.sh. The migration's effect is a stack test."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from core import watch
from core.config import get_settings
from gonogo.__main__ import HOSTED_ROW, OFF_BY_DESIGN, VOICE_ROW, voice_rows
from tests.test_compose_speech import _compose

ROOT = Path(__file__).resolve().parents[3]
KEY_MISSING = "Sarvam key missing (automatic)"


# ---- the watch ------------------------------------------------------------------------------------------------


@pytest.fixture
def flips(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    seen: list[tuple[str, str]] = []

    def off(conn: Any, name: str, reason: str, actor: str = watch.ACTOR) -> bool:
        seen.append((name, reason))
        return True

    monkeypatch.setattr(watch, "switch_off", off)
    return seen


def _env(monkeypatch: pytest.MonkeyPatch, **env: str) -> None:
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    get_settings.cache_clear()


def test_BLD_C115_a_missing_key_switches_voice_and_hosted_speech_off(
    monkeypatch: pytest.MonkeyPatch, flips: list[tuple[str, str]]
) -> None:
    _env(monkeypatch, APP_ENV="uat", SPEECH_MODE="sarvam", SARVAM_API_KEY="")
    try:
        assert watch.Watch.speech_route(object()) is True  # type: ignore[arg-type]
    finally:
        _env(monkeypatch, APP_ENV="test")
    assert flips == [("capture.voice", KEY_MISSING), ("speech.hosted", KEY_MISSING)]
    assert watch.SARVAM_KEY_MISSING == KEY_MISSING


@pytest.mark.parametrize(
    "env",
    [
        {"APP_ENV": "uat", "SPEECH_MODE": "sarvam", "SARVAM_API_KEY": "synthetic-key"},
        {"APP_ENV": "test", "SPEECH_MODE": "sarvam", "SARVAM_API_KEY": ""},  # dev and test: no key needed
    ],
)
def test_BLD_C115_with_the_key_or_in_test_nothing_is_switched(
    monkeypatch: pytest.MonkeyPatch, flips: list[tuple[str, str]], env: dict[str, str]
) -> None:
    _env(monkeypatch, **env)
    try:
        assert watch.Watch.speech_route(object()) is False  # type: ignore[arg-type]
    finally:
        _env(monkeypatch, APP_ENV="test")
    assert flips == []


# ---- the go/no-go rows ----------------------------------------------------------------------------------------


def _s(**kw: str) -> SimpleNamespace:
    base = {"speech_mode": "sarvam", "sarvam_api_key": "synthetic-key", "speech_hosted_approval": "DEC-108",
            "speech_engine_url": ""}  # fmt: skip
    base.update(kw)
    return SimpleNamespace(**base)


ON = {"state": "on", "reason": "On at launch (DEC-108)"}


def _states(rows: list[dict[str, str]]) -> dict[str, tuple[str, str]]:
    return {r["criterion"]: (r["state"], r["evidence"]) for r in rows}


def test_BLD_C115_both_on_with_the_key_are_met_and_never_print_the_key() -> None:
    rows, why = voice_rows(_s(), ON, ON)
    got = _states(rows)
    assert got[VOICE_ROW] == ("met", "on; SPEECH_MODE sarvam; Sarvam key present")
    assert got[HOSTED_ROW][0] == "met" and "non-negotiable 2's voice exception" in got[HOSTED_ROW][1]
    assert "DPO's approval" in got[HOSTED_ROW][1] and "approval DEC-108" in got[HOSTED_ROW][1]
    assert why == [] and "synthetic-key" not in str(rows)


def test_BLD_C115_switched_off_by_the_watch_says_exactly_that() -> None:
    off = {"state": "off", "reason": KEY_MISSING}
    rows, why = voice_rows(_s(sarvam_api_key=""), off, off)
    got = _states(rows)
    assert got[VOICE_ROW] == ("not met", "off: Sarvam key missing (automatic)")
    assert got[HOSTED_ROW] == ("not met", "off: Sarvam key missing (automatic)")
    assert len(why) == 2


def test_BLD_C115_on_without_the_key_is_not_met() -> None:
    rows, why = voice_rows(_s(sarvam_api_key=""), ON, ON)
    got = _states(rows)
    assert got[VOICE_ROW][0] == "not met" and "Sarvam key absent" in got[VOICE_ROW][1]
    assert got[HOSTED_ROW][0] == "not met" and "Sarvam key absent" in got[HOSTED_ROW][1]
    assert why == ["voice notes on without the Sarvam key", "hosted speech on without the Sarvam key"]


def test_BLD_C115_off_for_another_reason_shows_it_with_the_key_state() -> None:
    off = {"state": "off", "reason": "Automatic: Sarvam error rate above 20% over 15 minutes (DEC-108)"}
    rows, _ = voice_rows(_s(), ON, off)
    assert _states(rows)[HOSTED_ROW] == (
        "not met",
        "off: Automatic: Sarvam error rate above 20% over 15 minutes (DEC-108); Sarvam key present",
    )
    rows, _ = voice_rows(_s(), None, None)
    assert _states(rows)[VOICE_ROW] == ("not met", "off: no switch row; Sarvam key present")


def test_BLD_C115_hosted_on_without_the_approval_is_not_met() -> None:
    rows, why = voice_rows(_s(speech_hosted_approval=""), ON, ON)
    assert (
        _states(rows)[HOSTED_ROW][0] == "not met" and "hosted speech on without its approval reference" in why
    )


@pytest.mark.parametrize(
    ("mode", "url", "state"),
    [("local", "http://speech:8300", "confirm"), ("fake", "", "not met"), ("local", "", "not met")],
)
def test_BLD_C115_other_routes_with_voice_on(mode: str, url: str, state: str) -> None:
    rows, _ = voice_rows(_s(speech_mode=mode, speech_engine_url=url), ON, ON)
    assert _states(rows)[VOICE_ROW][0] == state


def test_BLD_C115_nothing_is_off_by_design_any_more() -> None:
    assert OFF_BY_DESIGN == {}


# ---- the key is the worker's alone ----------------------------------------------------------------------------


def test_BLD_C115_compose_gives_the_key_to_the_worker_and_blanks_it_for_the_web_app() -> None:
    for name in ("docker-compose.yml", "uat/compose.uat.yml"):
        services = _compose(name)["services"]
        assert services["web"]["environment"]["SARVAM_API_KEY"] == "", name
        assert services["worker"]["environment"]["SARVAM_API_KEY"] == "${SARVAM_API_KEY:-}", name
        assert "SARVAM_API_KEY" not in (services.get("speech", {}).get("environment") or {}), name


def test_BLD_C115_deploy_refuses_the_key_in_the_app_env_file() -> None:
    script = (ROOT / "scripts" / "uat" / "deploy.sh").read_text()
    assert '[[ -z "$(value SARVAM_API_KEY "$APP_ENV_FILE")" ]]' in script
    assert '[[ -n "$(value SARVAM_API_KEY "$DB_ENV_FILE")" ]]' in script
    example = (ROOT / ".env.example").read_text()
    assert "SPEECH_HOSTED_APPROVAL=DEC-108" in example
    assert not any(line.startswith("SARVAM_API_KEY=") for line in example.splitlines())


# ---- the migration, against the running stack ----------------------------------------------------------------


@pytest.mark.stack
def test_BLD_C115_voice_and_hosted_speech_are_on_with_audited_reasons() -> None:
    from core.db import connect

    with connect(autocommit=True) as db:
        rows = {
            r["name"]: r
            for r in db.execute(
                "SELECT name, state, reason FROM kill_switches WHERE name IN ('capture.voice', 'speech.hosted')"
            ).fetchall()
        }
        audits = db.execute(
            "SELECT entity FROM audit_log WHERE actor = 'migration' AND reason LIKE 'On at launch%%DEC-108%%'"
        ).fetchall()
    # Other stack tests switch voice off and put it back with their own reasons, so the migration's audit rows are
    # the evidence; the states are on unless a test is mid-way.
    assert rows["capture.voice"]["state"] == "on" and rows["speech.hosted"]["state"] == "on"
    assert {a["entity"] for a in audits} >= {"kill_switch:capture.voice", "kill_switch:speech.hosted"}
