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
    worker(APP_ENV="uat", SPEECH_ENGINE_HOSTS="127.0.0.1")  # the contract server runs on localhost
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


# ---- round B review fixes (BLD-C018, BLD-C019, BLD-C030, BLD-C031) ----------------------------------------------


def test_a_note_that_waits_too_long_for_the_engine_is_busy_and_retried(
    server: Any, worker: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from voice.service import RETRY

    srv, _ = server
    monkeypatch.setattr(svc, "LOCK_WAIT_S", 0.3)
    srv.engine.lock.acquire()  # another recording holds the engine
    try:
        with pytest.raises(speech.SpeechUnavailable) as exc:
            speech.transcribe(f.wav(1, words="x"), "audio/wav")
    finally:
        srv.engine.lock.release()
    assert exc.value.code == "busy" and "busy" in RETRY


def test_an_answer_over_the_reply_cap_fails_that_note_and_restarts(worker: Any) -> None:
    with pytest.raises(speech.SpeechUnavailable) as exc:
        speech.transcribe(f.wav(1) + b"FAKE-BIG", "audio/wav")
    assert exc.value.code == "engine_crashed"
    assert speech.transcribe(f.wav(1, words="Fine again."), "audio/wav").text == "Fine again."


def test_outside_dev_an_answer_must_name_a_real_engine(worker: Any) -> None:
    """A missing engine key is refused like a fake one (BLD-C030)."""
    import http.server
    import json

    class NoEngine(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            self.rfile.read(int(self.headers["Content-Length"]))
            raw = json.dumps({"text": "words"}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, format: str, *args: Any) -> None:
            return

    stub = http.server.ThreadingHTTPServer(("127.0.0.1", 0), NoEngine)
    threading.Thread(target=stub.serve_forever, daemon=True).start()
    try:
        worker(
            APP_ENV="uat",
            SPEECH_ENGINE_HOSTS="127.0.0.1",
            SPEECH_ENGINE_URL=f"http://127.0.0.1:{stub.server_address[1]}",
        )
        with pytest.raises(speech.SpeechUnavailable) as exc:
            speech.transcribe(f.wav(1), "audio/wav")
        assert exc.value.code == "engine_unknown"
    finally:
        stub.shutdown()


def _raw(url: str) -> Any:
    import socket

    host, port = url.removeprefix("http://").split(":")
    return socket.create_connection((host, int(port)), timeout=5)


def test_a_length_that_is_not_plain_digits_is_refused(server: Any) -> None:
    _, url = server
    with _raw(url) as s:
        s.sendall(
            b"POST /transcribe HTTP/1.1\r\nX-Speech-Token: "
            + TOKEN.encode()
            + b"\r\nContent-Length: \xb2\r\n\r\n"
        )
        assert s.recv(64).startswith(b"HTTP/1.0 411")


def test_a_slow_client_is_cut_at_the_read_deadline(server: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    import time

    _, url = server
    monkeypatch.setattr(svc, "READ_DEADLINE_S", 1.0)
    with _raw(url) as s:
        s.sendall(b"POST /transcribe HTTP/1.1\r\n")  # and then nothing more
        time.sleep(2)
        assert s.recv(64) == b""  # the server closed it


def test_connections_over_the_cap_are_busy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPEECH_ENGINE", "fake")
    monkeypatch.setattr(svc, "MAX_CONNECTIONS", 2)
    srv = svc.build(0, TOKEN, timeout_s=3, host="127.0.0.1")
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        held = [_raw(url), _raw(url)]  # two open, idle connections
        import time

        time.sleep(0.3)
        with _raw(url) as third:
            assert third.recv(64).startswith(b"HTTP/1.1 503")
        for s in held:
            s.close()
    finally:
        srv.shutdown()
        srv.engine._kill()


def test_the_service_needs_a_token_of_at_least_32(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPEECH_SERVICE_TOKEN", "x" * 31)
    assert svc.serve_main() == 2


@pytest.mark.skipif(not __import__("sys").platform.startswith("linux"), reason="/proc and prctl are Linux")
def test_the_engine_cannot_read_the_servers_environment(tmp_path: Any) -> None:
    """The real entry point, as the container runs it: non-dumpable, so /proc/<server>/environ is root's (BLD-C018)."""
    import os
    import socket
    import subprocess
    import sys
    import time
    from pathlib import Path

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    env = {
        "PATH": os.defpath,
        "SPEECH_ENGINE": "fake",
        "SPEECH_SERVICE_TOKEN": TOKEN,
        "SPEECH_PORT": str(port),
    }
    script = Path(svc.__file__).resolve()
    proc = subprocess.Popen(
        [sys.executable, "-E", "-s", str(script), "serve"], env=env, stdout=subprocess.DEVNULL
    )
    try:
        url = f"http://127.0.0.1:{port}"
        for _ in range(50):
            try:
                if httpx.get(f"{url}/health", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.2)
        r = httpx.post(
            f"{url}/transcribe",
            content=f.wav(1) + b"FAKE-PARENT-ENV",
            headers={"X-Speech-Token": TOKEN},
            timeout=30,
        )
        assert r.json()["text"] == "denied"
    finally:
        proc.kill()
        proc.wait(5)
