"""Go/no-go and smoke voice rules under DEC-108: voice is on at launch through Sarvam; the on-server engine behind the
isolated service is an allowed fallback; off is a row to confirm, never "off as expected" (BLD-A185)."""

from __future__ import annotations

import pytest

from core.config import Settings
from core.speech_route import hosted_problem, key_set, voice_problem
from gonogo.__main__ import HOSTED, OFF_BY_DESIGN, VOICE, voice_rows


def _states(rows: list[dict[str, str]]) -> dict[str, str]:
    return {r["criterion"]: r["state"] for r in rows}


def test_voice_off_is_a_row_to_confirm_not_off_as_expected() -> None:
    rows, why = voice_rows(False, False, "fake", "", "", False)
    assert _states(rows) == {VOICE: "confirm", HOSTED: "met"}
    assert why == []
    assert "capture.voice" not in OFF_BY_DESIGN and "speech.hosted" not in OFF_BY_DESIGN


def test_voice_on_through_sarvam_with_switch_approval_and_key_is_met() -> None:
    rows, why = voice_rows(True, True, "sarvam", "", "DEC-108", True)
    assert _states(rows) == {VOICE: "met", HOSTED: "met"}
    assert why == []


def test_sarvam_without_its_key_is_not_met_and_rules_out_mode_a() -> None:
    rows, why = voice_rows(True, True, "sarvam", "", "DEC-108", False)
    assert _states(rows) == {VOICE: "not met", HOSTED: "not met"}
    assert "key" in rows[0]["evidence"] and len(why) == 2


def test_sarvam_with_the_hosted_switch_off_refuses_every_recording() -> None:
    rows, why = voice_rows(True, False, "sarvam", "", "DEC-108", True)
    assert _states(rows) == {VOICE: "not met", HOSTED: "confirm"}
    assert why == ["voice on without a working route"]


def test_hosted_on_without_an_approval_reference_is_not_met() -> None:
    rows, why = voice_rows(True, True, "sarvam", "", "  ", True)
    assert _states(rows) == {VOICE: "not met", HOSTED: "not met"}
    assert len(why) == 2


def test_hosted_on_without_approval_is_not_met_even_on_the_local_fallback() -> None:
    rows, why = voice_rows(True, True, "local", "http://speech:8000", "", True)
    assert _states(rows) == {VOICE: "met", HOSTED: "not met"}
    assert why == ["hosted speech on without its approval reference or key"]


def test_the_on_server_engine_behind_the_isolated_service_is_an_allowed_fallback() -> None:
    rows, why = voice_rows(True, False, "local", "http://speech:8000", "", False)
    assert _states(rows) == {VOICE: "met", HOSTED: "met"}
    assert why == []


@pytest.mark.parametrize("mode", ["fake", "", "whisper"])
def test_voice_on_the_fake_or_an_unknown_route_is_not_met(mode: str) -> None:
    rows, why = voice_rows(True, False, mode, "", "", False)
    assert _states(rows)[VOICE] == "not met"
    assert why == ["voice on without a working route"]


def test_the_shared_rules_the_smoke_check_uses() -> None:
    assert voice_problem(False, False, "fake", "", "", False) is None
    assert voice_problem(True, True, "sarvam", "", "DEC-108", True) is None
    assert voice_problem(True, False, "local", "", "", False) is not None
    assert hosted_problem(False, "", False) is None
    assert hosted_problem(True, "DEC-108", False) is not None
    assert hosted_problem(True, "DEC-108", True) is None


def test_the_key_is_read_as_set_or_missing_only() -> None:
    # lane C renames the setting to sarvam_api_key; the rule reads whichever this Settings has
    field = "sarvam_api_key" if "sarvam_api_key" in Settings.model_fields else "speech_hosted_key"
    assert key_set(Settings().model_copy(update={field: ""})) is False
    assert key_set(Settings().model_copy(update={field: "synthetic-test-key"})) is True
