"""Fakes for Sarvam (DEC-108): a settings helper, a connection that records metering rows, and a local WebSocket
server that plays Sarvam's streaming speech-to-text and text-to-speech. Synthetic data only; nothing here calls the
real service (there is no key in dev or CI)."""

from __future__ import annotations

import base64
import json
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from websockets.sync.server import ServerConnection, serve

from core.config import get_settings
from gateway import sarvam, speech

KEY = "synthetic-test-key-0000"  # not a real key


def configure(monkeypatch: pytest.MonkeyPatch, *, hosted_on: bool = True, **env: str) -> None:
    """SPEECH_MODE=sarvam with the DEC-108 approval and a synthetic key, unless `env` says otherwise."""
    values = {
        "APP_ENV": "test",
        "SPEECH_MODE": "sarvam",
        "SPEECH_HOSTED_APPROVAL": "DEC-108",
        "SARVAM_API_KEY": KEY,
        "SARVAM_BASE_URL": "",
    }
    values.update(env)
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    monkeypatch.setattr(speech.killswitch, "is_on_fresh", lambda name, conn=None: hosted_on)
    monkeypatch.setattr(sarvam, "_sleep", lambda s: None)


class Result:
    def __init__(self, row: dict[str, Any] | None) -> None:
        self.row = row

    def fetchone(self) -> dict[str, Any] | None:
        return self.row

    def fetchall(self) -> list[dict[str, Any]]:
        return [self.row] if self.row else []


class MeterConn:
    """Records `speech_calls` inserts; answers the error-rate query with `totals`."""

    def __init__(self, totals: tuple[int, int] = (0, 0)) -> None:
        self.calls: list[dict[str, Any]] = []
        self.totals = totals

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> Result:
        if sql.startswith("INSERT INTO speech_calls"):
            keys = ("call", "model", "ref_id", "outcome", "error_code", "seconds", "chars", "latency_ms", "cost")
            self.calls.append(dict(zip(keys, params, strict=True)))
            return Result(None)
        if "FROM speech_calls" in sql:
            return Result({"total": self.totals[0], "failed": self.totals[1]})
        raise AssertionError(f"unexpected SQL: {sql[:40]}")


class FakeSarvamWs:
    """A local WebSocket server standing in for wss://api.sarvam.ai. It records what it was sent and answers like
    the documented API: STT `data` messages after a flush; TTS `audio` messages and a `final` event."""

    def __init__(self, *, heard: str = "Branch staff retype the form", tts_chunks: int = 2) -> None:
        self.heard = heard
        self.tts_chunks = tts_chunks
        self.paths: list[str] = []
        self.headers: list[dict[str, str]] = []
        self.received: list[dict[str, Any]] = []
        self.audio = bytearray()
        self.on_stt: Callable[[ServerConnection, dict[str, Any]], None] | None = None

    def handler(self, ws: ServerConnection) -> None:
        assert ws.request is not None
        self.paths.append(ws.request.path)
        self.headers.append({k.lower(): v for k, v in ws.request.headers.raw_items()})
        if ws.request.path.startswith("/speech-to-text/ws"):
            self._stt(ws)
        else:
            self._tts(ws)

    def _stt(self, ws: ServerConnection) -> None:
        for raw in ws:
            msg = json.loads(raw)
            self.received.append(msg)
            if self.on_stt:
                self.on_stt(ws, msg)
            if "audio" in msg:
                self.audio += base64.b64decode(msg["audio"]["data"])
            elif msg.get("type") == "flush":
                ws.send(
                    json.dumps(
                        {
                            "type": "data",
                            "data": {
                                "request_id": "req-1",
                                "transcript": self.heard,
                                "language_code": "hi-IN",
                                "metrics": {"audio_duration": len(self.audio) / 32000, "processing_latency": 0.1},
                            },
                        }
                    )
                )

    def _tts(self, ws: ServerConnection) -> None:
        for raw in ws:
            msg = json.loads(raw)
            self.received.append(msg)
            if msg.get("type") == "flush":
                for _ in range(self.tts_chunks):
                    frames = sarvam.fake_frames(10)
                    ws.send(
                        json.dumps(
                            {
                                "type": "audio",
                                "data": {"content_type": "audio/mpeg", "audio": base64.b64encode(frames).decode()},
                            }
                        )
                    )
                ws.send(json.dumps({"type": "event", "data": {"event_type": "final"}}))


@contextmanager
def ws_server(monkeypatch: pytest.MonkeyPatch, fake: FakeSarvamWs) -> Iterator[FakeSarvamWs]:
    server = serve(fake.handler, "127.0.0.1", 0)
    port = server.socket.getsockname()[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("SARVAM_BASE_URL", f"http://127.0.0.1:{port}")
    get_settings.cache_clear()
    try:
        yield fake
    finally:
        server.shutdown()
        thread.join(timeout=5)
