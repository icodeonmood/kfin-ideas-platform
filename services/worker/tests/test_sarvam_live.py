"""BLD-C177 (DEC-108, L-LISTEN, L-DRAFT.voice): `make sarvam-live`, the live contract check of the Sarvam client,
run here against the fakes (`tests/sarvam_fakes.py`: a local WebSocket server at SARVAM_BASE_URL, and an httpx
MockTransport for the REST calls), never against Sarvam. The decoder is passed in, so CI (Linux) never needs macOS's
afconvert. It pins the output format, the plain refusals (no key, CI, SARVAM_BASE_URL), the proof that a call with
`speech.hosted` off refuses before any network call, the throwaway database being dropped even on failure, and that
nothing printed holds the synthetic text or the key."""

from __future__ import annotations

import ast
import io
import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any, ClassVar

import httpx
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
SUMMARY = re.compile(
    r"^summary +\d+ of \d+ passed  log lines: \d+, IDs only: (?:yes|no)  (?:PASS|FAIL)(?:  \([^()]+\))?$"
)
# What the fakes hear and translate: synthetic, with a word of each spoken sentence.
HEARD_TEXT = "The printer near the lift is out of paper. Please order more chairs for the meeting room."
ENGLISH = "The office printer has not worked since yesterday, please order new toner."
PCM = bytes(3 * sarvam_live.CHUNK_BYTES)  # three seconds of silence: the fakes do not decode audio


def rest_fake(monkeypatch: pytest.MonkeyPatch) -> list[httpx.Request]:
    """Sarvam's REST replies, in the documented shapes (docs.sarvam.ai, 18 Nov 2026)."""
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/speech-to-text":
            return httpx.Response(
                200,
                json={
                    "request_id": "req-1",
                    "transcript": HEARD_TEXT,
                    "language_code": "en-IN",
                    "timestamps": {
                        "words": ["a", "b"],
                        "start_time_seconds": [0.0, 2.1],
                        "end_time_seconds": [2.0, 4.4],
                    },
                },
            )
        if request.url.path == "/translate":
            return httpx.Response(
                200, json={"request_id": "req-2", "translated_text": ENGLISH, "source_language_code": "hi-IN"}
            )
        return httpx.Response(404, json={"error": {"message": "not here", "code": "not_found_error"}})

    monkeypatch.setattr(sarvam, "_transport", httpx.MockTransport(handle))
    return seen


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
    assert sarvam_live.SENTINEL not in text  # the stored-output sentinel is never printed


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


def test_BLD_C177_L_DRAFT_voice_all_four_calls_pass_through_the_workers_paths_against_the_fakes(
    monkeypatch: pytest.MonkeyPatch, test_database: str
) -> None:
    rest = rest_fake(monkeypatch)
    decoded: list[bytes] = []

    def decode(mp3: bytes) -> bytes:
        decoded.append(mp3)
        return PCM

    out = io.StringIO()
    with ws_server(monkeypatch, FakeSarvamWs(heard=HEARD_TEXT)) as fake:
        code = sarvam_live.run(
            list(sarvam_live.ALL), out=out, database=test_database, decode=decode, pace_s=0
        )
    lines = out.getvalue().splitlines()
    assert code == 0, lines
    assert [x.split()[0] for x in lines[:4]] == ["tts", "stt_rest", "stt_stream", "translate"]
    want = {
        "tts": ("bulbul:v4-flash", "ws 1000", False),
        "stt_rest": ("saaras:v4", "http 200", True),
        "stt_stream": ("saaras:v4", "ws 1000", True),
        "translate": ("mayura:v1", "http 200", False),
    }
    for text in lines[:4]:
        m = LINE.match(text)
        assert m, text
        model, status, words = want[m["call"]]
        assert (m["model"], m["status"]) == (model, status), text
        assert ("  words: yes  " in text) is words and text.endswith("  PASS")
    assert (
        SUMMARY.match(lines[4])
        and lines[4].startswith("summary     4 of 4 passed")
        and lines[4].endswith("PASS")
    )
    printed_is_clean(out.getvalue())
    # The decoder got the tts MP3 once; both speech-to-text calls heard its PCM.
    assert len(decoded) == 1 and decoded[0][:2] == b"\xff\xf3"
    stt = [r for r in rest if r.url.path == "/speech-to-text"]
    assert len(stt) == 1 and b"RIFF" in stt[0].content and b"saaras:v4" in stt[0].content
    assert fake.audio == PCM  # relayed unchanged, a second at a time
    assert sum(1 for m in fake.received if "audio" in m) == 3
    # One socket per call; every refusal with speech.hosted off reached no network entry point.
    assert [p.split("?")[0] for p in fake.paths] == ["/text-to-speech/ws", "/speech-to-text/ws"]
    translate = [json.loads(r.content) for r in rest if r.url.path == "/translate"]
    assert translate and all(t["model"] == "mayura:v1" and t["mode"] == "code-mixed" for t in translate)
    assert "speaker_gender" not in translate[-1]


def test_BLD_C177_without_afconvert_speech_to_text_fails_with_no_decoder_and_tts_still_runs(
    monkeypatch: pytest.MonkeyPatch, test_database: str
) -> None:
    rest_fake(monkeypatch)

    def no_decoder(mp3: bytes) -> bytes:
        raise sarvam_live.DecodeFailed("no_decoder")

    out = io.StringIO()
    with ws_server(monkeypatch, FakeSarvamWs(heard=HEARD_TEXT)) as fake:
        code = sarvam_live.run(
            list(sarvam_live.ALL), out=out, database=test_database, decode=no_decoder, pace_s=0
        )
    lines = out.getvalue().splitlines()
    assert code == 1
    assert lines[0].startswith("tts ") and lines[0].endswith("PASS")
    assert lines[1].startswith("stt_rest ") and lines[1].endswith("FAIL no_decoder")
    assert lines[2].startswith("stt_stream ") and lines[2].endswith("FAIL no_decoder")
    assert lines[3].startswith("translate ") and lines[3].endswith("PASS")
    assert SUMMARY.match(lines[4]) and lines[4].endswith(f"FAIL  ({sarvam_live.NO_DECODER_NOTE})")
    assert [p.split("?")[0] for p in fake.paths] == ["/text-to-speech/ws"]
    printed_is_clean(out.getvalue())


def test_BLD_C177_afconvert_runs_as_a_list_without_the_key_in_a_private_folder_removed_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import subprocess

    calls: list[tuple[list[str], dict[str, Any]]] = []
    folders: list[Path] = []

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        calls.append((cmd, kwargs))
        folders.append(Path(cmd[-1]).parent)
        assert Path(cmd[-2]).read_bytes() == b"mp3 bytes"
        with __import__("wave").open(cmd[-1], "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(bytes(64))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(sarvam_live.shutil, "which", lambda name: "/usr/bin/afconvert")
    monkeypatch.setattr(sarvam_live.subprocess, "run", fake_run)
    assert sarvam_live.afconvert_pcm(b"mp3 bytes") == bytes(64)
    cmd, kwargs = calls[0]
    assert cmd[:7] == ["/usr/bin/afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1"]
    assert "shell" not in kwargs and "SARVAM_API_KEY" not in kwargs["env"]
    assert kwargs["stdout"] is subprocess.DEVNULL and kwargs["stderr"] is subprocess.DEVNULL
    assert not folders[0].exists()  # removed at the end

    monkeypatch.setattr(sarvam_live.subprocess, "run", lambda cmd, **k: subprocess.CompletedProcess(cmd, 1))
    with pytest.raises(sarvam_live.DecodeFailed) as failed:
        sarvam_live.afconvert_pcm(b"mp3 bytes")
    assert failed.value.code == "decode_failed"

    monkeypatch.setattr(sarvam_live.shutil, "which", lambda name: None)
    with pytest.raises(sarvam_live.DecodeFailed) as missing:
        sarvam_live.afconvert_pcm(b"mp3 bytes")
    assert missing.value.code == "no_decoder"


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
    assert sarvam_live._parse("translate") == ["translate"]
    assert sarvam_live._parse("stt_stream,tts") == ["tts", "stt_stream"]
    assert sarvam_live._parse("stt_rest") == ["tts", "stt_rest"]  # speech to text hears what tts made
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


# ---- review round 1 (BLD-C177): masking proven, not counted; no traceback; logs at INFO; signals; meter fields ----


def all_four(
    monkeypatch: pytest.MonkeyPatch, test_database: str
) -> tuple[int, list[str], FakeSarvamWs, list[Any]]:
    rest = rest_fake(monkeypatch)
    out = io.StringIO()
    with ws_server(monkeypatch, FakeSarvamWs(heard=HEARD_TEXT)) as fake:
        code = sarvam_live.run(
            list(sarvam_live.ALL), out=out, database=test_database, decode=lambda mp3: PCM, pace_s=0
        )
    printed_is_clean(out.getvalue())
    sent = json.dumps(fake.received, ensure_ascii=False) + "".join(
        r.content.decode("utf-8", "replace") for r in rest
    )
    assert sarvam_live.SENTINEL not in sent and "\\u200b" not in sent  # never sent to Sarvam
    return code, out.getvalue().splitlines(), fake, rest


def test_BLD_C177_each_masking_function_tags_a_synthetic_vector() -> None:
    assert sarvam_live.maskers_tag() == dict.fromkeys(sarvam_live.MASKERS, True)


def test_BLD_C177_L_LISTEN_text_handed_on_that_is_not_the_masking_output_fails_tts(
    monkeypatch: pytest.MonkeyPatch, test_database: str
) -> None:
    from speech import listen

    real = listen.outgoing

    def copies(
        script: Any,
    ) -> list[tuple[str, str]]:  # equal text, but not the object mask_for_service returned
        return [(part, "".join(list(text))) for part, text in real(script)]

    monkeypatch.setattr(listen, "outgoing", copies)
    code, lines, _fake, _rest = all_four(monkeypatch, test_database)
    assert code == 1 and lines[0].startswith("tts ") and lines[0].endswith("FAIL not_masked")


def test_BLD_C177_a_voice_note_transcript_that_is_not_the_masking_output_fails_stt_rest(
    monkeypatch: pytest.MonkeyPatch, test_database: str
) -> None:
    from voice import service as voice_notes

    real = voice_notes.status

    def altered(conn: Any, voice_id: str, idea_uuid: str) -> dict[str, Any] | None:
        view = real(conn, voice_id, idea_uuid)
        return (
            {**view, "transcript": view["transcript"] + " again"} if view and "transcript" in view else view
        )

    monkeypatch.setattr(voice_notes, "status", altered)
    code, lines, _fake, _rest = all_four(monkeypatch, test_database)
    assert code == 1 and lines[1].startswith("stt_rest ") and lines[1].endswith("FAIL not_masked")
    assert lines[0].endswith("PASS") and lines[2].endswith("PASS") and lines[3].endswith("PASS")


def test_BLD_C177_L_DRAFT_voice_a_masking_function_that_tags_nothing_fails_and_the_vector_never_leaves(
    monkeypatch: pytest.MonkeyPatch, test_database: str
) -> None:
    from pii import vectors
    from speech import drafts
    from speech.adapters import Hidden

    monkeypatch.setattr(drafts, "hide_text", lambda text: Hidden(text=text, spans=[], count=0))  # a no-op
    code, lines, fake, rest = all_four(monkeypatch, test_database)
    assert code == 1
    assert lines[0].endswith("PASS") and lines[1].endswith("PASS")
    assert lines[2].startswith("stt_stream ") and lines[2].endswith("FAIL masking_no_op")
    assert lines[3].startswith("translate ") and lines[3].endswith("FAIL masking_no_op")
    vector = next(v for v in vectors.build(n=1)["vectors"] if v["expect"]["blocks"])
    sent = json.dumps(fake.received, ensure_ascii=False) + "".join(
        r.content.decode("utf-8", "replace") for r in rest
    )
    value = vector["text"][vector["python"][0]["start"] : vector["python"][0]["end"]]
    assert vector["text"] not in sent and value not in sent and value not in "\n".join(lines)


def test_BLD_C177_the_summary_scans_logs_at_info(monkeypatch: pytest.MonkeyPatch, test_database: str) -> None:
    import logging

    from core.logging import get_logger

    real = sarvam_live.CHECKS["tts"]

    def noisy(run: Any) -> sarvam_live.Line:
        get_logger("voice").info("voice.ready", voice_id="printer paper")  # text in an INFO line
        return real(run)

    monkeypatch.setitem(sarvam_live.CHECKS, "tts", noisy)
    before = logging.getLogger().level
    out = io.StringIO()
    with ws_server(monkeypatch, FakeSarvamWs()):
        code = sarvam_live.run(["tts"], out=out, database=test_database)
    lines = out.getvalue().splitlines()
    assert code == 1 and lines[0].endswith("PASS") and lines[1].endswith("IDs only: no  FAIL")
    assert logging.getLogger().level == before
    printed_is_clean(out.getvalue())


def test_BLD_C177_an_uncaught_exception_prints_its_type_only(capsys: pytest.CaptureFixture[str]) -> None:
    import sys
    import threading

    before = (sys.excepthook, threading.excepthook)
    with sarvam_live._quiet_logs():
        try:
            raise ValueError("printer paper " + KEY)
        except ValueError as exc:
            sys.excepthook(type(exc), exc, exc.__traceback__)

        def boom() -> None:
            raise RuntimeError("chairs meeting " + KEY)

        worker = threading.Thread(target=boom)
        worker.start()
        worker.join()
    assert (sys.excepthook, threading.excepthook) == before
    err = capsys.readouterr().err
    assert "sarvam-live stopped: ValueError." in err and "background thread stopped: RuntimeError." in err
    printed_is_clean(err)


def test_BLD_C177_a_settings_error_is_one_plain_line(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setenv(
        "POSTGRES_PORT", "printer-paper"
    )  # pydantic refuses it, quoting the value in its message
    monkeypatch.setattr(sarvam_live, "run", _never)
    get_settings.cache_clear()
    out = io.StringIO()
    assert sarvam_live.main([], out=out) == 1
    assert out.getvalue() == "sarvam-live stopped: ValidationError. Nothing more is printed.\n"
    printed_is_clean(out.getvalue())


class Admin:
    """psycopg's admin connection, recording SQL; `on_create` runs when CREATE DATABASE is sent."""

    sql: ClassVar[list[str]] = []
    on_create: ClassVar[Any] = None

    def __enter__(self) -> Admin:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, statement: str) -> None:
        Admin.sql.append(statement)
        if statement.startswith("CREATE") and Admin.on_create:
            Admin.on_create()


@pytest.fixture
def admin(monkeypatch: pytest.MonkeyPatch) -> type[Admin]:
    import subprocess

    import psycopg

    Admin.sql, Admin.on_create = [], None
    monkeypatch.setattr(psycopg, "connect", lambda *a, **k: Admin())
    monkeypatch.setattr(
        sarvam_live.subprocess, "run", lambda cmd, **k: subprocess.CompletedProcess(cmd, 0, "", "")
    )
    return Admin


def test_BLD_C177_sigterm_ends_the_run_and_the_database_is_still_dropped(
    monkeypatch: pytest.MonkeyPatch, admin: type[Admin]
) -> None:
    import os
    import signal
    import time

    before = (signal.getsignal(signal.SIGTERM), signal.getsignal(signal.SIGHUP))

    def killed(*_a: Any) -> int:
        os.kill(os.getpid(), signal.SIGTERM)
        time.sleep(5)
        raise AssertionError("SIGTERM did not end the run")

    monkeypatch.setattr(sarvam_live, "_run_in", killed)
    with pytest.raises(KeyboardInterrupt):
        sarvam_live.run(["tts"], out=io.StringIO())
    assert admin.sql[-1].startswith('DROP DATABASE IF EXISTS "sarvam_live_')
    assert (signal.getsignal(signal.SIGTERM), signal.getsignal(signal.SIGHUP)) == before


def test_BLD_C177_an_interrupted_create_is_dropped_too(admin: type[Admin]) -> None:
    def interrupted() -> None:
        raise KeyboardInterrupt

    admin.on_create = interrupted
    with pytest.raises(KeyboardInterrupt), sarvam_live.throwaway_database():
        pass
    name = admin.sql[0].split('"')[1]
    assert admin.sql == [f'CREATE DATABASE "{name}"', f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)']


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("error_code", "Printer Paper failed"),
        ("error_code", "hosted error: see body"),
        ("ref_id", "the meeting room"),
        ("ref_id", "idea:not-a-uuid"),
    ],
)
def test_BLD_C177_a_speech_calls_row_with_free_text_fails(column: str, value: str) -> None:
    row = {
        "call": "tts", "model": "bulbul:v4-flash", "ref_id": "idea:11111111-2222-4333-8444-555555555555",
        "outcome": "ok", "error_code": None, "speech_seconds": None, "char_count": 90, "latency_ms": 5, "cost_inr": 0,
    }  # fmt: skip
    row[column] = value

    class Rows:
        def execute(self, sql: str, params: Any = ()) -> Any:
            return type("R", (), {"fetchall": lambda self: [row]})()

    assert sarvam_live._metered(Rows(), 0, "tts", "bulbul:v4-flash", 1) == "meter_text"
    row[column] = None if column == "error_code" else "stream:11111111-2222-4333-8444-555555555555"
    assert sarvam_live._metered(Rows(), 0, "tts", "bulbul:v4-flash", 1) is None


# ---- review round 2 (BLD-C177): a path that ignores its masker's output fails; codes are the gateway's own ----


def test_BLD_C177_L_LISTEN_tts_that_discards_the_masking_output_fails(
    monkeypatch: pytest.MonkeyPatch, test_database: str
) -> None:
    from speech import listen
    from speech.adapters import spoken

    def discarding(script: Any) -> list[tuple[str, str]]:  # masks, then hands on its own input
        texts = [(p.part, spoken(p.title, p.text)) for p in listen._ordered(script)]
        for _part, text in texts:
            listen.mask_for_service(text)
            sarvam.check_masked(text)
        return texts

    monkeypatch.setattr(listen, "outgoing", discarding)
    code, lines, _fake, _rest = all_four(monkeypatch, test_database)
    assert code == 1 and lines[0].startswith("tts ") and lines[0].endswith("FAIL not_masked")


def test_BLD_C177_stt_rest_that_stores_the_masking_input_fails(
    monkeypatch: pytest.MonkeyPatch, test_database: str
) -> None:
    from voice import service as voice_notes

    seen: dict[str, str] = {}
    real_normalise, real_encrypt = voice_notes.normalise, voice_notes.encrypt_bytes

    def normalise(text: str) -> str:
        seen["input"] = real_normalise(text)
        return seen["input"]

    def encrypt(plain: bytes, context: str, *args: Any, **kwargs: Any) -> bytes:
        if context.startswith("voice:"):  # stores what went into leave_out_blocked, not what came out
            plain = json.dumps({"text": seen["input"]}).encode()
        return real_encrypt(plain, context, *args, **kwargs)

    monkeypatch.setattr(voice_notes, "normalise", normalise)
    monkeypatch.setattr(voice_notes, "encrypt_bytes", encrypt)
    code, lines, _fake, _rest = all_four(monkeypatch, test_database)
    assert code == 1 and lines[1].startswith("stt_rest ") and lines[1].endswith("FAIL not_masked")


def test_BLD_C177_L_DRAFT_voice_stt_stream_that_keeps_the_masking_input_fails(
    monkeypatch: pytest.MonkeyPatch, test_database: str
) -> None:
    from speech import drafts

    seen: dict[str, str] = {}
    real_bytes, real_json = drafts.encrypt_bytes, drafts.encrypt_json

    def sealed(plain: bytes, context: str, *args: Any, **kwargs: Any) -> bytes:
        if context.startswith("voice_streams.own_words:"):
            seen["own"] = plain.decode()
        return real_bytes(plain, context, *args, **kwargs)

    def kept(value: dict[str, Any], context: str, *args: Any, **kwargs: Any) -> bytes:
        if context.startswith("voice_streams.masked:"):  # keeps what went into hide_text, not what came out
            value = {"text": seen["own"]}
        return real_json(value, context, *args, **kwargs)

    monkeypatch.setattr(drafts, "encrypt_bytes", sealed)
    monkeypatch.setattr(drafts, "encrypt_json", kept)
    code, lines, _fake, _rest = all_four(monkeypatch, test_database)
    assert code == 1 and lines[2].startswith("stt_stream ") and lines[2].endswith("FAIL not_masked")


def test_BLD_C177_L_DRAFT_voice_translate_that_discards_the_masking_output_fails(
    monkeypatch: pytest.MonkeyPatch, test_database: str
) -> None:
    from speech import drafts

    def discarding(
        conn: Any, stream_id: str, masked: str, lang: str | None, user_id: str | None, **_k: Any
    ) -> tuple[
        str | None, bool | None, str | None
    ]:  # masks both ways, then uses its own input and Sarvam's reply
        drafts.mask_for_service(masked)
        got = sarvam.translate(masked, conn=conn, ref_id=f"stream:{stream_id}", source=lang or "auto")
        drafts.hide_text(got.text)
        return got.text, got.translated, None

    monkeypatch.setattr(drafts, "_english", discarding)
    code, lines, _fake, _rest = all_four(monkeypatch, test_database)
    assert code == 1 and lines[3].startswith("translate ") and lines[3].endswith("FAIL not_masked")


def test_BLD_C177_an_error_code_must_be_one_of_the_workers_own() -> None:
    row = {
        "call": "tts", "model": "bulbul:v4-flash", "ref_id": None, "outcome": "route_error", "error_code": "printer",
        "speech_seconds": None, "char_count": 90, "latency_ms": 5, "cost_inr": 0,
    }  # fmt: skip

    class Rows:
        def execute(self, sql: str, params: Any = ()) -> Any:
            return type("R", (), {"fetchall": lambda self: [row]})()

    assert sarvam_live._metered(Rows(), 0, "tts", "bulbul:v4-flash", 1) == "meter_text"  # one lowercase word
    row["error_code"] = "hosted_403"
    assert (
        sarvam_live._metered(Rows(), 0, "tts", "bulbul:v4-flash", 1) == "meter_outcome"
    )  # ours, but a failure


def test_BLD_C177_the_code_prefixes_are_the_gateways_own() -> None:
    found: set[str] = set()
    for name in ("sarvam.py", "speech.py"):
        src = (ROOT / "services" / "worker" / "gateway" / name).read_text(encoding="utf-8")
        found |= set(re.findall(r'(?:SarvamFailed|SpeechUnavailable|HostedRefused)\(\s*"([a-z0-9_]+)"', src))
        found |= set(re.findall(r'(?<!outcome, )\b(?:code|_failure)\s*=\s*"([a-z0-9_]+)"', src))
        found |= {p + "403" for p in re.findall(r'(?:SpeechUnavailable\(|\bcode\s*=\s*)f"([a-z]+_)\{', src)}
    assert len(found) >= 20, sorted(found)
    assert [c for c in sorted(found) if not sarvam_live.CODE.match(c)] == []
    assert set(sarvam_live.CODE_PREFIXES) == {c.split("_", 1)[0] + "_" for c in found}


# ---- BLD-C200 (DEC-120 fixed; L-DRAFT.voice): the English copy's text is tagged like a model call on the way out --


def test_BLD_C200_L_DRAFT_voice_the_tagging_step_tags_a_colleague_and_a_vector_and_leaves_nothing_behind(
    test_database: str,
) -> None:
    with connect(helpers.db_url(test_database), autocommit=True) as conn:
        before = conn.execute(
            "SELECT (SELECT count(*) FROM users) AS users, (SELECT count(*) FROM pseudonym_vault) AS vault"
        ).fetchone()
        assert sarvam_live.tagger_tags(conn) is True
        after = conn.execute(
            "SELECT (SELECT count(*) FROM users) AS users, (SELECT count(*) FROM pseudonym_vault) AS vault"
        ).fetchone()
        assert after == before  # the synthetic colleague and the vault rows were rolled back
        assert conn.execute("SELECT 1 FROM users WHERE name = %s", (sarvam_live.TAG_NAME,)).fetchone() is None


def test_BLD_C200_L_DRAFT_voice_translate_that_sends_the_untagged_text_fails(
    monkeypatch: pytest.MonkeyPatch, test_database: str
) -> None:
    from speech import drafts

    def untagged(
        conn: Any, stream_id: str, masked: str, lang: str | None, user_id: str | None, *, idea_uuid: str
    ) -> tuple[str | None, bool | None, str | None]:  # tags, then sends the copy from before the tags
        out = drafts.mask_for_service(masked)
        sarvam.tag_for_service(out, conn=conn, scope_id=f"DRAFT-{idea_uuid}")
        got = sarvam.translate(out, conn=conn, ref_id=f"stream:{stream_id}", source=lang or "auto")
        return drafts.hide_text(got.text).text, got.translated, None

    monkeypatch.setattr(drafts, "_english", untagged)
    code, lines, _fake, _rest = all_four(monkeypatch, test_database)
    assert code == 1 and lines[3].startswith("translate ") and lines[3].endswith("FAIL not_masked")


def test_BLD_C200_L_DRAFT_voice_a_tagging_step_that_tags_nothing_fails_and_the_name_never_leaves(
    monkeypatch: pytest.MonkeyPatch, test_database: str
) -> None:
    monkeypatch.setattr(sarvam, "tag_for_service", lambda text, **k: sarvam.Outgoing(text=text, tags={}))
    code, lines, fake, rest = all_four(monkeypatch, test_database)
    assert code == 1 and lines[0].endswith("PASS") and lines[1].endswith("PASS")
    assert lines[2].startswith("stt_stream ") and lines[2].endswith("FAIL masking_no_op")
    assert lines[3].startswith("translate ") and lines[3].endswith("FAIL masking_no_op")
    sent = json.dumps(fake.received, ensure_ascii=False) + "".join(
        r.content.decode("utf-8", "replace") for r in rest
    )
    assert sarvam_live.TAG_NAME not in sent and sarvam_live.TAG_NAME not in "\n".join(lines)
