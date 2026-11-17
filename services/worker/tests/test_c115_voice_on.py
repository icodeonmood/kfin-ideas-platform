"""BLD-C115 (DEC-108; non-negotiable 2's voice exception, confirmed with the DPO's approval): voice is on at launch.
The watch switches `capture.voice` and `speech.hosted` off if SARVAM_API_KEY is missing outside dev and test; the
go/no-go rows report the key present or absent (never its value), with a test for each row state; the key is the
worker's alone in compose and deploy.sh. The migration's effect is a stack test."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from core import watch
from core.config import get_settings
from gonogo.__main__ import HOSTED as HOSTED_ROW
from gonogo.__main__ import OFF_BY_DESIGN, voice_rows
from gonogo.__main__ import VOICE as VOICE_ROW
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


# ---- the go/no-go rows (lane A's `core/speech_route` is the one answer; this lane adds the key guard's row) ----


def test_BLD_C115_switched_off_by_the_key_guard_says_exactly_that() -> None:
    rows, why = voice_rows(
        False, False, "sarvam", "", "DEC-108", False, voice_reason=KEY_MISSING, hosted_reason=KEY_MISSING
    )
    got = {r["criterion"]: (r["state"], r["evidence"]) for r in rows}
    assert got[VOICE_ROW] == ("not met", "off: Sarvam key missing (automatic)")
    assert got[HOSTED_ROW] == ("not met", "off: Sarvam key missing (automatic)")
    assert len(why) == 2


def test_BLD_C115_on_with_the_route_the_approval_and_the_key_is_met() -> None:
    rows, why = voice_rows(True, True, "sarvam", "", "DEC-108", True)
    assert [r["state"] for r in rows] == ["met", "met"] and why == []
    rows, why = voice_rows(True, True, "sarvam", "", "", True)  # BLD-C117 (6): the approval is checked
    assert "met" not in {r["state"] for r in rows if r["criterion"] == HOSTED_ROW} and why


def test_BLD_C115_voice_is_not_off_by_design_any_more() -> None:
    # Voice left the off-by-design list with DEC-108. Still off by design: the file black-out (`files.blackout`,
    # DEC-107 and BLD-C064) until black-out passes review, and L-DRAFT.channels' intake (`intake.email`,
    # `intake.teams`, DEC-105 and BLD-C077) until IT gives the mailbox and the Teams app.
    assert "capture.voice" not in OFF_BY_DESIGN and "speech.hosted" not in OFF_BY_DESIGN
    assert set(OFF_BY_DESIGN) == {"intake.email", "intake.teams", "files.blackout"}


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
    assert (
        'export SPEECH_HOSTED_APPROVAL="${approval:-DEC-108}"' in script
    )  # DEC-108 unless the file names another
    uat_worker = _compose("uat/compose.uat.yml")["services"]["worker"]["environment"]
    assert uat_worker["SPEECH_HOSTED_APPROVAL"] == "${SPEECH_HOSTED_APPROVAL:-DEC-108}"
    assert uat_worker["SPEECH_MODE"] == "${SPEECH_MODE:-sarvam}"
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


def _up(name: str) -> str:
    sql = (ROOT / "db" / "migrations" / name).read_text()
    return sql.split("-- migrate:up", 1)[1].split("-- migrate:down", 1)[0]


@pytest.mark.stack
def test_BLD_C115_lane_as_reasons_then_ours_leave_both_switches_on_and_never_undo_a_switch_off() -> None:
    """Both migrations in order, from the seeded DEC-096 state, inside a transaction that is rolled back (nothing
    is left behind): lane A's DEC-108 reasons (20261122100500), then ours (20261122300530), find both switches on.
    A switch the watch has turned off since stays off."""
    import psycopg
    from psycopg.rows import dict_row

    seed = (
        "UPDATE kill_switches SET state = 'off', changed_by = 'migration', reason = CASE name "
        "WHEN 'capture.voice' THEN 'Off until IT deploys the isolated speech service and the memory, InfoSec agrees "
        "to the microphone and the model, and the DPO''s privacy notice covers voice notes (DEC-096)' "
        "ELSE 'Off until InfoSec and the DPO approve a hosted route (DEC-096)' END "
        "WHERE name IN ('capture.voice', 'speech.hosted')"
    )
    lane_a, ours = _up("20261122100500_voice_on_reasons.sql"), _up("20261122300530_voice_on_launch.sql")

    def states(conn: Any) -> dict[str, str]:
        rows = conn.execute(
            "SELECT name, state FROM kill_switches WHERE name IN ('capture.voice', 'speech.hosted')"
        ).fetchall()
        return {r["name"]: r["state"] for r in rows}

    with psycopg.connect(get_settings().database_url, row_factory=dict_row) as conn:
        try:
            conn.execute(seed)
            conn.execute(lane_a)
            conn.execute(ours)
            assert states(conn) == {"capture.voice": "on", "speech.hosted": "on"}
            conn.execute(seed)
            conn.execute(
                "UPDATE kill_switches SET changed_by = 'process:watch', reason = %s WHERE name = 'speech.hosted'",
                (KEY_MISSING,),
            )
            conn.execute(lane_a)
            conn.execute(ours)
            assert states(conn) == {"capture.voice": "on", "speech.hosted": "off"}
        finally:
            conn.rollback()
