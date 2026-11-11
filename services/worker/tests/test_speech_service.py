"""The isolated speech service (DEC-096, BLD-C015): its HTTP contract with the worker, with the fake engine in a
real engine child process. No stack, no model: the server runs in this test process on a free port."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from typing import Any

import httpx
import pytest

from core.config import get_settings
from gateway import speech
from speech_service import service as svc
from tests import voice_files as f

TOKEN = "synthetic-speech-token-for-the-contract-test"


@pytest.fixture
def server(monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    monkeypatch.setenv("SPEECH_ENGINE", "fake")
    monkeypatch.setenv("SPEECH_MEMORY_MB", "512")
    monkeypatch.setenv("SPEECH_SERVICE_TOKEN", TOKEN)  # the server's own; the engine child must not get it
    srv = svc.build(0, TOKEN, timeout_s=3, host="127.0.0.1")
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield srv, f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.engine._kill()


@pytest.fixture
def worker(monkeypatch: pytest.MonkeyPatch, server: Any) -> Iterator[Any]:
    def apply(**env: str) -> None:
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        get_settings.cache_clear()

    apply(SPEECH_MODE="local", SPEECH_ENGINE_URL=server[1], SPEECH_SERVICE_TOKEN=TOKEN, APP_ENV="test")
    yield apply
    get_settings.cache_clear()


def test_health_says_which_engine_is_loaded(server: Any) -> None:
    srv, url = server
    srv.engine._start()
    body = httpx.get(f"{url}/health").json()
    assert body == {"ok": True, "engine": "fake", "ready": True}


def test_the_worker_gets_the_text_over_http(worker: Any) -> None:
    got = speech.transcribe(f.wav(2, words="Forms are typed twice at the branch."), "audio/wav")
    assert got.text == "Forms are typed twice at the branch."


def test_the_model_stays_loaded_between_notes(server: Any, worker: Any) -> None:
    srv, _ = server
    speech.transcribe(f.wav(1, words="First."), "audio/wav")
    pid = srv.engine.proc.pid
    speech.transcribe(f.wav(1, words="Second."), "audio/wav")
    assert srv.engine.proc.pid == pid


def test_a_wrong_token_is_refused(worker: Any) -> None:
    worker(SPEECH_SERVICE_TOKEN="not-the-token")
    with pytest.raises(speech.SpeechUnavailable) as exc:
        speech.transcribe(f.wav(1, words="x"), "audio/wav")
    assert exc.value.code == "engine_unauthorized"


def test_a_large_body_is_refused_before_it_is_read(server: Any) -> None:
    _, url = server
    r = httpx.post(
        f"{url}/transcribe", content=bytes(svc.MAX_BYTES + 1), headers={"X-Speech-Token": TOKEN}, timeout=30
    )
    assert r.status_code == 413 and r.json() == {"error": "file_too_large"}


def test_a_fake_engine_is_refused_outside_dev_and_test(worker: Any) -> None:
    worker(APP_ENV="uat")
    with pytest.raises(speech.SpeechUnavailable) as exc:
        speech.transcribe(f.wav(1, words="x"), "audio/wav")
    assert exc.value.code == "fake_not_allowed"


@pytest.mark.parametrize(
    ("marker", "code"), [(b"FAKE-SLEEP", "engine_timeout"), (b"FAKE-CRASH", "engine_crashed")]
)
def test_a_hanging_or_dying_engine_fails_that_note_and_restarts(
    worker: Any, marker: bytes, code: str
) -> None:
    with pytest.raises(speech.SpeechUnavailable) as exc:
        speech.transcribe(f.wav(1) + marker, "audio/wav")
    assert exc.value.code == code
    assert speech.transcribe(f.wav(1, words="After the restart."), "audio/wav").text == "After the restart."


def test_the_engine_child_sees_no_token_and_no_platform_secret(
    worker: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgres://synthetic")
    names = speech.transcribe(f.wav(1) + b"FAKE-ENV", "audio/wav").text.split(",")
    assert "SPEECH_SERVICE_TOKEN" not in names
    assert not [n for n in names if any(w in n for w in ("DATABASE", "TOKEN", "SECRET", "PASSWORD", "KEY"))]


def test_the_server_never_logs_a_request(server: Any, capsys: pytest.CaptureFixture[str]) -> None:
    _, url = server
    httpx.post(
        f"{url}/transcribe", content=f.wav(1, words="Private words."), headers={"X-Speech-Token": TOKEN}
    )
    out = capsys.readouterr()
    assert "Private words" not in out.out + out.err and "/transcribe" not in out.out + out.err


def test_the_service_refuses_to_start_without_a_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPEECH_SERVICE_TOKEN", "")
    assert svc.serve_main() == 2


def test_an_unreachable_service_is_retried_later(worker: Any) -> None:
    from voice.service import RETRY

    worker(SPEECH_ENGINE_URL="http://127.0.0.1:9")
    with pytest.raises(speech.SpeechUnavailable) as exc:
        speech.transcribe(f.wav(1, words="x"), "audio/wav")
    assert exc.value.code == "engine_unreachable" and exc.value.code in RETRY
