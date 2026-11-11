"""The isolated speech service for voice notes (DEC-096, BLD-C014). One file, standard library only (plus the
engine itself): it runs in its own container, never inside the worker.

Why: a native audio decoder sees hostile input. In its own container, with its own non-root user, a read-only root
filesystem, a tmpfs /tmp, no secrets of the platform and an internal network that only the worker shares (no route
to Postgres, the store or the internet), a decoder exploit reaches nothing worth having (BLD-C012, BLD-C014).

Two processes:
- `serve` (this file's main): a small HTTP server on the internal network.
    GET  /health      -> {"ok", "engine", "ready"}; no token (it says nothing about anyone).
    POST /transcribe  -> the recording as the body; header `X-Speech-Token` (the shared internal token, compared
                         in constant time), `X-Max-Seconds`; at most MAX_BYTES. Answers {"text", "language",
                         "seconds", "engine"}, or {"error": code} with 401, 411, 413, 422 or 503.
  It never logs a request, a recording or a text.
- `engine`: a long-lived child the server starts with a cleared environment (no token) that loads the model once
  and answers one recording at a time over a pipe. It sets its own limits first (address space, no core dumps, no
  files written). The server gives each recording a wall-clock limit; a child that overruns or dies is killed and
  started again (the model reloads), and that recording fails with `engine_timeout` or `engine_crashed`.

Engines: `faster-whisper` (CPU, int8, model files read-only from SPEECH_MODEL_PATH, nothing downloaded) or `fake`
(tests and dev: the text a synthetic recording carries after `FAKE-TRANSCRIPT:`, else a fixed sample). The worker
refuses a `fake` engine outside dev and test (it reads `engine` from every answer).
"""

from __future__ import annotations

import contextlib
import hmac
import json
import os
import select
import struct
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

MAX_BYTES = 6 * 1024 * 1024
MAX_SECONDS_CAP = 600.0
FAKE_MARKER = b"FAKE-TRANSCRIPT:"
FAKE_SAMPLE = (
    "Branch staff type every change of bank form twice because the scanned copy is hard to read, "
    "and it adds a day to each request."
)


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


# ---- the engine child ----------------------------------------------------------------------------------------


def _limits(memory_mb: int) -> None:
    import resource

    for limit, value in (
        (resource.RLIMIT_CORE, 0),
        (resource.RLIMIT_FSIZE, 0),
        (resource.RLIMIT_AS, memory_mb * 1024 * 1024),
    ):
        with contextlib.suppress(
            ValueError, OSError
        ):  # macOS may refuse RLIMIT_AS; the wall clock still holds
            resource.setrlimit(limit, (value, value))


def _read_exact(stream: Any, n: int) -> bytes:
    out = b""
    while len(out) < n:
        chunk = stream.read(n - len(out))
        if not chunk:
            raise EOFError
        out += chunk
    return out


def _frame(payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + payload


class _Fake:
    name = "fake"

    def transcribe(self, data: bytes, max_seconds: float) -> dict[str, Any]:
        if b"FAKE-SLEEP" in data:  # tests: an engine that hangs
            time.sleep(3600)
        if b"FAKE-CRASH" in data:  # tests: an engine that dies
            os._exit(3)
        if b"FAKE-ENV" in data:  # tests: what the engine can see of its environment (names only)
            return {"text": ",".join(sorted(os.environ)), "language": None, "seconds": 0.0}
        at = data.find(FAKE_MARKER)
        if at >= 0:
            text = data[at + len(FAKE_MARKER) :].split(b"\0", 1)[0].decode("utf-8", "replace").strip()
            return {"text": text, "language": None, "seconds": 0.0}
        return {"text": FAKE_SAMPLE, "language": "en", "seconds": 0.0}


class _FasterWhisper:
    name = "faster-whisper"

    def __init__(self, model_path: str, threads: int) -> None:
        from faster_whisper import WhisperModel  # type: ignore[import-not-found]

        self.model = WhisperModel(
            model_path, device="cpu", compute_type="int8", cpu_threads=threads, local_files_only=True
        )

    def transcribe(self, data: bytes, max_seconds: float) -> dict[str, Any]:
        import io

        try:
            segments, info = self.model.transcribe(io.BytesIO(data), beam_size=1, vad_filter=True)
            if info.duration and info.duration > max_seconds:
                return {"error": "too_long"}
            text = " ".join(s.text.strip() for s in segments).strip()
        except MemoryError:
            return {"error": "too_big"}
        except Exception:  # decoder errors can carry pieces of the input: keep only a code
            return {"error": "unreadable"}
        return {"text": text, "language": info.language, "seconds": float(info.duration or 0.0)}


def engine_main() -> int:
    """The child: limits, then the model, then one recording at a time until the pipe closes."""
    _limits(int(_env("SPEECH_MEMORY_MB", "4096")))
    out = sys.stdout.buffer
    kind = _env("SPEECH_ENGINE", "faster-whisper")
    try:
        engine: Any = (
            _Fake()
            if kind == "fake"
            else _FasterWhisper(_env("SPEECH_MODEL_PATH", "/models"), int(_env("SPEECH_THREADS", "2")))
        )
        ready: dict[str, Any] = {"ready": True, "engine": engine.name}
    except ImportError:
        engine, ready = None, {"ready": False, "error": "engine_not_installed"}
    except Exception:  # a missing or broken model folder
        engine, ready = None, {"ready": False, "error": "model_unavailable"}
    out.write(_frame(json.dumps(ready).encode()))
    out.flush()
    if engine is None:
        return 1
    while True:
        try:
            header = json.loads(
                _read_exact(sys.stdin.buffer, struct.unpack(">I", _read_exact(sys.stdin.buffer, 4))[0])
            )
            data = _read_exact(sys.stdin.buffer, struct.unpack(">I", _read_exact(sys.stdin.buffer, 4))[0])
        except EOFError:
            return 0
        answer = engine.transcribe(data, float(header.get("max_seconds", 190)))
        answer.setdefault("engine", engine.name)
        out.write(_frame(json.dumps(answer).encode()))
        out.flush()


# ---- the server's side of the engine -------------------------------------------------------------------------


class EngineFailed(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class Engine:
    """One long-lived engine child; one recording at a time. Restarted after a timeout or a crash."""

    def __init__(self, timeout_s: float, start_timeout_s: float = 300.0) -> None:
        self.timeout_s = timeout_s
        self.start_timeout_s = start_timeout_s
        self.lock = threading.Lock()
        self.proc: subprocess.Popen[bytes] | None = None
        self.name = _env("SPEECH_ENGINE", "faster-whisper")
        self.ready = False

    def _child_env(self) -> dict[str, str]:
        """Only what the engine needs. The service token stays with the server."""
        keep = ("SPEECH_ENGINE", "SPEECH_MODEL_PATH", "SPEECH_THREADS", "SPEECH_MEMORY_MB")
        env = {k: os.environ[k] for k in keep if k in os.environ}
        threads = _env("SPEECH_THREADS", "2")
        home = tempfile.gettempdir()  # the container's tmpfs /tmp: the only writable place
        env.update({"PATH": os.defpath, "HOME": home, "LANG": "C.UTF-8", "OMP_NUM_THREADS": threads})
        env["HF_HUB_OFFLINE"] = "1"
        return env

    def _start(self) -> None:
        self.proc = subprocess.Popen(  # our own file, a fixed interpreter, no shell
            [sys.executable, "-E", "-s", os.path.abspath(__file__), "engine"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=self._child_env(),
            close_fds=True,
            cwd=tempfile.gettempdir(),
        )
        hello = self._read(self.start_timeout_s)
        self.ready = bool(hello.get("ready"))
        if not self.ready:
            self._kill()
            raise EngineFailed(str(hello.get("error") or "engine_not_ready"))
        self.name = str(hello.get("engine") or self.name)

    def _kill(self) -> None:
        if self.proc is not None:
            with contextlib.suppress(Exception):
                self.proc.kill()
                self.proc.wait(5)
        self.proc = None
        self.ready = False

    def _read(self, timeout_s: float) -> dict[str, Any]:
        assert self.proc is not None and self.proc.stdout is not None
        fd = self.proc.stdout.fileno()
        deadline = time.monotonic() + timeout_s
        buf = b""

        def take(n: int) -> bytes:
            nonlocal buf
            while len(buf) < n:
                left = deadline - time.monotonic()
                if left <= 0:
                    raise EngineFailed("engine_timeout")
                ready, _, _ = select.select([fd], [], [], left)
                if not ready:
                    raise EngineFailed("engine_timeout")
                chunk = os.read(fd, 65536)
                if not chunk:
                    raise EngineFailed("engine_crashed")
                buf += chunk
            part, buf = buf[:n], buf[n:]
            return part

        size = struct.unpack(">I", take(4))[0]
        answer = json.loads(take(size))
        if not isinstance(answer, dict):
            raise EngineFailed("engine_crashed")
        return answer

    def transcribe(self, data: bytes, max_seconds: float) -> dict[str, Any]:
        with self.lock:
            if self.proc is None or self.proc.poll() is not None:
                self._start()
            assert self.proc is not None and self.proc.stdin is not None
            try:
                self.proc.stdin.write(
                    _frame(json.dumps({"max_seconds": max_seconds}).encode()) + _frame(data)
                )
                self.proc.stdin.flush()
                return self._read(self.timeout_s)
            except (EngineFailed, BrokenPipeError, OSError, ValueError) as exc:
                self._kill()  # the next recording gets a fresh engine
                raise EngineFailed(exc.code if isinstance(exc, EngineFailed) else "engine_crashed") from None


# ---- HTTP ------------------------------------------------------------------------------------------------------


def make_handler(engine: Engine, token: str) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "speech"
        sys_version = ""
        timeout = 30  # reading a request body

        def log_message(self, format: str, *args: Any) -> None:  # never log requests
            return

        def _send(self, status: int, body: dict[str, Any]) -> None:
            raw = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:
            if self.path == "/health":
                self._send(200, {"ok": True, "engine": engine.name, "ready": engine.ready})
            else:
                self._send(404, {"error": "not_found"})

        def do_POST(self) -> None:
            if self.path != "/transcribe":
                return self._send(404, {"error": "not_found"})
            given = self.headers.get("X-Speech-Token", "")
            if not token or not hmac.compare_digest(given.encode(), token.encode()):
                return self._send(401, {"error": "unauthorized"})
            length = self.headers.get("Content-Length")
            if length is None or not length.isdigit():
                return self._send(411, {"error": "length_required"})
            if int(length) > MAX_BYTES:
                return self._send(413, {"error": "file_too_large"})
            try:
                max_seconds = min(MAX_SECONDS_CAP, float(self.headers.get("X-Max-Seconds", "190")))
            except ValueError:
                return self._send(422, {"error": "bad_request"})
            data = self.rfile.read(int(length))
            try:
                answer = engine.transcribe(data, max_seconds)
            except EngineFailed as exc:
                return self._send(503, {"error": exc.code, "engine": engine.name})
            if "error" in answer:
                return self._send(422, {"error": str(answer["error"]), "engine": engine.name})
            self._send(200, answer)

    return Handler


def build(port: int, token: str, timeout_s: float, host: str = "0.0.0.0") -> ThreadingHTTPServer:  # noqa: S104
    """The server, not yet serving (tests start it on port 0 in a thread)."""
    engine = Engine(timeout_s)
    server = ThreadingHTTPServer((host, port), make_handler(engine, token))
    server.daemon_threads = True
    server.engine = engine  # type: ignore[attr-defined]
    return server


def serve_main() -> int:
    token = _env("SPEECH_SERVICE_TOKEN", "")
    if len(token) < 16:
        print(json.dumps({"event": "speech.refused_to_start", "reason_code": "token_missing"}), flush=True)
        return 2
    server = build(int(_env("SPEECH_PORT", "8300")), token, float(_env("SPEECH_TIMEOUT_S", "300")))
    with contextlib.suppress(
        EngineFailed
    ):  # load the model before the first recording; health says if it failed
        server.engine._start()  # type: ignore[attr-defined]
    print(json.dumps({"event": "speech.serving", "engine": server.engine.name}), flush=True)  # type: ignore[attr-defined]
    server.serve_forever()
    return 0


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "serve"
    sys.exit(engine_main() if command == "engine" else serve_main())
