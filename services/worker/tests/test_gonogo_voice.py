"""Go/no-go voice rows under DEC-108: voice is on at launch through Sarvam; the on-server engine behind the
isolated service is an allowed fallback; off is a row to confirm, never "off as expected" (BLD-A185)."""

from __future__ import annotations

from gonogo.__main__ import HOSTED, OFF_BY_DESIGN, VOICE, voice_rows


def _states(rows: list[dict[str, str]]) -> dict[str, str]:
    return {r["criterion"]: r["state"] for r in rows}


def test_voice_off_is_a_row_to_confirm_not_off_as_expected() -> None:
    rows, why = voice_rows(False, False, "fake", "", "")
    assert _states(rows) == {VOICE: "confirm", HOSTED: "met"}
    assert why == []
    assert "capture.voice" not in OFF_BY_DESIGN and "speech.hosted" not in OFF_BY_DESIGN


def test_voice_on_through_sarvam_with_its_switch_and_approval_is_met() -> None:
    rows, why = voice_rows(True, True, "sarvam", "", "DEC-108")
    assert _states(rows) == {VOICE: "met", HOSTED: "met"}
    assert why == []


def test_sarvam_with_the_hosted_switch_off_refuses_every_recording() -> None:
    rows, why = voice_rows(True, False, "sarvam", "", "DEC-108")
    assert _states(rows) == {VOICE: "not met", HOSTED: "confirm"}
    assert why == ["voice on without a working route"]


def test_hosted_on_without_an_approval_reference_is_not_met() -> None:
    rows, why = voice_rows(True, True, "sarvam", "", "  ")
    assert _states(rows) == {VOICE: "not met", HOSTED: "not met"}
    assert len(why) == 2


def test_the_on_server_engine_behind_the_isolated_service_is_an_allowed_fallback() -> None:
    rows, why = voice_rows(True, False, "local", "http://speech:8000", "")
    assert _states(rows) == {VOICE: "met", HOSTED: "met"}
    assert why == []


def test_voice_on_the_fake_route_is_not_met() -> None:
    rows, why = voice_rows(True, False, "fake", "", "")
    assert _states(rows)[VOICE] == "not met"
    assert why == ["voice on without a working route"]
