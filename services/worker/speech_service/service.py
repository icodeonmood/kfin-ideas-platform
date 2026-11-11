"""The isolated speech service for voice notes (DEC-096, BLD-C014). One file, standard library only (plus the
engine itself): it runs in its own container, never inside the worker.

Why: a native audio decoder sees hostile input. In its own container, with its own non-root user, a read-only root
filesystem, a tmpfs /tmp, no secrets of the platform and an internal network that only the worker shares (no route
to Postgres, the store or the internet), a decoder exploit reaches nothing worth having (BLD-C012, BLD-C014).

Two processes:
- `serve` (this file's main): a small HTTP server on the internal network.
    GET  /health      -> {"ok", "engine", "ready"}; no token (it says nothing about anyone).
    POST /transcribe  -> the recording as the body; header `X-Speech-Token` (the shared internal token, compared
                         in constant time, at least 32 characters), `X-Max-Seconds`; at most MAX_BYTES. Answers
                         {"text", "language", "seconds", "engine"}, or {"error": code} with 400, 401, 411, 413,
                         422 or 503 (`busy` when the engine stayed taken for LOCK_WAIT_S; the worker retries).
  At most MAX_CONNECTIONS open at once (more get 503 busy), each request must arrive within READ_DEADLINE_S, and
  a recording whose client has gone is not run. It never logs a request, a recording or a text. On Linux it makes
  itself non-dumpable at start, so its /proc files (environ, mem) are root's and the engine child, which runs as
  the same user, cannot read the token from them; the token is also removed from its environment (BLD-C018).
- `engine`: a long-lived child the server starts with a cleared environment (no token) that loads the model once
  and answers one recording at a time over a pipe. It sets its own limits first (address space, no core dumps, no
  files written) and speaks on a copy of its stdout, with fd 1 itself pointed at /dev/null, so nothing a native
  library prints can corrupt an answer. The server gives each recording a wall-clock limit and refuses an answer
  over MAX_REPLY_BYTES; a child that overruns, dies or fails to start is killed and started again (the model
  reloads), and that recording fails with `engine_timeout` or `engine_crashed`.

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
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

MAX_BYTES = 6 * 1024 * 1024
MAX_SECONDS_CAP = 600.0
TOKEN_MIN = 32  # the same as deploy.sh
LOCK_WAIT_S = (
    30.0  # how long a recording waits for the engine before the answer is 503 busy (the worker retries)
)
MAX_REPLY_BYTES = 1024 * 1024  # an engine answer larger than this is refused
MAX_CONNECTIONS = 8  # open connections at once; more are refused with 503 busy
HEADER_TIMEOUT_S = 10  # each read of the request
READ_DEADLINE_S = 60.0  # the whole request (headers and body) must arrive within this
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
        if b"FAKE-BIG" in data:  # tests: an answer larger than the server accepts
            return {"text": "x" * (2 * 1024 * 1024), "language": None, "seconds": 0.0}
        if b"FAKE-PARENT-ENV" in data:  # tests: can the engine read the server's environment? (BLD-C018)
            try:
                with open(f"/proc/{os.getppid()}/environ", "rb") as fh:
                    fh.read(1)
                verdict = "readable"
            except PermissionError:
                verdict = "denied"
            except OSError:
                verdict = "no_proc"
            return {"text": verdict, "language": None, "seconds": 0.0}
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
    # The protocol gets its own copy of the pipe; fd 1 goes to /dev/null, so anything a native library prints can
    # never corrupt a frame (BLD-C031).
    out = os.fdopen(os.dup(1), "wb", buffering=0)
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, 1)
    os.close(devnull)
    sys.stdout = open(os.devnull, "w")  # noqa: SIM115 - lives as long as the process
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


# ---- the server's side of the engine -------------------------------------------------------------------------


class EngineFailed(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class EngineBusy(EngineFailed):
    """Another recording held the engine for longer than LOCK_WAIT_S: try again later (the worker retries)."""

    def __init__(self) -> None:
        super().__init__("busy")


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
        try:
            self._spawn()
        except BaseException:
            self._kill()  # a child that hung or failed while starting never lingers (BLD-C031)
            raise

    def _spawn(self) -> None:
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
        if size > MAX_REPLY_BYTES:
            raise EngineFailed("engine_crashed")
        answer = json.loads(take(size))
        if not isinstance(answer, dict):
            raise EngineFailed("engine_crashed")
        return answer

    def transcribe(
        self, data: bytes, max_seconds: float, still_wanted: Callable[[], bool] | None = None
    ) -> dict[str, Any]:
        if not self.lock.acquire(timeout=LOCK_WAIT_S):  # never queue without end behind a long recording
            raise EngineBusy()
        try:
            if still_wanted is not None and not still_wanted():
                raise EngineFailed(
                    "client_gone"
                )  # the worker gave up while this waited: do not run the engine
            return self._run(data, max_seconds)
        finally:
            self.lock.release()

    def _run(self, data: bytes, max_seconds: float) -> dict[str, Any]:
        if self.proc is None or self.proc.poll() is not None:
            self._start()
        assert self.proc is not None and self.proc.stdin is not None
        try:
            self.proc.stdin.write(_frame(json.dumps({"max_seconds": max_seconds}).encode()) + _frame(data))
            self.proc.stdin.flush()
            return self._read(self.timeout_s)
        except (EngineFailed, BrokenPipeError, OSError, ValueError) as exc:
            self._kill()  # the next recording gets a fresh engine
            raise EngineFailed(exc.code if isinstance(exc, EngineFailed) else "engine_crashed") from None


# ---- HTTP ------------------------------------------------------------------------------------------------------


BUSY = b'{"error": "busy"}'


def make_handler(
    engine: Engine, token: str, slots: threading.BoundedSemaphore
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "speech"
        sys_version = ""
        timeout = HEADER_TIMEOUT_S  # each read; the whole request also has READ_DEADLINE_S

        def handle(self) -> None:
            """At most MAX_CONNECTIONS at once, and the request must arrive within READ_DEADLINE_S: a slow or
            flooding client cannot hold the service (BLD-C031)."""
            if not slots.acquire(blocking=False):
                with contextlib.suppress(OSError):
                    self.wfile.write(
                        b"HTTP/1.1 503 Service Unavailable\r\nContent-Type: application/json\r\nConnection: close\r\n"
                        + f"Content-Length: {len(BUSY)}\r\n\r\n".encode()
                        + BUSY
                    )
                return
            self._deadline = threading.Timer(READ_DEADLINE_S, self._cut)
            self._deadline.daemon = True
            self._deadline.start()
            try:
                super().handle()
            finally:
                self._deadline.cancel()
                slots.release()

        def _cut(self) -> None:
            with contextlib.suppress(OSError):
                self.connection.shutdown(socket.SHUT_RDWR)

        def _client_gone(self) -> bool:
            """True when the worker has closed the connection (it gave up while the recording waited)."""
            try:
                ready, _, _ = select.select([self.connection], [], [], 0)
                return bool(ready) and self.connection.recv(1, socket.MSG_PEEK) == b""
            except OSError:
                return True

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
            length = self.headers.get("Content-Length", "")
            if not (length.isascii() and length.isdigit()):
                return self._send(411, {"error": "length_required"})
            try:
                size = int(length)
            except ValueError:
                return self._send(400, {"error": "bad_request"})
            if size > MAX_BYTES:
                return self._send(413, {"error": "file_too_large"})
            try:
                max_seconds = min(MAX_SECONDS_CAP, float(self.headers.get("X-Max-Seconds", "190")))
            except ValueError:
                return self._send(400, {"error": "bad_request"})
            try:
                data = self.rfile.read(size)
            except OSError:
                return None  # cut at the read deadline, or the client went away
            if len(data) != size:
                return None
            self._deadline.cancel()  # the request is in; the engine has its own limits from here
            try:
                answer = engine.transcribe(data, max_seconds, still_wanted=lambda: not self._client_gone())
            except EngineFailed as exc:
                if exc.code == "client_gone":
                    return None
                return self._send(503, {"error": exc.code, "engine": engine.name})
            if "error" in answer:
                return self._send(422, {"error": str(answer["error"]), "engine": engine.name})
            self._send(200, answer)

    return Handler


def build(port: int, token: str, timeout_s: float, host: str = "0.0.0.0") -> ThreadingHTTPServer:  # noqa: S104
    """The server, not yet serving (tests start it on port 0 in a thread)."""
    engine = Engine(timeout_s)
    slots = threading.BoundedSemaphore(MAX_CONNECTIONS)
    server = ThreadingHTTPServer((host, port), make_handler(engine, token, slots))
    server.daemon_threads = True
    server.engine = engine  # type: ignore[attr-defined]
    return server


def harden() -> None:
    """Linux: make this process non-dumpable, so its /proc files (environ, mem) belong to root and the engine child,
    which runs as the same user, cannot read the token from them or attach to this process (BLD-C018)."""
    if not sys.platform.startswith("linux"):
        return
    import ctypes

    with contextlib.suppress(OSError, AttributeError):
        ctypes.CDLL(None, use_errno=True).prctl(4, 0, 0, 0, 0)  # PR_SET_DUMPABLE = 4, value 0


def serve_main() -> int:
    harden()
    token = os.environ.pop("SPEECH_SERVICE_TOKEN", "")  # kept in memory only from here on
    if len(token) < TOKEN_MIN:
        print(json.dumps({"event": "speech.refused_to_start", "reason_code": "token_missing"}), flush=True)
        return 2
    server = build(int(_env("SPEECH_PORT", "8300")), token, float(_env("SPEECH_TIMEOUT_S", "300")))
    engine: Engine = server.engine  # type: ignore[attr-defined]
    with contextlib.suppress(
        EngineFailed
    ):  # load the model before the first recording; health says if it failed
        engine._start()
    print(json.dumps({"event": "speech.serving", "engine": engine.name}), flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "serve"
    sys.exit(engine_main() if command == "engine" else serve_main())
