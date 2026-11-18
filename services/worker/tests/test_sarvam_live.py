"""BLD-C177 (DEC-108, L-LISTEN): `make sarvam-live`, the live contract check of the Sarvam client, run here against
the fakes (`tests/sarvam_fakes.py`, a local WebSocket server at SARVAM_BASE_URL), never against Sarvam. It pins the
output format, the plain refusals (no key, CI, SARVAM_BASE_URL), the proof that a call with `speech.hosted` off
refuses before any network call, the throwaway database being dropped even on failure, and that nothing printed
holds the synthetic text or the key."""

from __future__ import annotations

import ast
import io
import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from core import killswitch
from core.config import REPO_ROOT, get_settings
from core.db import connect
from gateway import sarvam
from speech import sarvam_live
from tests import helpers
from tests.sarvam_fakes import KEY, FakeSarvamWs, ws_server

assert REPO_ROOT is not None
ROOT: Path = REPO_ROOT
MODULE = Path(sarvam_live.__file__)
LINE = re.compile(
    r"^(?P<call>[a-z_]+) +(?P<model>[a-z0-9:._-]+) +(?P<status>(?:ws|http) (?:\d+|ok|-)) +(?P<ms>\d+) ms"
    r"(?:  words: (?:yes|no))?  (?:PASS|FAIL [a-z0-9_]+)$"
)
SUMMARY = re.compile(r"^summary +\d+ of \d+ passed  warnings: \d+, IDs only: (?:yes|no)  (?:PASS|FAIL)$")


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("SARVAM_API_KEY", KEY)
    monkeypatch.setenv("SPEECH_MODE", "fake")  # the check sets sarvam for itself, and puts this back
    monkeypatch.delenv("SARVAM_BASE_URL", raising=False)
    monkeypatch.setattr(sarvam, "_sleep", lambda s: None)
    get_settings.cache_clear()
    killswitch.clear_cache()
    yield
    get_settings.cache_clear()
    killswitch.clear_cache()


def printed_is_clean(text: str) -> None:
    low = text.lower()
    assert KEY not in text
    assert not any(word in low for word in sarvam_live.MARKERS)
    assert sarvam_live.SPOKEN.lower() not in low
    assert "traceback" not in low and "http://" not in low and "ws://" not in low and "wss://" not in low
    assert "subscription" not in low


def test_BLD_C177_L_LISTEN_tts_through_listens_path_passes_against_the_fake(
    monkeypatch: pytest.MonkeyPatch, test_database: str
) -> None:
    out = io.StringIO()
    with ws_server(monkeypatch, FakeSarvamWs()) as fake:
        code = sarvam_live.run(["tts"], out=out, database=test_database)
    lines = out.getvalue().splitlines()
    assert code == 0, lines
    assert len(lines) == 2
    m = LINE.match(lines[0])
    assert m and m["call"] == "tts" and m["model"] == "bulbul:v4-flash" and m["status"] == "ws 1000"
    assert lines[0].endswith("  PASS") and "words:" not in lines[0]
    assert SUMMARY.match(lines[1]) and lines[1].endswith("IDs only: yes  PASS")
    printed_is_clean(out.getvalue())
    # One synthesis reached the fake: the refusal with speech.hosted off opened no socket.
    assert len(fake.paths) == 1 and fake.paths[0].startswith("/text-to-speech/ws?")
    kinds = [m.get("type") for m in fake.received]
    assert kinds[0] == "config" and kinds[-1] == "flush" and "text" in kinds
    # The check put the switch back on, and its process settings back as they were.
    with connect(helpers.db_url(test_database), autocommit=True) as conn:
        assert killswitch.is_on_fresh(sarvam_live.SPEECH_HOSTED, conn)
    assert get_settings().speech_mode == "fake"


def test_BLD_C177_a_call_that_ignores_the_switch_trips_the_network_guard(
    monkeypatch: pytest.MonkeyPatch, test_database: str
) -> None:
    """The proof works: a path that skips the switch reaches `_ws_open`, the tripwire fires, and the line fails."""
    from gateway import speech

    monkeypatch.setattr(speech.killswitch, "is_on_fresh", lambda name, conn=None: True)
    out = io.StringIO()
    with ws_server(monkeypatch, FakeSarvamWs()) as fake:
        code = sarvam_live.run(["tts"], out=out, database=test_database)
    lines = out.getvalue().splitlines()
    assert code == 1
    assert LINE.match(lines[0]) and lines[0].endswith("FAIL refusal_reached_network")
    assert lines[1].endswith("FAIL")
    assert len(fake.paths) == 1  # the tripwire stood in for the second connection
    printed_is_clean(out.getvalue())


def test_BLD_C177_a_failed_call_prints_our_code_never_the_reply(
    monkeypatch: pytest.MonkeyPatch, test_database: str
) -> None:
    class Failing(FakeSarvamWs):
        def _tts(self, ws: Any) -> None:
            for raw in ws:  # Sarvam's error shape, its message quoting the text: never printed
                if json.loads(raw).get("type") == "flush":
                    ws.send(
                        '{"type": "error", "data": {"message": "printer paper chairs meeting", "code": 400}}'
                    )
                    return

    out = io.StringIO()
    with ws_server(monkeypatch, Failing()):
        code = sarvam_live.run(["tts"], out=out, database=test_database)
    lines = out.getvalue().splitlines()
    assert code == 1
    assert LINE.match(lines[0]) and lines[0].endswith("FAIL hosted_tts_error")
    printed_is_clean(out.getvalue())


@pytest.mark.parametrize("value", [None, "", "   "])
def test_BLD_C177_without_the_key_it_says_so_plainly_and_stops_first(
    monkeypatch: pytest.MonkeyPatch, value: str | None
) -> None:
    if value is None:
        monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    else:
        monkeypatch.setenv("SARVAM_API_KEY", value)
    monkeypatch.setenv("CI", "true")  # the key is checked before anything else
    monkeypatch.setattr(sarvam_live, "run", _never)
    out = io.StringIO()
    assert sarvam_live.main(["--only", "tts"], out=out) == 2
    assert out.getvalue() == "SARVAM_API_KEY is not set. Load it in your own terminal and run this again.\n"


def test_BLD_C177_it_refuses_in_ci(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CI", "true")
    monkeypatch.setattr(sarvam_live, "run", _never)
    out = io.StringIO()
    assert sarvam_live.main([], out=out) == 2
    assert out.getvalue() == sarvam_live.IN_CI + "\n"
    printed_is_clean(out.getvalue())


def test_BLD_C177_it_refuses_a_base_url_so_it_can_only_reach_sarvam(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setenv("SARVAM_BASE_URL", "http://127.0.0.1:9")
    monkeypatch.setattr(sarvam_live, "run", _never)
    out = io.StringIO()
    assert sarvam_live.main([], out=out) == 2
    assert out.getvalue() == sarvam_live.BASE_URL_SET + "\n"
    printed_is_clean(out.getvalue())


def test_BLD_C177_only_takes_known_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setattr(sarvam_live, "run", _never)
    assert sarvam_live._parse("") == list(sarvam_live.ALL)
    assert sarvam_live._parse("tts") == ["tts"]
    assert sarvam_live._parse("tts, nope") is None
    out = io.StringIO()
    assert sarvam_live.main(["--only", "nope"], out=out) == 2
    assert out.getvalue().startswith("ONLY takes tts")


def test_BLD_C177_the_throwaway_database_is_dropped_even_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess

    import psycopg

    sql: list[str] = []
    envs: list[dict[str, str]] = []

    class Admin:
        def __enter__(self) -> Admin:
            return self

        def __exit__(self, *exc: object) -> None:
            return None

        def execute(self, statement: str) -> None:
            sql.append(statement)

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        envs.append(kwargs["env"])
        assert cmd[-2:] == ["dbmate", "up"] and "config" not in cmd and "inspect" not in cmd
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(psycopg, "connect", lambda *a, **k: Admin())
    monkeypatch.setattr(sarvam_live.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError), sarvam_live.throwaway_database() as name:
        assert name.startswith("sarvam_live_")
        raise RuntimeError
    assert sql[0].startswith('CREATE DATABASE "sarvam_live_') and sql[-1].startswith(
        'DROP DATABASE IF EXISTS "sarvam_live_'
    )
    assert "SARVAM_API_KEY" not in envs[0]  # the key never goes to a child process

    sql.clear()
    monkeypatch.setattr(
        sarvam_live.subprocess, "run", lambda cmd, **k: subprocess.CompletedProcess(cmd, 1, "", "")
    )
    with pytest.raises(sarvam_live._NoDatabase), sarvam_live.throwaway_database():
        pass
    assert sql[-1].startswith("DROP DATABASE IF EXISTS")


def test_BLD_C177_no_database_is_one_plain_line(monkeypatch: pytest.MonkeyPatch) -> None:
    import psycopg

    def refuse(*_a: Any, **_k: Any) -> None:
        raise psycopg.OperationalError("connection refused at a host")

    monkeypatch.setattr(psycopg, "connect", refuse)
    out = io.StringIO()
    assert sarvam_live.run(["tts"], out=out) == 1
    assert out.getvalue() == sarvam_live.NO_DATABASE + "\n"


def test_BLD_C177_the_check_uses_no_sdk_and_no_raw_http_or_websockets() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert not imported & {"httpx", "websockets", "sarvamai", "requests", "urllib3", "aiohttp"}


def test_BLD_C177_the_make_target_never_puts_the_key_on_a_command_line() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    recipe = makefile.split("\nsarvam-live:", 1)[1].split("\n\n", 1)[0]
    assert "speech.sarvam_live" in recipe and "SPEECH_MODE=sarvam" in recipe
    assert "SARVAM_API_KEY" not in recipe and "sarvam.env" not in recipe and ".config" not in recipe


def _never(*_a: Any, **_k: Any) -> int:
    raise AssertionError("the check ran when it should have refused first")
