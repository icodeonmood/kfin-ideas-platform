"""DEC-096: the speech route. Fake in dev and tests; the engine on KFin's own server needs its image and model
files; a hosted route never runs without BOTH its approval reference and its switch (raw voice cannot be tagged
before it leaves, non-negotiables 1 and 2). No stack needed: switches and settings are patched here."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from core.config import get_settings
from gateway import speech
from voice import service

WEBM = b"\x1a\x45\xdf\xa3" + bytes(16)


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    def apply(**env: str) -> None:
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        get_settings.cache_clear()
        speech._engine = None

    yield apply
    get_settings.cache_clear()
    speech._engine = None


def switches(monkeypatch: pytest.MonkeyPatch, **on: bool) -> None:
    def state(name: str, conn: object = None) -> bool:
        return on.get(name.replace(".", "_"), False)

    monkeypatch.setattr(speech.killswitch, "is_on", state)
    monkeypatch.setattr(speech.killswitch, "is_on_fresh", state)


def test_fake_reads_the_text_a_synthetic_recording_carries(settings: Any) -> None:
    settings(SPEECH_MODE="fake")
    got = speech.transcribe(WEBM + speech.FAKE_MARKER + b"Forms are typed twice at the branch.", "audio/webm")
    assert got.text == "Forms are typed twice at the branch."


def test_fake_gives_a_fixed_sample_for_any_other_recording(settings: Any) -> None:
    settings(SPEECH_MODE="fake")
    assert speech.transcribe(WEBM, "audio/webm").text == speech.FAKE_SAMPLE


def test_the_local_engine_needs_its_image_and_never_fetches_a_model(settings: Any) -> None:
    settings(SPEECH_MODE="local", SPEECH_LOCAL_ENGINE="faster-whisper", SPEECH_MODEL_PATH="")
    with pytest.raises(speech.SpeechUnavailable) as exc:
        speech.transcribe(WEBM, "audio/webm")
    assert exc.value.code in {"engine_not_installed", "model_path_missing"}


def test_indic_conformer_is_coming_soon(settings: Any) -> None:
    settings(SPEECH_MODE="local", SPEECH_LOCAL_ENGINE="indic-conformer")
    with pytest.raises(speech.SpeechUnavailable) as exc:
        speech.transcribe(WEBM, "audio/webm")
    assert exc.value.code == "engine_coming_soon"


def test_an_unknown_mode_refuses(settings: Any) -> None:
    settings(SPEECH_MODE="somewhere-else")
    with pytest.raises(speech.SpeechUnavailable) as exc:
        speech.transcribe(WEBM, "audio/webm")
    assert exc.value.code == "unknown_mode"


@pytest.mark.parametrize(
    ("approval", "switch_on", "code"),
    [
        ("", False, "hosted_not_approved"),
        ("", True, "hosted_not_approved"),  # the switch alone is not enough
        ("INFOSEC-2026-017 / DPO-2026-004", False, "hosted_switched_off"),  # nor the approval alone
    ],
)
def test_a_hosted_route_refuses_without_both_its_approval_and_its_switch(
    settings: Any, monkeypatch: pytest.MonkeyPatch, approval: str, switch_on: bool, code: str
) -> None:
    settings(SPEECH_MODE="sarvam", SPEECH_HOSTED_APPROVAL=approval, SPEECH_HOSTED_KEY="synthetic-test-key")
    switches(monkeypatch, speech_hosted=switch_on)
    called: list[bool] = []
    monkeypatch.setattr(speech, "_sarvam", lambda data, mime: called.append(True))
    with pytest.raises(speech.HostedRefused) as exc:
        speech.transcribe(WEBM, "audio/webm")
    assert exc.value.code == code
    assert called == []  # nothing left the building


def test_with_both_the_hosted_route_is_called(settings: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    settings(SPEECH_MODE="sarvam", SPEECH_HOSTED_APPROVAL="INFOSEC-2026-017 / DPO-2026-004")
    switches(monkeypatch, speech_hosted=True)
    monkeypatch.setattr(speech, "_sarvam", lambda data, mime: speech.Transcript("ok", "hi-IN", None))
    assert speech.transcribe(WEBM, "audio/webm").text == "ok"


def test_the_hosted_client_lives_in_the_gateway_and_uses_no_vendor_sdk() -> None:
    import inspect

    source = inspect.getsource(speech)
    assert "import httpx" in source
    assert "sarvamai" not in source


@pytest.mark.parametrize(
    ("data", "mime"),
    [
        (b"\x1a\x45\xdf\xa3" + bytes(8), "audio/webm"),
        (b"OggS" + bytes(8), "audio/ogg"),
        (bytes(4) + b"ftypM4A " + bytes(4), "audio/mp4"),
        (b"RIFF" + bytes(4) + b"WAVE" + bytes(4), "audio/wav"),
        (b"%PDF-1.7" + bytes(8), None),
        (b"MZ\x90\x00" + bytes(8), None),
    ],
)
def test_recordings_are_typed_by_their_bytes(data: bytes, mime: str | None) -> None:
    assert service.sniff(data) == mime


def test_fake_is_refused_outside_dev_and_test(settings: Any) -> None:
    settings(SPEECH_MODE="fake", APP_ENV="uat")
    with pytest.raises(speech.SpeechUnavailable) as exc:
        speech.transcribe(WEBM, "audio/webm")
    assert exc.value.code == "fake_not_allowed"
    settings(APP_ENV="test")
    assert speech.transcribe(WEBM, "audio/webm").text == speech.FAKE_SAMPLE


def test_the_hosted_switch_is_read_past_the_cache(settings: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """The cached read says on; the table says off a moment later: the fresh read wins (BLD-C011)."""
    settings(SPEECH_MODE="sarvam", SPEECH_HOSTED_APPROVAL="INFOSEC-2026-017 / DPO-2026-004")
    monkeypatch.setattr(speech.killswitch, "is_on", lambda name, conn=None: True)
    monkeypatch.setattr(speech.killswitch, "is_on_fresh", lambda name, conn=None: False)
    with pytest.raises(speech.HostedRefused) as exc:
        speech.transcribe(WEBM, "audio/webm")
    assert exc.value.code == "hosted_switched_off"


def test_the_local_engine_runs_in_an_isolated_child(settings: Any, tmp_path: Any) -> None:
    """No faster-whisper on this machine: the child says so, and the worker never imported it (BLD-C005)."""
    import sys

    settings(SPEECH_MODE="local", SPEECH_MODEL_PATH=str(tmp_path), SPEECH_TIMEOUT_S="60")
    with pytest.raises(speech.SpeechUnavailable) as exc:
        speech.transcribe(WEBM, "audio/webm")
    assert exc.value.code in {"engine_not_installed", "model_unavailable"}
    assert "faster_whisper" not in sys.modules


def test_the_watch_switches_voice_off_when_fake_runs_outside_dev(
    settings: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from core import watch

    calls: list[tuple[str, str]] = []

    def record(conn: object, name: str, reason: str, actor: str = "x") -> bool:
        calls.append((name, reason))
        return True

    monkeypatch.setattr(watch, "switch_off", record)
    for env, mode, expected in (
        ("uat", "fake", 1),
        ("prod", "local", 0),
        ("dev", "fake", 0),
        ("test", "fake", 0),
    ):
        calls.clear()
        settings(APP_ENV=env, SPEECH_MODE=mode)
        watch.Watch.speech_route(None)  # type: ignore[arg-type]
        assert len(calls) == expected, (env, mode)
    settings(APP_ENV="uat", SPEECH_MODE="fake")
    watch.Watch.speech_route(None)  # type: ignore[arg-type]
    assert calls[-1][0] == "capture.voice" and "DEC-096" in calls[-1][1]
