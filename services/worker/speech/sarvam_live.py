"""`make sarvam-live`: the live contract check of the Sarvam client (BLD-C177; DEC-108; L-LISTEN).

The product lead runs it in their own terminal, with `SARVAM_API_KEY` loaded there, before the gates. It never runs
in CI: it refuses when `CI` is set, it is not a test pytest collects, and CI keeps `SPEECH_MODE=fake` with no secret.
It refuses `SARVAM_BASE_URL` too, so it can only reach the real API. Every call goes through the worker's own code
path, never an SDK and never raw httpx or websockets here:

| Call | The worker's path | Model |
|---|---|---|
| `tts` | Listen: `speech.listen.outgoing` (masked for the service, leak-checked), then `listen._synthesise` into `gateway.sarvam.tts`, with the audio parsed as Listen parses it | bulbul:v4-flash |

Per call it checks that the reply parses the way our code expects, that the text was masked on its way through the
worker, that `speech_calls` has its row (call, model, outcome, and no text in any column), and that with
`speech.hosted` off the same call refuses before any network call: the client's two network entry points
(`gateway.sarvam._post` and `_ws_open`) are replaced by tripwires, and reaching either fails the check.

Synthetic text only, written here: ordinary office words, no names, nothing shaped like a folio, PAN, phone number,
email, account number or amount. The only audio is what tts makes.

The check makes its own throwaway database the way the tests' `test_database` fixture does (created on the local
stack's Postgres, migrated with the dbmate container, dropped at the end even on failure; `make up` must be running),
with `speech.hosted` on inside it. It never touches the demo database or any other.

Output: one line per call (the call, model, status, latency in ms, PASS or FAIL with our own reason code), then a
summary. It never prints text, audio, the key, a header, a URL or a traceback. The worker's logs go to a buffer at
WARNING for the run and are checked against the log rules (non-negotiable 3), never printed.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import logging
import os
import secrets
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any, TextIO

ALL = ("tts",)  # run order: tts makes the audio the speech-to-text calls hear
MISSING_KEY = "SARVAM_API_KEY is not set. Load it in your own terminal and run this again."
IN_CI = "This check calls Sarvam with a real key, so it never runs in CI. Run it in your own terminal."
BASE_URL_SET = "SARVAM_BASE_URL is set, so this would not reach Sarvam. Unset it and run this again."
NO_DATABASE = (
    "The local stack's Postgres is not reachable, or dbmate failed. Run `make up` and run this again."
)
APPROVAL = "DEC-108"  # the reference docs/UAT.md gives for SPEECH_HOSTED_APPROVAL (the voice row)
DB_PREFIX = "sarvam_live"
ACTOR = "sarvam-live"
SPEECH_HOSTED = "speech.hosted"

# Synthetic, written for this check. Each sentence carries two words that are easy to check once speech to text has
# heard the audio tts made of it.
SPOKEN = "The printer near the lift is out of paper. Please order more chairs for the meeting room."
SPOKEN_TITLE = "Summary"
HEARD = (("printer", "paper"), ("chairs", "meeting"))  # at least one word of each sentence must come back
# Words that must never show in a printed line, a `speech_calls` column or a worker warning.
MARKERS = frozenset({"printer", "paper", "lift", "chairs", "meeting"})


class _Tripped(BaseException):
    """A network entry point was reached while the check expected a refusal. BaseException, so no worker `except
    Exception` can swallow it."""


class _NoDatabase(Exception):
    pass


@dataclass
class Line:
    call: str
    model: str
    status: str = "-"
    ms: int = 0
    words: bool | None = None  # speech to text only: did the expected words come back
    reason: str | None = None  # None: PASS

    @property
    def passed(self) -> bool:
        return self.reason is None

    def render(self) -> str:
        words = "" if self.words is None else f"  words: {'yes' if self.words else 'no'}"
        verdict = "PASS" if self.reason is None else f"FAIL {self.reason}"
        return f"{self.call:<10}  {self.model:<15}  {self.status:<8}  {self.ms:>6} ms{words}  {verdict}"


@dataclass
class _Spy:
    """What the worker's path did, by count only: never the text or the audio."""

    sockets: list[Any] = field(default_factory=list)
    masked: int = 0  # texts through the worker's masking for the service
    leak_checked: int = 0  # texts through the gateway's leak check before anything goes out


@dataclass
class _Run:
    conn: Any
    out: TextIO
    mp3: bytes = b""  # what tts made, for the speech-to-text calls


# ---- small tools ---------------------------------------------------------------------------------------------


@contextlib.contextmanager
def _patched(obj: Any, name: str, value: Any) -> Iterator[None]:
    old = getattr(obj, name)
    setattr(obj, name, value)
    try:
        yield
    finally:
        setattr(obj, name, old)


@contextlib.contextmanager
def _watching(spy: _Spy) -> Iterator[None]:
    """Count what goes through the masking and the leak check, and keep the sockets the client opens (for their close
    codes). The real functions still run."""
    from gateway import sarvam
    from speech import adapters, listen

    real_open, real_check, real_mask = sarvam._ws_open, sarvam.check_masked, adapters.mask_for_service

    def ws_open(path: str, params: dict[str, str]) -> Any:
        ws = real_open(path, params)
        spy.sockets.append(ws)
        return ws

    def check_masked(text: str) -> None:
        spy.leak_checked += 1
        real_check(text)

    def mask_for_service(text: str) -> str:
        spy.masked += 1
        return real_mask(text)

    with (
        _patched(sarvam, "_ws_open", ws_open),
        _patched(sarvam, "check_masked", check_masked),
        _patched(listen, "mask_for_service", mask_for_service),
    ):
        yield


@contextlib.contextmanager
def _no_network() -> Iterator[list[str]]:
    """Tripwires on the client's two network entry points. The list names any that was reached."""
    from gateway import sarvam

    reached: list[str] = []

    def post(*_args: Any, **_kwargs: Any) -> Any:
        reached.append("_post")
        raise _Tripped

    def ws_open(*_args: Any, **_kwargs: Any) -> Any:
        reached.append("_ws_open")
        raise _Tripped

    with _patched(sarvam, "_post", post), _patched(sarvam, "_ws_open", ws_open):
        yield reached


def _status(kind: str, sockets: Sequence[Any], code: str | None) -> str:
    """`http 200`, `ws 1000` (the close code), `ws ok`; on a refusal at the door, the HTTP status in our code."""
    if code and code.startswith("hosted_") and code[len("hosted_") :].isdigit():
        return f"{kind} {code[len('hosted_') :]}"
    if kind == "http":
        return "http 200" if code is None else "http -"
    closes = [getattr(ws, "close_code", None) for ws in sockets]
    if closes and closes[-1] is not None:
        return f"ws {closes[-1]}"
    return "ws ok" if sockets and code is None else "ws -"


def _since(conn: Any) -> int:
    row = conn.execute("SELECT coalesce(max(id), 0) AS n FROM speech_calls").fetchone()
    return int(row["n"])


def _metered(conn: Any, since: int, call: str, model: str, rows_expected: int) -> str | None:
    """The call's rows in `speech_calls`: the right call, model and outcome, and no synthetic word in any column."""
    rows = conn.execute(
        "SELECT call, model, ref_id, outcome, error_code, speech_seconds, char_count, latency_ms, cost_inr "
        "FROM speech_calls WHERE id > %s ORDER BY id",
        (since,),
    ).fetchall()
    if len(rows) != rows_expected:
        return "meter_rows"
    for row in rows:
        if row["call"] != call or row["model"] != model:
            return "meter_call"
        if row["outcome"] not in ("ok", "ok_after_retry") or row["error_code"] is not None:
            return "meter_outcome"
        values = " ".join(str(v) for v in row.values() if v is not None).lower()
        if any(w in values for w in MARKERS):
            return "meter_text"
    return None


def _refuses_offline(conn: Any, attempt: Callable[[], object]) -> str | None:
    """With `speech.hosted` off, the same call must refuse with `hosted_switched_off` before either network entry
    point is reached. The switch goes back on afterwards. Returns a reason code, or None when it refused properly."""
    from core import killswitch
    from gateway.speech import SpeechUnavailable

    killswitch.set_switch(
        conn,
        SPEECH_HOSTED,
        "off",
        reason="Live check: the refusal before any network call (BLD-C177)",
        actor=ACTOR,
    )
    try:
        with _no_network() as reached:
            try:
                attempt()
            except _Tripped:
                return "refusal_reached_network"
            except SpeechUnavailable as exc:
                if reached:
                    return "refusal_reached_network"
                return None if exc.code == "hosted_switched_off" else f"refusal_{exc.code}"
            return "refusal_missing"
    finally:
        killswitch.set_switch(
            conn,
            SPEECH_HOSTED,
            "on",
            reason="Live check: back on after the refusal check (BLD-C177)",
            actor=ACTOR,
        )


# ---- the calls -------------------------------------------------------------------------------------------------


def _tts(run: _Run) -> Line:
    """Listen's path: the script part masked for the service and leak-checked (`listen.outgoing`), spoken by
    `listen._synthesise` through `gateway.sarvam.tts`, the audio parsed as Listen parses it (leading tags stripped,
    MPEG frames counted). Listen's store is stood in for here: the check keeps the audio in memory only."""
    from gateway import sarvam
    from gateway.speech import SpeechUnavailable
    from speech import listen
    from speech.adapters import Script, ScriptPart

    line = Line("tts", sarvam.TTS_MODEL)
    script = Script(parts=(ScriptPart("summary", SPOKEN_TITLE, SPOKEN),), version="sarvamlivecheck01")
    idea = str(uuid.uuid4())
    kept: dict[str, Any] = {}

    def keep(*_args: Any, **_kwargs: Any) -> None:
        _conn, _idea, _version, _voice, _lang, audio, chapters, duration_s = _args
        kept.update(audio=audio, chapters=chapters, duration_s=duration_s)

    def attempt() -> bytes:
        texts = listen.outgoing(script)
        return b"".join(
            listen._synthesise(run.conn, idea, script.version, texts, listen.LANG, listen._voice())
        )

    since = _since(run.conn)
    spy = _Spy()
    audio = b""
    started = time.monotonic()
    with _patched(listen, "_store", keep), _watching(spy):
        try:
            audio = attempt()
        except SpeechUnavailable as exc:
            line.reason = exc.code
    line.ms = int((time.monotonic() - started) * 1000)
    line.status = _status("ws", spy.sockets, line.reason)
    if line.reason:
        return line
    if not audio or kept.get("audio") != audio:
        line.reason = "no_audio"
    elif listen.mp3_seconds(audio) <= 0 or float(kept.get("duration_s") or 0) <= 0:
        line.reason = "not_mp3"
    elif [c.get("part") for c in kept.get("chapters", [])] != ["summary"]:
        line.reason = "chapters"
    elif spy.masked < 1 or spy.leak_checked < 2:  # outgoing's check and tts's own
        line.reason = "not_masked"
    else:
        line.reason = _metered(run.conn, since, "tts", sarvam.TTS_MODEL, rows_expected=1)
    if line.reason is None:
        with _patched(listen, "_store", keep):  # never the real store, even if the refusal were to fail
            line.reason = _refuses_offline(run.conn, attempt)
    run.mp3 = audio
    return line


CHECKS: dict[str, Callable[[_Run], Line]] = {"tts": _tts}


def _model(call: str) -> str:
    from gateway import sarvam

    return {"tts": sarvam.TTS_MODEL}.get(call, "-")


# ---- the run ---------------------------------------------------------------------------------------------------


@contextlib.contextmanager
def _quiet_logs() -> Iterator[io.StringIO]:
    """The worker's logs at WARNING into a buffer for the run, never printed; the previous setup comes back after."""
    from core import logging as klog

    root = logging.getLogger()
    level, handlers = root.level, [h for h in root.handlers if getattr(h, "_kfin", False)]
    hooks = (sys.excepthook, threading.excepthook)
    buffer = io.StringIO()
    klog.configure("WARNING", stream=buffer)
    try:
        yield buffer
    finally:
        for h in [h for h in root.handlers if getattr(h, "_kfin", False)]:
            root.removeHandler(h)
        for h in handlers:
            root.addHandler(h)
        root.setLevel(level)
        sys.excepthook, threading.excepthook = hooks


def _child_env() -> dict[str, str]:
    """The environment for the dbmate container: the key never goes to a child process."""
    return {k: v for k, v in os.environ.items() if k != "SARVAM_API_KEY"}


def _admin_url() -> str:
    from core.config import get_settings

    return os.environ.get(
        "TEST_ADMIN_DATABASE_URL",
        f"postgres://ideas:ideas@localhost:{get_settings().postgres_port}/postgres?sslmode=disable",
    )


def _db_url(name: str, host: str = "localhost") -> str:
    from core.config import get_settings

    port = 5432 if host == "postgres" else get_settings().postgres_port
    return f"postgres://ideas:ideas@{host}:{port}/{name}?sslmode=disable"


@contextlib.contextmanager
def throwaway_database() -> Iterator[str]:
    """Created, migrated with the real dbmate container, dropped at the end even on failure: the same way as the
    tests' `test_database` fixture (tests/conftest.py, tests/helpers.py)."""
    import psycopg

    from core.config import REPO_ROOT

    name = f"{DB_PREFIX}_{secrets.token_hex(4)}"
    try:
        with psycopg.connect(_admin_url(), autocommit=True) as admin:
            admin.execute(f'CREATE DATABASE "{name}"')
    except Exception:
        raise _NoDatabase from None
    try:
        compose = ["docker", "compose", "-f", "infra/docker-compose.yml", "--project-directory", "."]
        migrate = subprocess.run(
            [
                *compose,
                "--env-file",
                ".env",
                "run",
                "--rm",
                "-T",
                "-e",
                f"DATABASE_URL={_db_url(name, 'postgres')}",
                "dbmate",
                "up",
            ],
            cwd=REPO_ROOT,
            env=_child_env(),
            capture_output=True,  # never printed: compose may echo settings
            text=True,
            check=False,
        )
        if migrate.returncode != 0:
            raise _NoDatabase
        yield name
    finally:
        with psycopg.connect(_admin_url(), autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


@contextlib.contextmanager
def _env(**values: str) -> Iterator[None]:
    """Set variables for this process only, and put them back after."""
    from core.config import get_settings

    old = {k: os.environ.get(k) for k in values}
    os.environ.update(values)
    get_settings.cache_clear()
    try:
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        get_settings.cache_clear()


def run(calls: Sequence[str], *, out: TextIO, database: str | None = None) -> int:
    """Run the checks in order and print one line each, then the summary. `database` is a database that already
    exists (the tests' fixture); without it the check makes and drops its own."""
    with _quiet_logs() as logs:
        if database is not None:
            return _run_in(database, calls, out, logs)
        try:
            with throwaway_database() as name:
                return _run_in(name, calls, out, logs)
        except _NoDatabase:
            print(NO_DATABASE, file=out)
            return 1


def _run_in(name: str, calls: Sequence[str], out: TextIO, logs: io.StringIO) -> int:
    from core import killswitch
    from core.db import connect
    from pii.log_rules import scan_log_lines

    lines: list[Line] = []
    with _env(DATABASE_URL=_db_url(name), SPEECH_MODE="sarvam", SPEECH_HOSTED_APPROVAL=APPROVAL):
        killswitch.clear_cache()
        conn = connect(_db_url(name), autocommit=True)
        try:
            row = conn.execute("SELECT state FROM kill_switches WHERE name = %s", (SPEECH_HOSTED,)).fetchone()
            before = row["state"] if row else None
            if before != "on":
                killswitch.set_switch(
                    conn,
                    SPEECH_HOSTED,
                    "on",
                    reason="Live check: on in its own database (BLD-C177)",
                    actor=ACTOR,
                )
            state = _Run(conn=conn, out=out)
            for call in calls:
                try:
                    line = CHECKS[call](state)
                except Exception as exc:  # the type only: a message could quote a reply
                    line = Line(call, _model(call), reason=f"error_{type(exc).__name__.lower()}"[:40])
                lines.append(line)
                print(line.render(), file=out, flush=True)
            if before is not None and before != "on":
                killswitch.set_switch(
                    conn, SPEECH_HOSTED, before, reason="Live check: as it was before (BLD-C177)", actor=ACTOR
                )
        finally:
            conn.close()
            killswitch.clear_cache()
    warnings = [line for line in logs.getvalue().splitlines() if line.strip()]
    logs_ok = not scan_log_lines(warnings) and not any(_holds_text(w) for w in warnings)
    passed = sum(1 for line in lines if line.passed)
    ok = passed == len(lines) and logs_ok
    print(
        f"summary     {passed} of {len(lines)} passed  warnings: {len(warnings)}, "
        f"IDs only: {'yes' if logs_ok else 'no'}  {'PASS' if ok else 'FAIL'}",
        file=out,
        flush=True,
    )
    return 0 if ok else 1


def _holds_text(line: str) -> bool:
    """A worker warning holding any synthetic word or the key."""
    low = line.lower()
    key = os.environ.get("SARVAM_API_KEY", "").strip()
    return any(w in low for w in MARKERS) or bool(key and key in line)


# ---- the command -----------------------------------------------------------------------------------------------


def _parse(only: str) -> list[str] | None:
    asked = [c.strip() for c in only.replace(" ", ",").split(",") if c.strip()]
    if any(c not in ALL for c in asked):
        return None
    return [c for c in ALL if c in asked] if asked else list(ALL)


def main(argv: Sequence[str] | None = None, *, out: TextIO | None = None) -> int:
    stream = out or sys.stdout
    parser = argparse.ArgumentParser(prog="sarvam-live", add_help=True)
    parser.add_argument("--only", default="", help=f"a comma-separated list of: {', '.join(ALL)}")
    args = parser.parse_args(list(argv) if argv is not None else None)
    # The key first, before anything else; from the environment only (never .env), and never printed in any form.
    if not os.environ.get("SARVAM_API_KEY", "").strip():
        print(MISSING_KEY, file=stream)
        return 2
    if os.environ.get("CI", "").strip():
        print(IN_CI, file=stream)
        return 2
    from core.config import get_settings

    get_settings.cache_clear()
    if os.environ.get("SARVAM_BASE_URL", "").strip() or get_settings().sarvam_base_url.strip():
        print(BASE_URL_SET, file=stream)
        return 2
    calls = _parse(args.only)
    if calls is None:
        print(f"ONLY takes {', '.join(ALL)}, or a comma-separated list of them.", file=stream)
        return 2
    try:
        return run(calls, out=stream)
    except BaseException as exc:  # the type only, never a message or a traceback: either could quote a reply
        if isinstance(exc, KeyboardInterrupt):
            print("sarvam-live stopped.", file=stream)
            return 130
        print(f"sarvam-live stopped: {type(exc).__name__}. Nothing more is printed.", file=stream)
        return 1


if __name__ == "__main__":
    sys.exit(main())
