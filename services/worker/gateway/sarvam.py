"""Sarvam's speech APIs, through the gateway (DEC-108, BLD-C110). Every call to Sarvam is in this file and nowhere
else (non-negotiable 1): plain httpx and websockets, no vendor SDK.

| Call | Model | How | Used by |
|---|---|---|---|
| `stt_rest` | saaras:v4 | REST, multipart, clips under 30 s | voice notes in quick capture (`gateway.speech`) |
| `stt_stream` | saaras:v4 | WebSocket; 16 kHz mono PCM s16le relayed as it arrives | drafts "By voice" (`speech.drafts`) |
| `translate` | mayura:v1 | REST JSON, code-mixed, into English, at most 1000 characters a request | the English copy |
| `tts` | bulbul:v4-flash | WebSocket, one text message per sentence, under 500 characters | Listen (`speech.listen`) |

The person's own words come from `SARVAM_STT_MODE` (`codemix` by default: English words stay English, Indian
words stay in their script; or `transcribe`), language detected.

DEC-108 bends non-negotiable 2 for audio only: raw voice goes to Sarvam untagged. Text going out (translate, tts)
must already be masked (DEC-103): `check_masked` re-runs the level-1 patterns on it and refuses with
`unmasked_text` on any hit, like the gateway's leak check. Transcripts are masked by the caller as they return.
Text for mayura is also tagged like a model call (BLD-C200, non-negotiable 2): `tag_for_service` is `run_agent`'s
steps 1 and 2 (the gateway's own tagger, then its leak check on the tagged text), and `tags_back` is step 7 for the
reply: every tag sent must come back intact, or the reply is refused as `hosted_tags_broken`.

Every call needs `SPEECH_HOSTED_APPROVAL` (DEC-108), the `speech.hosted` switch read fresh, past the cache, and
`SARVAM_API_KEY` from the worker-only env. Every call is metered in `speech_calls` (IDs, seconds, characters,
outcome and a code: never text), and a sustained error rate switches `speech.hosted` off, audited, the way an agent's
switch goes off (`gateway/core.py`). Nothing here logs or raises text, audio, transcripts or the key: errors carry a
code only. websockets' own logger is silenced, because at debug level it would print frames.

`SPEECH_MODE=fake` gives deterministic fakes for dev and tests (refused outside them, BLD-C007); tests that exercise
the real client point `SARVAM_BASE_URL` at an httpx MockTransport or a local fake WebSocket server.
"""

from __future__ import annotations

import base64
import contextlib
import json
import logging
import re
import threading
import time
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlencode

import httpx
from websockets.exceptions import InvalidStatus, WebSocketException
from websockets.sync.client import ClientConnection
from websockets.sync.client import connect as ws_connect

from core.config import get_settings
from core.db import Conn
from core.logging import get_logger
from gateway.core import _alert, leak_hits
from gateway.speech import FAKE_MARKER, FAKE_SAMPLE, SpeechUnavailable, Transcript, hosted_allowed
from pii.detect import Directory
from pii.patterns import scan
from pii.tagger import TAG_RE, tag_payload, tags_in

log = get_logger("sarvam")
_ws_log = logging.getLogger("kfin.sarvam.websockets")
_ws_log.disabled = True  # websockets logs frames at debug level; frames carry audio and text

BASE = "https://api.sarvam.ai"
STT_MODEL = "saaras:v4"
TRANSLATE_MODEL = "mayura:v1"
TTS_MODEL = "bulbul:v4-flash"
STT_MODES = frozenset({"codemix", "transcribe"})
REST_MAX_SECONDS = 30  # the REST endpoint is for short clips; longer notes stream
PCM_RATE = 16000
PCM_BYTES_PER_SECOND = PCM_RATE * 2  # 16-bit mono
TRANSLATE_MAX_CHARS = 1000  # mayura:v1's limit per request
TTS_MAX_CHARS = 499  # under 500 per message (DEC-108)
TTS_CODEC = "mp3"
TTS_BITRATE = "64k"
TTS_SAMPLE_RATE = 24000
RETRY_STATUS = frozenset({429, 500, 502, 503, 504})
BACKOFF_S = (0.5, 1.5)  # two retries
OPEN_TIMEOUT_S = 10.0
TTS_RECV_TIMEOUT_S = 20.0
STT_FINISH_WAIT_S = 10.0  # the most we wait for the last words after a flush
STT_FIRST_WORDS_S = 4.0  # if nothing at all arrives this long after a flush, nothing was pending
STT_QUIET_S = 0.6  # after the flush's words arrive, this much quiet ends the wait
ERROR_RATE_DEFAULT = 0.2
# Refused because of what we sent (bad or too short audio, a malformed field): recorded as `bad_input`, never counted
# toward the error rate that switches hosted speech off. Everything else that fails is the service's (BLD-C117).
BAD_INPUT_CODES = frozenset({"hosted_400", "hosted_413", "hosted_422"})
TTS_DEADLINE_S = 60.0  # one part's whole synthesis; a brownout must not hold the job runner for minutes
# Planning figures in rupees, to be replaced by the order form's (DEC-096 put hosted speech at about ₹1.5 a minute).
INR_PER_STT_MINUTE = 1.5
INR_PER_10K_TRANSLATE_CHARS = 20.0
INR_PER_10K_TTS_CHARS = 30.0

_sleep: Callable[[float], None] = time.sleep  # tests replace it so retries do not wait
_transport: httpx.BaseTransport | None = None  # tests put an httpx.MockTransport here


class SarvamFailed(SpeechUnavailable):
    """A Sarvam call failed. `code` is safe to log and store."""


@dataclass(frozen=True)
class Translation:
    text: str
    source_language: str | None
    translated: bool  # False when the text was already English and went nowhere


# ---- the gate, the key, the address ------------------------------------------------------------------------


def _key() -> str:
    key = get_settings().sarvam_api_key.strip()
    if not key:
        raise SarvamFailed("hosted_key_missing")
    return key


def key_present() -> bool:
    """For the watch, the go/no-go report and the smoke check: present or absent, never the value."""
    return bool(get_settings().sarvam_api_key.strip())


def allowed(conn: Conn | None) -> None:
    """Raise unless a call may go out now: the approval reference, `speech.hosted` read fresh, and the key."""
    hosted_allowed(conn)
    _key()


def _base() -> str:
    s = get_settings()
    if s.sarvam_base_url.strip() and not s.is_production_like:  # a local fake, dev and test only
        return s.sarvam_base_url.strip().rstrip("/")
    return BASE


def _ws_base() -> str:
    base = _base()
    if base.startswith("https://"):
        return "wss://" + base[len("https://") :]
    return "ws://" + base.split("://", 1)[-1]


def _fake() -> bool:
    s = get_settings()
    if s.speech_mode != "fake":
        return False
    if s.is_production_like:  # a sample sentence must never stand in for someone's words (BLD-C007)
        raise SarvamFailed("fake_not_allowed")
    return True


def check_masked(text: str) -> None:
    """Text for mayura or bulbul gets the gateway's own leak check (`gateway.core.leak_hits`): any pattern hit, with
    no domain allowed, aborts the call before anything is sent (BLD-C117). Non-negotiable 2's DEC-108 exception
    covers audio only; text going out is masked first (`speech.adapters.mask_for_service`)."""
    if scan(text, kfin_domains=[]):
        raise SarvamFailed("unmasked_text")


# ---- text going out, tagged like a model call (BLD-C200) ---------------------------------------------------


@dataclass(frozen=True)
class Outgoing:
    """Text for Sarvam after `run_agent`'s steps 1 and 2: `text` is the only copy that may go to the service, and
    `tags` maps every tag in it to its type (never a value)."""

    text: str
    tags: dict[str, str]


# What is left of a tag the reply broke: a bracket pair, or a tag's name and number without them.
_TAG_PIECE = re.compile(r"\[\[|\]\]|\b[A-Z][A-Z_]*_[0-9]+\b")


def tag_for_service(text: str, *, conn: Conn, scope_id: str, d: Directory | None = None) -> Outgoing:
    """The masked text tagged in the idea's vault scope by the gateway's own tagger (`pii.tagger.tag_payload`:
    colleagues from `users`, other names, client organisations, codes and any pattern value), then the gateway's leak
    check (`gateway.core.leak_hits`) on the tagged text, in `run_agent`'s order. A hit means detection missed
    something: an `alert.leak_check` row (pattern ids only) and `unmasked_text`, before anything is sent."""
    tagged = tag_payload(conn, scope_id, text, d=d)
    hits = leak_hits(tagged.payload)
    if hits:
        _alert(conn, "alert.leak_check", "speech:sarvam", {"patterns": hits, "ref_id": scope_id})
        raise SarvamFailed("unmasked_text")
    return Outgoing(text=str(tagged.payload), tags=dict(tagged.tags))


def tags_back(sent: Outgoing, text: str) -> str:
    """`run_agent`'s step 7 for the service's reply, stricter: every tag sent is back intact, and no other tag or
    piece of one is there. A translation can translate, split or drop a tag; that is a failed reply
    (`hosted_tags_broken`), never a leak, because no value behind a tag was ever sent. Returns `text` as it is."""
    if tags_in(text) != set(sent.tags) or _TAG_PIECE.search(TAG_RE.sub(" ", text)):
        raise SarvamFailed("hosted_tags_broken")
    return text


# ---- metering and the automatic switch-off -----------------------------------------------------------------


def _cost(call: str, seconds: float | None, chars: int | None) -> float:
    if call in ("stt_rest", "stt_stream"):
        return round((seconds or 0.0) / 60.0 * INR_PER_STT_MINUTE, 4)
    if call == "translate":
        return round((chars or 0) / 10_000 * INR_PER_10K_TRANSLATE_CHARS, 4)
    return round((chars or 0) / 10_000 * INR_PER_10K_TTS_CHARS, 4)


def failed_outcome(code: str) -> str:
    """`bad_input` for a refusal of what we sent, else `route_error` (counted toward the switch-off)."""
    return "bad_input" if code in BAD_INPUT_CODES else "route_error"


def meter(
    conn: Conn | None,
    call: str,
    model: str,
    *,
    ref_id: str | None,
    outcome: str,
    error_code: str | None = None,
    seconds: float | None = None,
    chars: int | None = None,
    started: float | None = None,
) -> None:
    """One row in `speech_calls`: IDs, seconds, characters, outcome and a code. A failure to meter never fails the
    call; a route error may switch `speech.hosted` off."""
    if conn is None:
        return
    latency = max(0, int((time.monotonic() - started) * 1000)) if started is not None else None
    try:
        conn.execute(
            "INSERT INTO speech_calls (call, model, ref_id, outcome, error_code, speech_seconds, char_count, "
            "latency_ms, cost_inr) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                call,
                model,
                ref_id,
                outcome,
                error_code,
                round(seconds, 2) if seconds is not None else None,
                chars,
                latency,
                _cost(call, seconds, chars),
            ),
        )
    except Exception as exc:  # metering is bookkeeping: the person's words must not be lost for it
        log.warning("sarvam.meter_failed", call=call, error_type=type(exc).__name__)
        return
    if outcome == "route_error":
        try:
            _after_error(conn)
        except Exception as exc:
            log.warning("sarvam.error_rate_check_failed", error_type=type(exc).__name__)


def _after_error(conn: Conn) -> None:
    """More than the agents' error rate (rules `kill_switch_triggers.speech_error_rate_15min`, default 20%) over 15
    minutes, with at least 10 calls: `speech.hosted` goes off, audited, and stays off until InfoSec checks it."""
    from gateway.core import ERROR_MIN_CALLS, ERROR_WINDOW, _maybe_switch_off, _thresholds

    rate = float(_thresholds().get("speech_error_rate_15min", ERROR_RATE_DEFAULT))
    row = conn.execute(
        "SELECT count(*) AS total, count(*) FILTER (WHERE outcome = 'route_error') AS failed FROM speech_calls "
        "WHERE outcome IN ('ok', 'ok_after_retry', 'route_error') AND created_at > now() - %s::interval",
        (ERROR_WINDOW,),
    ).fetchone()
    if row and int(row["total"]) >= ERROR_MIN_CALLS and int(row["failed"]) / int(row["total"]) > rate:
        _maybe_switch_off(
            conn,
            "speech.hosted",
            f"Automatic: Sarvam error rate above {int(rate * 100)}% over 15 minutes (DEC-108)",
        )


# ---- REST -------------------------------------------------------------------------------------------------


def _post(path: str, *, timeout: httpx.Timeout, **kwargs: Any) -> tuple[dict[str, Any], bool]:
    """POST with two retries on 429, 5xx, timeouts and connection errors. Returns (body, retried)."""
    code = "hosted_unreachable"
    attempts = 1 + len(BACKOFF_S)
    for attempt in range(attempts):
        try:
            with httpx.Client(transport=_transport, timeout=timeout) as client:
                r = client.post(f"{_base()}{path}", headers={"api-subscription-key": _key()}, **kwargs)
        except httpx.TimeoutException:
            code = "hosted_timeout"
        except httpx.HTTPError:
            code = "hosted_unreachable"
        else:
            if r.status_code == 200:
                try:
                    body = r.json()
                except ValueError:
                    raise SarvamFailed("hosted_bad_reply") from None
                if not isinstance(body, dict):
                    raise SarvamFailed("hosted_bad_reply")
                return body, attempt > 0
            code = f"hosted_{r.status_code}"
            if r.status_code not in RETRY_STATUS:
                break
        if attempt < attempts - 1:
            _sleep(BACKOFF_S[attempt])
    raise SarvamFailed(code)


def stt_rest(
    data: bytes, mime: str, *, conn: Conn | None = None, ref_id: str | None = None, language: str = "unknown"
) -> Transcript:
    """A short clip (under 30 s) to text: the person's own words, language detected."""
    if _fake():
        at = data.find(FAKE_MARKER)
        text = (
            data[at + len(FAKE_MARKER) :].split(b"\0", 1)[0].decode("utf-8", "replace").strip()
            if at >= 0
            else FAKE_SAMPLE
        )
        return Transcript(text=text, language=None if at >= 0 else "en-IN", seconds=None)
    allowed(conn)
    started = time.monotonic()
    try:
        body, retried = _post(
            "/speech-to-text",
            files={"file": ("voice-note", data, mime)},
            data={
                "model": STT_MODEL,
                "mode": _stt_mode(),
                "language_code": language,
                "with_timestamps": "true",  # for the seconds metered; chunk level only
            },
            timeout=httpx.Timeout(20.0, connect=5.0),  # a clip under 30 s; a brownout fails fast (BLD-C117)
        )
        said = body.get("transcript")
        if not isinstance(said, str):
            raise SarvamFailed("hosted_bad_reply")
    except SarvamFailed as exc:
        meter(
            conn,
            "stt_rest",
            STT_MODEL,
            ref_id=ref_id,
            outcome=failed_outcome(exc.code),
            error_code=exc.code,
            started=started,
        )
        raise
    seconds = _rest_seconds(body.get("timestamps"))
    meter(
        conn,
        "stt_rest",
        STT_MODEL,
        ref_id=ref_id,
        outcome="ok_after_retry" if retried else "ok",
        seconds=seconds,
        started=started,
    )
    lang = body.get("language_code")
    return Transcript(text=said.strip(), language=lang if isinstance(lang, str) else None, seconds=seconds)


def _rest_seconds(stamps: Any) -> float | None:
    if not isinstance(stamps, dict):
        return None
    ends = stamps.get("end_time_seconds")
    if isinstance(ends, list) and ends and all(isinstance(x, int | float) for x in ends):
        return float(max(ends))
    return None


def _stt_mode() -> str:
    mode = get_settings().sarvam_stt_mode
    return mode if mode in STT_MODES else "codemix"


# ---- splitting text into requests and messages ----------------------------------------------------------

_SENTENCE = re.compile(r"[^.!?।॥\n]+(?:[.!?।॥]+|$)\s*|\n+")


def sentences(text: str) -> list[str]:
    """The text in sentences, each keeping its full stop; blank pieces dropped."""
    return [s.strip() for s in _SENTENCE.findall(text) if s.strip()]


def pieces(text: str, limit: int) -> list[str]:
    """Whole sentences packed into pieces of at most `limit` characters; a longer sentence is cut at spaces, and
    a word longer than the limit is cut where it must be."""
    out: list[str] = []
    current = ""
    for sentence in sentences(text):
        for part in _cut(sentence, limit):
            joined = f"{current} {part}" if current else part
            if len(joined) <= limit:
                current = joined
            else:
                out.append(current)
                current = part
    if current:
        out.append(current)
    return out


def _cut(sentence: str, limit: int) -> list[str]:
    if len(sentence) <= limit:
        return [sentence]
    out: list[str] = []
    current = ""
    for word in sentence.split():
        while len(word) > limit:
            if current:
                out.append(current)
                current = ""
            out.append(word[:limit])
            word = word[limit:]
        joined = f"{current} {word}" if current else word
        if len(joined) <= limit:
            current = joined
        else:
            out.append(current)
            current = word
    if current:
        out.append(current)
    return out


# ---- translation ------------------------------------------------------------------------------------------

GENDERS = frozenset({"Male", "Female"})


def translate(
    masked: str,
    *,
    gender: str | None = None,
    conn: Conn | None = None,
    ref_id: str | None = None,
    source: str = "auto",
) -> Translation:
    """Masked text into English with mayura:v1, code-mixed. `gender` ("Male" or "Female") is sent only when the
    person chose how to be referred to; otherwise it is left out and the wording stays neutral (DEC-108 (3))."""
    if source == "en-IN":
        return Translation(text=masked, source_language="en-IN", translated=False)
    check_masked(masked)
    if _fake():
        return Translation(text=masked, source_language=None if source == "auto" else source, translated=True)
    allowed(conn)
    out: list[str] = []
    detected: str | None = None
    for piece in pieces(masked, TRANSLATE_MAX_CHARS):
        started = time.monotonic()
        body: dict[str, Any] = {
            "input": piece,
            "source_language_code": source,
            "target_language_code": "en-IN",
            "model": TRANSLATE_MODEL,
            "mode": "code-mixed",
            "numerals_format": "international",  # digits stay digits, so the patterns can still find them
        }
        if gender in GENDERS:
            body["speaker_gender"] = gender
        try:
            reply, retried = _post("/translate", json=body, timeout=httpx.Timeout(20.0, connect=5.0))
            text = reply.get("translated_text")
            if not isinstance(text, str):
                raise SarvamFailed("hosted_bad_reply")
        except SarvamFailed as exc:
            meter(
                conn,
                "translate",
                TRANSLATE_MODEL,
                ref_id=ref_id,
                outcome=failed_outcome(exc.code),
                error_code=exc.code,
                chars=len(piece),
                started=started,
            )
            raise
        meter(
            conn,
            "translate",
            TRANSLATE_MODEL,
            ref_id=ref_id,
            outcome="ok_after_retry" if retried else "ok",
            chars=len(piece),
            started=started,
        )
        out.append(text.strip())
        lang = reply.get("source_language_code")
        detected = detected or (lang if isinstance(lang, str) else None)
    return Translation(text=" ".join(t for t in out if t), source_language=detected, translated=True)


# ---- WebSockets -------------------------------------------------------------------------------------------


def _ws_open(path: str, params: dict[str, str]) -> ClientConnection:
    """Open a WebSocket to Sarvam, with two retries on connection errors, 429 and 5xx. The key goes in a header."""
    url = f"{_ws_base()}{path}?{urlencode(params)}"
    code = "hosted_unreachable"
    attempts = 1 + len(BACKOFF_S)
    for attempt in range(attempts):
        try:
            return ws_connect(
                url,
                additional_headers={"Api-Subscription-Key": _key()},
                open_timeout=OPEN_TIMEOUT_S,
                close_timeout=2.0,
                max_size=4 * 1024 * 1024,
                logger=_ws_log,
                legacy=True,  # the connection outlives this call: the session holds it across requests
            )
        except InvalidStatus as exc:
            status = exc.response.status_code
            code = f"hosted_{status}"
            if status not in RETRY_STATUS:
                break
        except TimeoutError:
            code = "hosted_timeout"
        except (OSError, WebSocketException):
            code = "hosted_unreachable"
        if attempt < attempts - 1:
            _sleep(BACKOFF_S[attempt])
    raise SarvamFailed(code)


@dataclass(frozen=True)
class Heard:
    """What a stream has heard so far: the person's own words, unmasked. The caller masks before anything else
    sees it (DEC-103)."""

    text: str
    language: str | None
    seconds: float


class SttStream(Protocol):
    def send(self, pcm: bytes) -> None: ...

    def heard(self) -> Heard: ...

    def finish(self) -> Heard: ...

    def close(self) -> None: ...

    @property
    def seconds(self) -> float: ...

    @property
    def failure(self) -> str | None: ...


def stt_stream(
    *, conn: Conn | None = None, ref_id: str | None = None, language: str = "unknown"
) -> SttStream:
    """Open one streaming speech-to-text session through the configured route."""
    if _fake():
        return FakeStream()
    s = get_settings()
    if s.speech_mode != "sarvam":
        raise SarvamFailed("stream_route_unavailable")  # the on-server engine does not stream (DEC-108)
    allowed(conn)
    started = time.monotonic()
    try:
        return SarvamStream(ref_id=ref_id, language=language)
    except SarvamFailed as exc:  # an outage on the streaming path counts toward the switch-off too (BLD-C117)
        meter(
            conn,
            "stt_stream",
            STT_MODEL,
            ref_id=ref_id,
            outcome=failed_outcome(exc.code),
            error_code=exc.code,
            started=started,
        )
        raise


class _Counted:
    """Shared bookkeeping: bytes relayed, segments heard, the language and a failure code."""

    def __init__(self) -> None:
        self._lock = threading.Condition()
        self._segments: list[str] = []
        self._language: str | None = None
        self._bytes = 0
        self._data_count = 0
        self._last_data_at = 0.0
        self._failure: str | None = None

    @property
    def seconds(self) -> float:
        return self._bytes / PCM_BYTES_PER_SECOND

    @property
    def failure(self) -> str | None:
        return self._failure

    def heard(self) -> Heard:
        with self._lock:
            return Heard(text=" ".join(self._segments).strip(), language=self._language, seconds=self.seconds)

    def _add(self, text: str, language: str | None) -> None:
        with self._lock:
            if text.strip():
                self._segments.append(text.strip())
            if language:
                self._language = language
            self._data_count += 1
            self._last_data_at = time.monotonic()
            self._lock.notify_all()


class SarvamStream(_Counted):
    """One saaras:v4 streaming session. Audio is relayed as it arrives: base64 inside a JSON message, never
    decoded, kept or logged. A reader thread collects what Sarvam hears. `finish` flushes, waits briefly for the
    last words and closes."""

    def __init__(self, *, ref_id: str | None, language: str = "unknown") -> None:
        super().__init__()
        self.ref_id = ref_id
        self._closing = threading.Event()
        self._ws = _ws_open(
            "/speech-to-text/ws",
            {
                "model": STT_MODEL,
                "mode": _stt_mode(),
                "language-code": language,
                "sample_rate": str(PCM_RATE),
                "input_audio_codec": "pcm_s16le",
                "vad_signals": "true",
                "flush_signal": "true",
            },
        )
        self._reader = threading.Thread(target=self._read, name="sarvam-stt", daemon=True)
        self._reader.start()

    def send(self, pcm: bytes) -> None:
        if self._failure:
            raise SarvamFailed(self._failure)
        message = json.dumps(
            {
                "audio": {
                    "data": base64.b64encode(pcm).decode("ascii"),
                    "sample_rate": str(PCM_RATE),
                    "encoding": "audio/wav",
                }
            }
        )
        try:
            self._ws.send(message)
        except (WebSocketException, OSError):
            self._failure = "stream_broken"
            raise SarvamFailed("stream_broken") from None
        self._bytes += len(pcm)

    def _read(self) -> None:
        try:
            for raw in self._ws:
                try:
                    msg = json.loads(raw)
                except (TypeError, ValueError):
                    continue
                if not isinstance(msg, dict):
                    continue
                kind, data = msg.get("type"), msg.get("data")
                if kind == "data" and isinstance(data, dict):
                    text = data.get("transcript")
                    lang = data.get("language_code")
                    self._add(text if isinstance(text, str) else "", lang if isinstance(lang, str) else None)
                elif kind == "error":
                    self._failure = "hosted_stream_error"
                    break
        except (WebSocketException, OSError):
            if not self._closing.is_set():
                self._failure = self._failure or "stream_broken"
        finally:
            with self._lock:
                self._lock.notify_all()

    def finish(self) -> Heard:
        """Flush, then wait for the flush's words (or a short while if none come), then close."""
        flushed_at = time.monotonic()
        before = self._data_count
        with contextlib.suppress(WebSocketException, OSError):  # already broken: what was heard still counts
            self._ws.send(json.dumps({"type": "flush"}))
        deadline = flushed_at + STT_FINISH_WAIT_S
        with self._lock:
            while self._reader.is_alive():
                now = time.monotonic()
                if now >= deadline:
                    break
                if self._data_count > before:
                    if now - self._last_data_at >= STT_QUIET_S:
                        break
                elif now - flushed_at >= STT_FIRST_WORDS_S:
                    break
                self._lock.wait(0.1)
        self.close()
        return self.heard()

    def close(self) -> None:
        self._closing.set()
        with contextlib.suppress(Exception):  # already closed or broken: nothing left to release
            self._ws.close()


class FakeStream(_Counted):
    """Dev and tests only (refused outside them, BLD-C007). A chunk that carries `FAKE-TRANSCRIPT:<words>` is heard
    as those words; otherwise every 5 seconds of audio is heard as the fixed sample. No audio is decoded."""

    def __init__(self) -> None:
        super().__init__()
        self._unheard = 0

    def send(self, pcm: bytes) -> None:
        self._bytes += len(pcm)
        at = pcm.find(FAKE_MARKER)
        if at >= 0:
            self._add(pcm[at + len(FAKE_MARKER) :].split(b"\0", 1)[0].decode("utf-8", "replace"), "en-IN")
            return
        self._unheard += len(pcm)
        if self._unheard >= 5 * PCM_BYTES_PER_SECOND:
            self._unheard = 0
            self._add(FAKE_SAMPLE, "en-IN")

    def finish(self) -> Heard:
        return self.heard()

    def close(self) -> None:
        return None


# ---- text to speech ---------------------------------------------------------------------------------------


def tts(
    masked: str,
    *,
    lang: str = "en-IN",
    speaker: str | None = None,
    conn: Conn | None = None,
    ref_id: str | None = None,
) -> Iterator[bytes]:
    """Masked text to MP3 with bulbul:v4-flash over one WebSocket: a text message per sentence (under 500
    characters), then a flush; audio is yielded as it arrives, until Sarvam's "final" event."""
    messages = [
        cut for sentence in sentences(masked) for cut in _cut(sentence, TTS_MAX_CHARS)
    ]  # a sentence each
    check_masked(masked)
    if not messages:
        return
    if _fake():
        yield from _fake_mp3(messages)
        return
    allowed(conn)
    chars = sum(len(m) for m in messages)
    started = time.monotonic()
    outcome, code = "route_error", "hosted_unreachable"
    try:
        ws = _ws_open("/text-to-speech/ws", {"model": TTS_MODEL, "send_completion_event": "true"})
        try:
            ws.send(
                json.dumps(
                    {
                        "type": "config",
                        "data": {
                            "model": TTS_MODEL,
                            "language_code": lang,
                            "speaker": speaker or get_settings().sarvam_tts_speaker,
                            "output_audio_codec": TTS_CODEC,
                            "output_audio_bitrate": TTS_BITRATE,
                            "speech_sample_rate": TTS_SAMPLE_RATE,
                            "max_chunk_length": TTS_MAX_CHARS,
                        },
                    }
                )
            )
            for m in messages:
                ws.send(json.dumps({"type": "text", "data": {"text": m}}))
            ws.send(json.dumps({"type": "flush"}))
            got_audio = False
            deadline = started + TTS_DEADLINE_S
            while True:
                left = deadline - time.monotonic()
                if left <= 0:  # the whole part, not just each wait (BLD-C117)
                    code = "hosted_timeout"
                    raise SarvamFailed(code)
                try:
                    raw = ws.recv(timeout=min(TTS_RECV_TIMEOUT_S, left))
                except TimeoutError:
                    code = "hosted_timeout"
                    raise SarvamFailed(code) from None
                try:
                    msg = json.loads(raw)
                except (TypeError, ValueError):
                    continue
                kind = msg.get("type") if isinstance(msg, dict) else None
                data = msg.get("data") if isinstance(msg, dict) else None
                if kind == "audio" and isinstance(data, dict) and isinstance(data.get("audio"), str):
                    try:
                        audio = base64.b64decode(data["audio"], validate=True)
                    except ValueError:
                        code = "hosted_bad_reply"
                        raise SarvamFailed(code) from None
                    got_audio = True
                    yield audio
                elif kind == "event" and isinstance(data, dict) and data.get("event_type") == "final":
                    break
                elif kind == "error":
                    code = "hosted_tts_error"
                    raise SarvamFailed(code)
            if not got_audio:
                code = "hosted_no_audio"
                raise SarvamFailed(code)
            outcome, code = "ok", ""
        finally:
            with contextlib.suppress(Exception):  # already closed: nothing to release
                ws.close()
    except GeneratorExit:  # the listener went away: not an error, and not counted against Sarvam
        outcome, code = "cancelled", ""
        raise
    except SarvamFailed as exc:
        code = exc.code
        raise
    except (WebSocketException, OSError):
        code = "stream_broken"
        raise SarvamFailed(code) from None
    finally:
        meter(
            conn,
            "tts",
            TTS_MODEL,
            ref_id=ref_id,
            outcome=failed_outcome(code) if outcome == "route_error" else outcome,
            error_code=code or None,
            chars=chars,
            started=started,
        )


def _fake_mp3(messages: Iterable[str]) -> Iterator[bytes]:
    """Silent MPEG-2 Layer III frames (24 kHz, 64 kbit/s, 576 samples each), one per 4 characters, so lengths can
    be computed from the audio as for the real thing."""
    for m in messages:
        yield fake_frames(max(1, len(m) // 4))


def fake_frames(count: int) -> bytes:
    header = bytes([0xFF, 0xF3, 0x84, 0xC4])  # MPEG-2, Layer III, no CRC, 64 kbit/s, 24 kHz, no padding
    frame_len = 72 * 64_000 // 24_000  # 192 bytes
    return (header + bytes(frame_len - 4)) * count
