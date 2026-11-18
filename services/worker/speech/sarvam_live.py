"""`make sarvam-live`: the live contract check of the Sarvam client (BLD-C177; DEC-108; L-LISTEN, L-DRAFT.voice).

The product lead runs it in their own terminal, with `SARVAM_API_KEY` loaded there, before the gates. It never runs
in CI: it refuses when `CI` is set, it is not a test pytest collects, and CI keeps `SPEECH_MODE=fake` with no secret.
It refuses `SARVAM_BASE_URL` too, so it can only reach the real API. Every call goes through the worker's own code
path, never an SDK and never raw httpx or websockets here:

| Call | The worker's path | Model |
|---|---|---|
| `tts` | Listen: `listen.outgoing` (masked for the service, leak-checked), then `listen._synthesise` into `gateway.sarvam.tts`; the audio parsed as Listen parses it | bulbul:v4-flash |
| `stt_rest` | Voice notes, the service itself: `voice.service.transcribe` on a note of the check's own draft (scan, probe, `gateway.speech.transcribe` into `gateway.sarvam.stt_rest`, `leave_out_blocked` on return), read back with `voice.service.status` | saaras:v4, codemix |
| `stt_stream` | Drafts "By voice": `speech.drafts.start`, `chunk` (one second of PCM at a time, a second apart, as the browser sends it), `end`, into `gateway.sarvam.stt_stream`; masked on return by `hide_text` | saaras:v4, codemix |
| `translate` | The English copy: `speech.drafts._english` (masked for the service, into `gateway.sarvam.translate`, masked again on return) | mayura:v1, code-mixed |

The speech-to-text calls hear the audio tts made, decoded to 16 kHz mono s16le by macOS's own `afconvert` (no new
dependency): as a WAV file for the REST call, as raw one-second chunks for the stream. `ONLY=stt_rest` (or
`stt_stream`) runs tts first for that reason. Without `afconvert` (not macOS), both fail with `no_decoder` and tts
still runs. Stood in for, in memory: Listen's audio store, the drafts' stream store, and for the voice note its
quarantine bucket (read and delete) and the virus scan (clean). Their SQL and I/O are covered by the tests.

Per call it checks that the reply parses the way our code expects; that the text was masked on its way through the
worker, in two parts: the text the path hands on (to Sarvam, or back to its caller) is what the real masking function
returned for that call, and, before any network call, each masking function tags a synthetic vector from
`pii.vectors` (which never leaves the process); that `speech_calls` has its row (call, model, outcome, our codes and
IDs only, no text in any column); and that with `speech.hosted` off the same call refuses before any network call:
the client's two network entry points (`gateway.sarvam._post` and `_ws_open`) are replaced by tripwires, and reaching
either fails the check. For speech to text it also checks that a word of each spoken sentence came back,
which shows tts spoke both sentences sent before one flush.

Synthetic text only, written here: ordinary office words, no names, nothing shaped like a folio, PAN, phone number,
email, account number or amount. The only audio is what tts makes.

The check makes its own throwaway database the way the tests' `test_database` fixture does (created on the local
stack's Postgres, migrated with the dbmate container, dropped at the end even on failure; `make up` must be running),
with `speech.hosted` on inside it. It never touches the demo database or any other.

Output: one line per call (the call, model, status, latency in ms, for speech to text whether the words came back,
then PASS or FAIL with our own reason code), then a summary. It never prints text, audio, the key, a header, a URL or
a traceback (an uncaught exception prints its type name only). The worker's logs go to a buffer at INFO for the run
and are checked against the log rules (non-negotiable 3), never printed. No child process (dbmate, afconvert) is given
the key. SIGTERM and SIGHUP end the run like Ctrl-C, and the throwaway database is still dropped.

It sets `SPEECH_MODE=sarvam` and `SPEECH_HOSTED_APPROVAL=DEC-108` for its own process, so a PASS does not test the
deployed approval or mode: the go/no-go voice rows and the UAT smoke line do.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib
import io
import logging
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import wave
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import FrameType, SimpleNamespace
from typing import Any, TextIO

ALL = ("tts", "stt_rest", "stt_stream", "translate")  # run order: tts makes the audio speech to text hears
NEEDS_AUDIO = frozenset({"stt_rest", "stt_stream"})
MISSING_KEY = "SARVAM_API_KEY is not set. Load it in your own terminal and run this again."
IN_CI = "This check calls Sarvam with a real key, so it never runs in CI. Run it in your own terminal."
BASE_URL_SET = "SARVAM_BASE_URL is set, so this would not reach Sarvam. Unset it and run this again."
NO_DATABASE = (
    "The local stack's Postgres is not reachable, or dbmate failed. Run `make up` and run this again."
)
NO_DECODER_NOTE = "afconvert is not on this machine, so speech to text had no audio: run this on the Mac"
DROP_FAILED = (
    "The throwaway database {name} could not be dropped. Drop it by hand once Postgres answers again."
)
APPROVAL = "DEC-108"  # the reference docs/UAT.md gives for SPEECH_HOSTED_APPROVAL (the voice row)
DB_PREFIX = "sarvam_live"
ACTOR = "sarvam-live"
SPEECH_HOSTED = "speech.hosted"
PCM_RATE = 16000
CHUNK_BYTES = PCM_RATE * 2  # one second of 16-bit mono, as the browser sends it (drafts.chunk_contract)
CONTRIBUTOR = "CTR-5a1e00"  # synthetic: the owner of the check's own draft
# The masking functions, where each path looks them up: (module, name). Each is wrapped for the identity checks and
# run once on a synthetic vector before any network call.
MASKERS = {
    "listen.mask_for_service": ("speech.listen", "mask_for_service"),  # tts, on the way out
    "voice.leave_out_blocked": ("voice.service", "leave_out_blocked"),  # stt_rest, on return
    "drafts.hide_text": ("speech.drafts", "hide_text"),  # stt_stream and translate, on return
    "drafts.mask_for_service": ("speech.drafts", "mask_for_service"),  # translate, on the way out
}
# What a `speech_calls` row may hold besides numbers: our own codes, and an ID or a uuid (optionally `kind:`).
CODE = re.compile(r"^[a-z0-9_.]{1,60}$")
REF = re.compile(
    r"^(?:[a-z_]{1,20}:)?(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[A-Z]{2,8}-[0-9]{4}-[0-9]{6})$"
)

# Synthetic, written for this check. Each sentence carries two words that are easy to check once speech to text has
# heard the audio tts made of it.
SPOKEN = "The printer near the lift is out of paper. Please order more chairs for the meeting room."
SPOKEN_TITLE = "Summary"
HEARD = (("printer", "paper"), ("chairs", "meeting"))  # at least one word of each sentence must come back
# Hinglish as the codemix transcript gives it (Indian words in their script, English words in English).
HINGLISH = "ऑफिस का printer कल से काम नहीं कर रहा, कृपया नया toner मंगवा दीजिए।"
HINGLISH_LANG = "hi-IN"
# Words that must never show in a printed line, a `speech_calls` column or a worker warning.
MARKERS = frozenset({"printer", "paper", "lift", "chairs", "meeting", "toner", "ऑफिस"})

Decoder = Callable[[bytes], bytes]  # MP3 in, 16 kHz mono s16le PCM out; raises DecodeFailed


class _Tripped(BaseException):
    """A network entry point was reached while the check expected a refusal. BaseException, so no worker `except
    Exception` can swallow it."""


class _NoDatabase(Exception):
    pass


class _DropFailed(Exception):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.name = name


class DecodeFailed(Exception):
    """`code` is ours: `no_decoder` or `decode_failed`. Never the tool's output."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


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
    """What the worker's path did, held in memory for the identity checks only: never printed, logged or kept."""

    sockets: list[Any] = field(default_factory=list)
    masked: dict[str, list[tuple[Any, Any]]] = field(
        default_factory=dict
    )  # masking function: [(input, output)]
    sent: dict[str, list[Any]] = field(
        default_factory=dict
    )  # `sarvam.tts` or `translate`: the text handed to it

    def calls(self, name: str) -> list[tuple[Any, Any]]:
        return self.masked.get(name, [])

    def outputs(self, name: str) -> list[Any]:
        return [out for _given, out in self.calls(name)]


@dataclass
class _Run:
    conn: Any
    decode: Decoder
    pace_s: float  # the gap between two one-second chunks on the stream (the browser's pace)
    mp3: bytes = b""  # what tts made
    pcm: bytes | None = None  # that audio at 16 kHz mono s16le, once decoded
    pcm_failure: str | None = None
    notes: list[str] = field(default_factory=list)
    tagged: dict[str, bool] = field(default_factory=dict)  # each masking function tagged the synthetic vector

    def masking_works(self, *names: str) -> bool:
        return all(self.tagged.get(n, False) for n in names)


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
    """Record what each masking function was given and gave back, what the paths hand to `sarvam.tts` and
    `sarvam.translate`, and the sockets the client opens (for their close codes). The real functions still run, with
    the same arguments, and their results are returned unchanged (the same objects)."""
    from gateway import sarvam

    real_open = sarvam._ws_open

    def ws_open(path: str, params: dict[str, str]) -> Any:
        ws = real_open(path, params)
        spy.sockets.append(ws)
        return ws

    def recording(name: str, real: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(text: Any, *args: Any, **kwargs: Any) -> Any:
            out = real(text, *args, **kwargs)
            spy.masked.setdefault(name, []).append((text, out))
            return out

        return wrapper

    def handing(call: str, real: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(text: Any, *args: Any, **kwargs: Any) -> Any:
            spy.sent.setdefault(call, []).append(text)
            return real(text, *args, **kwargs)

        return wrapper

    with contextlib.ExitStack() as stack:
        stack.enter_context(_patched(sarvam, "_ws_open", ws_open))
        for name, (module, attr) in MASKERS.items():
            mod = importlib.import_module(module)
            stack.enter_context(_patched(mod, attr, recording(name, getattr(mod, attr))))
        for call in ("tts", "translate"):
            stack.enter_context(_patched(sarvam, call, handing(call, getattr(sarvam, call))))
        yield


def maskers_tag() -> dict[str, bool]:
    """Each masking function the paths use, run once on a synthetic vector from `pii.vectors` (generated at run time,
    a value the patterns block), before any network call: it must come back tagged, the value gone. The vector stays
    in this process: never sent, printed or logged."""
    from pii import vectors
    from speech.adapters import DOTS

    vector = next(v for v in vectors.build(n=1)["vectors"] if v["expect"]["blocks"])
    text = str(vector["text"])
    values = [text[h["start"] : h["end"]] for h in vector["python"] if h["action"] == "block"]
    tagged: dict[str, bool] = {}
    for name, (module, attr) in MASKERS.items():
        try:
            out = getattr(importlib.import_module(module), attr)(text)
        except Exception:
            tagged[name] = False
            continue
        got = out.text if hasattr(out, "text") else out[0] if isinstance(out, tuple) else out
        tagged[name] = (
            isinstance(got, str)
            and bool(values)
            and (DOTS in got or "left out]" in got)
            and not any(v in got for v in values)
        )
    return tagged


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


_HOSTED_STATUS = re.compile(r"^hosted_(\d{3})$")


def _status(kind: str, sockets: Sequence[Any], code: str | None) -> str:
    """`http 200`, `ws 1000` (the close code), `ws ok`; on a refusal at the door, the HTTP status in our code."""
    m = _HOSTED_STATUS.match(code or "")
    if m:
        return f"{kind} {m.group(1)}"
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
    """The call's rows in `speech_calls`: the right call, model and outcome. No row the call wrote (a translation the
    stream asked for included) holds a synthetic word in any column."""
    rows = conn.execute(
        "SELECT call, model, ref_id, outcome, error_code, speech_seconds, char_count, latency_ms, cost_inr "
        "FROM speech_calls WHERE id > %s ORDER BY id",
        (since,),
    ).fetchall()
    for row in rows:
        values = " ".join(str(v) for v in row.values() if v is not None).lower()
        if any(w in values for w in MARKERS):
            return "meter_text"
        if row["error_code"] is not None and not CODE.match(str(row["error_code"])):
            return "meter_text"
        if row["ref_id"] is not None and not REF.match(str(row["ref_id"])):
            return "meter_text"
    mine = [row for row in rows if row["call"] == call]
    if len(mine) != rows_expected:
        return "meter_rows"
    for row in mine:
        if row["model"] != model:
            return "meter_model"
        if row["outcome"] not in ("ok", "ok_after_retry") or row["error_code"] is not None:
            return "meter_outcome"
    return None


def _refuses_offline(conn: Any, refused: Callable[[], str | None]) -> str | None:
    """With `speech.hosted` off, the same call must refuse with `hosted_switched_off` before either network entry
    point is reached. `refused` runs the call and returns the code it refused with (None if it did not refuse). The
    switch goes back on afterwards. Returns a reason code, or None when it refused properly."""
    from core import killswitch

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
                code = refused()
            except _Tripped:
                return "refusal_reached_network"
            if reached:
                return "refusal_reached_network"
            if code is None:
                return "refusal_missing"
            return None if code == "hosted_switched_off" else f"refusal_{code}"[:40]
    finally:
        killswitch.set_switch(
            conn,
            SPEECH_HOSTED,
            "on",
            reason="Live check: back on after the refusal check (BLD-C177)",
            actor=ACTOR,
        )


def _same_objects(sent: Sequence[Any], masked: Sequence[Any]) -> bool:
    """Every text handed on is the very object the masking function returned, one for one."""
    return bool(sent) and len(sent) == len(masked) and all(a is b for a, b in zip(sent, masked, strict=True))


def _words_back(text: str) -> bool:
    low = text.lower()
    return all(any(w in low for w in sentence) for sentence in HEARD)


def _elapsed(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


# ---- decoding the tts audio (macOS's own afconvert; no new dependency) ------------------------------------------


def afconvert_pcm(mp3: bytes) -> bytes:
    """MP3 to 16 kHz mono s16le PCM with macOS's built-in `afconvert`, in a private temporary folder removed at the
    end. Arguments as a list, no shell; the child gets no key; its output is never read, printed or logged."""
    tool = shutil.which("afconvert")
    if tool is None:
        raise DecodeFailed("no_decoder")
    folder = tempfile.TemporaryDirectory(prefix="sarvam-live-")
    try:
        src, dst = Path(folder.name) / "tts.mp3", Path(folder.name) / "heard.wav"
        src.write_bytes(mp3)
        done = subprocess.run(
            [tool, "-f", "WAVE", "-d", f"LEI16@{PCM_RATE}", "-c", "1", str(src), str(dst)],
            env=_child_env(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=60,
        )
        if done.returncode != 0 or not dst.exists():
            raise DecodeFailed("decode_failed")
        try:
            with wave.open(str(dst), "rb") as w:
                if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (1, 2, PCM_RATE):
                    raise DecodeFailed("decode_failed")
                return w.readframes(w.getnframes())
        except (wave.Error, EOFError):
            raise DecodeFailed("decode_failed") from None
    except subprocess.TimeoutExpired:
        raise DecodeFailed("decode_failed") from None
    finally:
        folder.cleanup()


def _wav(pcm: bytes) -> bytes:
    """The same 16 kHz mono s16le audio in a WAV container, as a voice-note file."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(PCM_RATE)
        w.writeframes(pcm)
    return buf.getvalue()


def _pcm(run: _Run) -> bytes | None:
    """The tts audio, decoded once for both speech-to-text calls. None with `run.pcm_failure` set."""
    if run.pcm is not None or run.pcm_failure:
        return run.pcm
    if not run.mp3:
        run.pcm_failure = "no_tts_audio"
        return None
    try:
        pcm = run.decode(run.mp3)
    except DecodeFailed as exc:
        run.pcm_failure = exc.code
    except Exception:
        run.pcm_failure = "decode_failed"
    else:
        if not pcm or len(pcm) % 2:
            run.pcm_failure = "decode_failed"
        else:
            run.pcm = pcm
    if run.pcm_failure == "no_decoder" and NO_DECODER_NOTE not in run.notes:
        run.notes.append(NO_DECODER_NOTE)
    return run.pcm


# ---- the calls -------------------------------------------------------------------------------------------------


def _tts(run: _Run) -> Line:
    """Listen's path: the script part masked for the service and leak-checked (`listen.outgoing`), spoken by
    `listen._synthesise` through `gateway.sarvam.tts`, the audio parsed as Listen parses it (leading tags stripped,
    MPEG frames counted). Listen's store is stood in for: the check keeps the audio in memory only. Masked: the text
    handed to `sarvam.tts` is the very object `mask_for_service` returned, and that function tags a vector."""
    from gateway import sarvam
    from gateway.speech import SpeechUnavailable
    from speech import listen
    from speech.adapters import Script, ScriptPart

    line = Line("tts", sarvam.TTS_MODEL)
    script = Script(parts=(ScriptPart("summary", SPOKEN_TITLE, SPOKEN),), version="sarvamlivecheck01")
    idea = str(uuid.uuid4())
    kept: dict[str, Any] = {}

    def keep(*args: Any) -> None:
        _conn, _idea, _version, _voice, _lang, audio, chapters, duration_s = args
        kept.update(audio=audio, chapters=chapters, duration_s=duration_s)

    def attempt() -> bytes:
        texts = listen.outgoing(script)
        return b"".join(
            listen._synthesise(run.conn, idea, script.version, texts, listen.LANG, listen._voice())
        )

    def refused() -> str | None:
        try:
            attempt()
        except SpeechUnavailable as exc:
            return exc.code
        return None

    since = _since(run.conn)
    spy = _Spy()
    audio = b""
    started = time.monotonic()
    with _patched(listen, "_store", keep):
        with _watching(spy):
            try:
                audio = attempt()
            except SpeechUnavailable as exc:
                line.reason = exc.code
        line.ms = _elapsed(started)
        line.status = _status("ws", spy.sockets, line.reason)
        if line.reason:
            return line
        if not audio or kept.get("audio") != audio:
            line.reason = "no_audio"
        elif listen.mp3_seconds(audio) <= 0 or float(kept.get("duration_s") or 0) <= 0:
            line.reason = "not_mp3"
        elif [c.get("part") for c in kept.get("chapters", [])] != ["summary"]:
            line.reason = "chapters"
        elif not _same_objects(spy.sent.get("tts", []), spy.outputs("listen.mask_for_service")):
            line.reason = "not_masked"
        elif not run.masking_works("listen.mask_for_service"):
            line.reason = "masking_no_op"
        else:
            line.reason = _metered(run.conn, since, "tts", sarvam.TTS_MODEL, rows_expected=1)
        run.mp3 = audio
        if line.reason is None:  # inside the stand-in store: never the real one, even if the refusal failed
            line.reason = _refuses_offline(run.conn, refused)
    return line


def _stt_rest(run: _Run) -> Line:
    """The voice-note path, the service itself: `voice.service.transcribe` on a voice-note row of the check's own
    draft (the virus scan, the container probe, `gateway.speech.transcribe` into `gateway.sarvam.stt_rest`, the masking
    on return, the encrypted transcript), the audio as a 16 kHz mono WAV file. Stood in for: the quarantine bucket
    (the recording is our own WAV, held in memory; read and delete) and the virus scan (clean). Masked: the transcript
    the service hands back (`voice.service.status`) is what `leave_out_blocked` returned for this note."""
    from attachments import clamav
    from gateway import sarvam, speech
    from voice import service as voice_notes

    line = Line("stt_rest", sarvam.STT_MODEL)
    pcm = _pcm(run)
    if pcm is None:
        line.status, line.reason = "http -", run.pcm_failure
        return line
    wav = _wav(pcm)
    held: dict[str, bytes] = {}
    bucket = SimpleNamespace(  # the quarantine bucket, stood in for
        get=lambda _bucket, key: held[key],
        delete=lambda _bucket, key: held.pop(key, None),
    )
    scanner = SimpleNamespace(  # the virus scan, stood in for: our own synthetic audio is clean
        scan_bytes=lambda _data, timeout=60.0: clamav.ScanResult(clean=True, signature=None),
        ScannerUnavailable=clamav.ScannerUnavailable,
    )
    idea = str(
        run.conn.execute(
            "INSERT INTO ideas (contributor_code, status) VALUES (%s, 'draft') RETURNING id", (CONTRIBUTOR,)
        ).fetchone()["id"]
    )

    def note() -> str:
        voice_id = str(uuid.uuid4())
        held[f"voice/{voice_id}"] = wav
        run.conn.execute(
            "INSERT INTO voice_notes (id, idea_uuid, uploaded_by_code, mime, bytes, store_key) "
            "VALUES (%s, %s, %s, 'audio/wav', %s, %s)",
            (voice_id, idea, CONTRIBUTOR, len(wav), f"voice/{voice_id}"),
        )
        return voice_id

    def transcribe(voice_id: str) -> tuple[str, str | None]:
        """The note's state and failure code, as the job runner would see them."""
        try:
            state = voice_notes.transcribe(run.conn, voice_id)
        except speech.SpeechUnavailable as exc:  # a code worth retrying: raised for the job runner
            return "quarantine", exc.code
        row = run.conn.execute("SELECT failure FROM voice_notes WHERE id = %s", (voice_id,)).fetchone()
        return state, (str(row["failure"]) if row and row["failure"] else None)

    def refused() -> str | None:
        state, code = transcribe(note())
        return None if state == "ready" else code or f"note_{state}"

    since = _since(run.conn)
    spy = _Spy()
    with _patched(voice_notes, "store", bucket), _patched(voice_notes, "clamav", scanner):
        voice_id = note()
        started = time.monotonic()
        with _watching(spy):
            state, code = transcribe(voice_id)
        line.ms = _elapsed(started)
        if state != "ready":
            line.reason = (code or f"note_{state}")[:40]
            line.status = _status("http", [], line.reason)
            return line
        line.status = "http 200"
        view = voice_notes.status(run.conn, voice_id, idea) or {}
        text = view.get("transcript")
        line.words = _words_back(text if isinstance(text, str) else "")
        masked = [out for out in spy.outputs("voice.leave_out_blocked") if isinstance(out, tuple)]
        if not isinstance(text, str) or not text.strip():
            line.reason = "nothing_heard"
        elif len(masked) != 1 or masked[0][0] != text:
            line.reason = "not_masked"
        elif not run.masking_works("voice.leave_out_blocked"):
            line.reason = "masking_no_op"
        elif not line.words:
            line.reason = "words_missing"
        else:
            line.reason = _metered(run.conn, since, "stt_rest", sarvam.STT_MODEL, rows_expected=1)
        if line.reason is None:  # inside the stand-ins: never the real bucket or scanner
            line.reason = _refuses_offline(run.conn, refused)
    return line


class _StandInStreams:
    """The drafts' stream store (`speech.drafts.Store`), in memory for the check: one synthetic draft, owned by the
    synthetic contributor. Nothing is kept after the run."""

    def __init__(self, idea_uuid: str) -> None:
        self.idea_uuid = idea_uuid
        self.rows: dict[str, dict[str, Any]] = {}

    def __call__(self, conn: Any) -> _StandInStreams:  # drafts asks its factory for a store per call
        return self

    def owned_draft(self, idea_uuid: str, by_code: str) -> str:
        return "draft" if (idea_uuid, by_code) == (self.idea_uuid, CONTRIBUTOR) else "not_found"

    def begin(self, stream_id: str, idea_uuid: str, by_code: str, per_hour: int) -> bool:
        self.rows[stream_id] = {
            "id": stream_id,
            "idea_uuid": idea_uuid,
            "by_code": by_code,
            "state": "live",
            "failure": None,
            "ended_by": None,
            "speech_seconds": 0,
            "chunk_count": 0,
            "lang": None,
            "own_words_sealed": None,
            "masked_encrypted": None,
            "text_en_encrypted": None,
            "translated": None,
            "spans": [],
            "hidden_count": 0,
            "handed_at": None,
        }
        return True

    def live_of(self, by_code: str) -> list[str]:
        return [k for k, r in self.rows.items() if r["by_code"] == by_code and r["state"] == "live"]

    def row(self, stream_id: str) -> dict[str, Any] | None:
        return dict(self.rows[stream_id]) if stream_id in self.rows else None

    def done(self, stream_id: str, v: dict[str, Any]) -> None:
        r = self.rows[stream_id]
        if r["state"] == "live":
            r.update(
                state="done",
                ended_by=v["ended_by"],
                speech_seconds=v["seconds"],
                chunk_count=v["chunks"],
                lang=v["lang"],
                own_words_sealed=v["own_words_sealed"],
                masked_encrypted=v["masked_encrypted"],
                text_en_encrypted=v["text_en_encrypted"],
                translated=v["translated"],
                spans=v["spans"],
                hidden_count=v["hidden_count"],
                failure=v.get("failure"),
            )

    def failed(self, stream_id: str, code: str, ended_by: str | None, seconds: float, chunks: int) -> None:
        r = self.rows[stream_id]
        if r["state"] == "live":
            r.update(
                state="failed", failure=code, ended_by=ended_by, speech_seconds=seconds, chunk_count=chunks
            )

    def handed(self, stream_id: str) -> None:
        self.rows.pop(stream_id, None)

    def sweep(self) -> tuple[int, int]:
        return 0, 0

    def masked_copy(self, stream_id: str) -> str | None:
        """The masked copy of the words heard (DEC-103), as `voice_to_message` reads it: what everyone but the
        speaker sees. Kept in memory for the check only."""
        from core.crypto import decrypt_json
        from speech import drafts

        sealed = self.rows.get(stream_id, {}).get("masked_encrypted")
        if sealed is None:
            return None
        text = decrypt_json(bytes(sealed), drafts._ctx("masked", stream_id)).get("text")
        return text if isinstance(text, str) else None

    def last_failure(self) -> str | None:
        failures = [r["failure"] for r in self.rows.values() if r["failure"]]
        return str(failures[-1]) if failures else None


def _stt_stream(run: _Run) -> Line:
    """The drafts "By voice" path: `speech.drafts.start` opens `gateway.sarvam.stt_stream`; `chunk` relays one second
    of PCM at a time, a second apart, the way the browser's audio arrives; `end` flushes, waits for the last words,
    closes, and masks what was heard (`hide_text`). The drafts' stream store is stood in for in memory. Masked: the
    masked copy kept for everyone but the speaker is what `hide_text` returned for the words heard."""
    from gateway import sarvam
    from speech import drafts

    line = Line("stt_stream", sarvam.STT_MODEL)
    pcm = _pcm(run)
    if pcm is None:
        line.status, line.reason = "ws -", run.pcm_failure
        return line
    audio: bytes = pcm
    idea = str(uuid.uuid4())
    store = _StandInStreams(idea)

    def stream() -> dict[str, Any]:
        begun = drafts.start(run.conn, idea_uuid=idea, by_code=CONTRIBUTOR)
        sid = str(begun["id"])
        opened = time.monotonic()
        for seq, at in enumerate(range(0, len(audio), CHUNK_BYTES)):
            wait = opened + seq * run.pace_s - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            drafts.chunk(
                run.conn, sid, idea_uuid=idea, by_code=CONTRIBUTOR, seq=seq, data=audio[at : at + CHUNK_BYTES]
            )
        return drafts.end(run.conn, sid, idea_uuid=idea, by_code=CONTRIBUTOR, ended_by="person")

    def refused() -> str | None:
        try:
            stream()
        except drafts.VoiceRefused:
            return store.last_failure()
        return None

    since = _since(run.conn)
    spy = _Spy()
    view: dict[str, Any] = {}
    started = time.monotonic()
    with _patched(drafts, "_store", store):
        with _watching(spy):
            try:
                view = stream()
            except drafts.VoiceRefused as exc:
                line.reason = store.last_failure() or exc.code
        line.ms = _elapsed(started)
        line.status = _status("ws", spy.sockets, line.reason)
        if line.reason:
            return line
        if view.get("state") != "done":
            line.reason = str(view.get("failure") or "stream_not_done")[:40]
            return line
        masked = store.masked_copy(str(view.get("id")))
        line.words = _words_back(masked or "")
        own = view.get("text")  # the speaker's own words, as the stream hands them back to them alone
        hidden = [out for given, out in spy.calls("drafts.hide_text") if given == own]
        english = view.get("text_en")
        translated = bool(spy.sent.get("translate"))
        if not masked or not isinstance(own, str):
            line.reason = "no_masked_copy"
        elif not hidden or any(getattr(out, "text", None) != masked for out in hidden):
            line.reason = (
                "not_masked"  # the masked copy kept for everyone else is hide_text's output for these words
            )
        elif (
            english is not None
            and english != masked
            and english not in [getattr(out, "text", None) for out in spy.outputs("drafts.hide_text")]
        ):
            line.reason = (
                "not_masked"  # the English copy is the masked words, or hide_text's output on the translation
            )
        elif not run.masking_works("drafts.hide_text", *(["drafts.mask_for_service"] if translated else [])):
            line.reason = "masking_no_op"
        elif not line.words:
            line.reason = "words_missing"
        else:
            line.reason = _metered(run.conn, since, "stt_stream", sarvam.STT_MODEL, rows_expected=1)
        if line.reason is None:
            line.reason = _refuses_offline(run.conn, refused)
    return line


def _translate(run: _Run) -> Line:
    """The English copy: `speech.drafts._english` masks the words for the service, sends them through
    `gateway.sarvam.translate` (mayura:v1, code-mixed, into English) and masks what comes back (`hide_text`). Masked:
    the text sent is the very object `mask_for_service` returned, and the text returned is the very object `hide_text`
    returned; both functions tag a vector."""
    from gateway import sarvam
    from speech import drafts
    from speech.adapters import hide_text

    line = Line("translate", sarvam.TRANSLATE_MODEL)
    masked = hide_text(HINGLISH).text  # as the stream hands it over: the masked copy of the words heard

    def english() -> tuple[str | None, bool | None, str | None]:
        return drafts._english(run.conn, str(uuid.uuid4()), masked, HINGLISH_LANG, None)

    def refused() -> str | None:
        _text, _translated, failure = english()
        return failure.removeprefix("translation_") if failure else None

    since = _since(run.conn)
    spy = _Spy()
    started = time.monotonic()
    with _watching(spy):
        text_en, translated, failure = english()
    back = spy.outputs("drafts.hide_text")
    line.ms = _elapsed(started)
    line.reason = failure.removeprefix("translation_") if failure else None
    line.status = _status("http", [], line.reason)
    if line.reason:
        return line
    if not isinstance(text_en, str) or not text_en.strip() or translated is not True:
        line.reason = "hosted_bad_reply"
    elif not _same_objects(spy.sent.get("translate", []), spy.outputs("drafts.mask_for_service")):
        line.reason = "not_masked"  # what went to mayura is the very object mask_for_service returned
    elif len(back) != 1 or text_en is not getattr(back[0], "text", None):
        line.reason = "not_masked"  # what came back to the caller is the very object hide_text returned
    elif not run.masking_works("drafts.mask_for_service", "drafts.hide_text"):
        line.reason = "masking_no_op"
    else:
        line.reason = _metered(
            run.conn, since, "translate", sarvam.TRANSLATE_MODEL, rows_expected=1
        ) or _refuses_offline(run.conn, refused)
    return line


CHECKS: dict[str, Callable[[_Run], Line]] = {
    "tts": _tts,
    "stt_rest": _stt_rest,
    "stt_stream": _stt_stream,
    "translate": _translate,
}


def _model(call: str) -> str:
    from gateway import sarvam

    return {"tts": sarvam.TTS_MODEL, "translate": sarvam.TRANSLATE_MODEL}.get(call, sarvam.STT_MODEL)


# ---- the run ---------------------------------------------------------------------------------------------------


@contextlib.contextmanager
def _quiet_logs() -> Iterator[io.StringIO]:
    """The worker's logs at INFO into a buffer for the run, never printed, and scanned at the end. An exception nothing
    catches (in this process or a thread) prints its type name only, never its message or a traceback. The previous
    setup comes back after."""
    from core import logging as klog

    root = logging.getLogger()
    level, handlers = root.level, [h for h in root.handlers if getattr(h, "_kfin", False)]
    hooks = (sys.excepthook, threading.excepthook)
    buffer = io.StringIO()
    klog.configure("INFO", stream=buffer)

    def type_only(exc_type: type[BaseException], _exc: BaseException, _tb: Any) -> None:
        print(f"sarvam-live stopped: {exc_type.__name__}.", file=sys.stderr)

    def thread_type_only(args: threading.ExceptHookArgs) -> None:
        name = args.exc_type.__name__ if args.exc_type is not None else "an exception"
        print(f"sarvam-live: a background thread stopped: {name}.", file=sys.stderr)

    sys.excepthook, threading.excepthook = type_only, thread_type_only
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
    """The environment for a child process (dbmate, afconvert): the key never goes to one."""
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
    created = False
    try:  # opened before CREATE, so even an interrupted create is dropped
        try:
            with psycopg.connect(_admin_url(), autocommit=True) as admin:
                admin.execute(f'CREATE DATABASE "{name}"')
            created = True
        except Exception:
            raise _NoDatabase from None
        compose = ["docker", "compose", "-f", "infra/docker-compose.yml", "--project-directory", "."]
        url = f"DATABASE_URL={_db_url(name, 'postgres')}"
        migrate = subprocess.run(
            [*compose, "--env-file", ".env", "run", "--rm", "-T", "-e", url, "dbmate", "up"],
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
        try:  # our own name only, and only if it exists
            with psycopg.connect(_admin_url(), autocommit=True) as admin:
                admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        except Exception:
            if (
                created
            ):  # Postgres went away mid-run: say so, plainly; unreachable from the start, nothing to drop
                raise _DropFailed(name) from None


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


def run(
    calls: Sequence[str],
    *,
    out: TextIO,
    database: str | None = None,
    decode: Decoder = afconvert_pcm,
    pace_s: float = 1.0,
) -> int:
    """Run the checks in order and print one line each, then the summary. `database` is a database that already
    exists (the tests' fixture); without it the check makes and drops its own. `decode` turns the tts MP3 into
    16 kHz mono s16le (tests pass PCM straight in); `pace_s` is the gap between stream chunks. SIGTERM and SIGHUP end
    the run as Ctrl-C does, so the throwaway database is still dropped."""
    with _interruptible(), _quiet_logs() as logs:
        if database is not None:
            return _run_in(database, calls, out, logs, decode, pace_s)
        try:
            with throwaway_database() as name:
                return _run_in(name, calls, out, logs, decode, pace_s)
        except _NoDatabase:
            print(NO_DATABASE, file=out)
            return 1
        except _DropFailed as exc:
            print(DROP_FAILED.format(name=exc.name), file=out)
            return 1


@contextlib.contextmanager
def _interruptible() -> Iterator[None]:
    """SIGTERM and SIGHUP raise KeyboardInterrupt for the run (the main thread only); the old handlers come back."""
    if threading.current_thread() is not threading.main_thread():
        yield
        return

    def stop(_signum: int, _frame: FrameType | None) -> None:
        raise KeyboardInterrupt

    old = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGHUP)}
    for sig in old:
        signal.signal(sig, stop)
    try:
        yield
    finally:
        for sig, handler in old.items():
            signal.signal(sig, handler)


def _run_in(
    name: str, calls: Sequence[str], out: TextIO, logs: io.StringIO, decode: Decoder, pace_s: float
) -> int:
    from core import killswitch
    from core.db import connect
    from pii.log_rules import scan_log_lines

    lines: list[Line] = []
    notes: list[str] = []
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
            # Before any network call: each masking function must tag a synthetic vector (never sent or printed).
            state = _Run(conn=conn, decode=decode, pace_s=pace_s, notes=notes, tagged=maskers_tag())
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
    logged = [line for line in logs.getvalue().splitlines() if line.strip()]  # INFO and above, never printed
    logs_ok = not scan_log_lines(logged) and not any(_holds_text(w) for w in logged)
    passed = sum(1 for line in lines if line.passed)
    ok = passed == len(lines) and logs_ok
    note = f"  ({'; '.join(notes)})" if notes else ""
    print(
        f"summary     {passed} of {len(lines)} passed  log lines: {len(logged)}, "
        f"IDs only: {'yes' if logs_ok else 'no'}  {'PASS' if ok else 'FAIL'}{note}",
        file=out,
        flush=True,
    )
    return 0 if ok else 1


def _holds_text(line: str) -> bool:
    """A worker log line holding any synthetic word or the key."""
    low = line.lower()
    key = os.environ.get("SARVAM_API_KEY", "").strip()
    return any(w in low for w in MARKERS) or bool(key and key in line)


# ---- the command -----------------------------------------------------------------------------------------------


def _parse(only: str) -> list[str] | None:
    """The calls asked for, in run order; speech to text brings tts with it (its audio is what is heard)."""
    asked = {c.strip() for c in only.replace(" ", ",").split(",") if c.strip()}
    if any(c not in ALL for c in asked):
        return None
    if asked & NEEDS_AUDIO:
        asked.add("tts")
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
    try:  # from here on, any failure (a settings error included) prints its type name only, never a traceback
        from core.config import get_settings

        get_settings.cache_clear()
        if os.environ.get("SARVAM_BASE_URL", "").strip() or get_settings().sarvam_base_url.strip():
            print(BASE_URL_SET, file=stream)
            return 2
        calls = _parse(args.only)
        if calls is None:
            print(f"ONLY takes {', '.join(ALL)}, or a comma-separated list of them.", file=stream)
            return 2
        return run(calls, out=stream)
    except BaseException as exc:  # the type only, never a message or a traceback: either could quote a reply
        if isinstance(exc, KeyboardInterrupt):
            print("sarvam-live stopped.", file=stream)
            return 130
        print(f"sarvam-live stopped: {type(exc).__name__}. Nothing more is printed.", file=stream)
        return 1


if __name__ == "__main__":
    sys.exit(main())
