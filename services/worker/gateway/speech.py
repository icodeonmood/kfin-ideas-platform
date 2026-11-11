"""Speech to text for voice notes in quick capture (DEC-096). The route is set by `SPEECH_MODE`.

- `fake` (dev and tests): a synthetic test recording carries its own text after the marker `FAKE-TRANSCRIPT:`;
  any other recording gives one fixed sample sentence. No audio is decoded.
- `local`: the engine runs on KFin's own server, no third party. Outside dev and test it must be the isolated
  speech service (`SPEECH_ENGINE_URL`, its own container with no route to the database, the store or the
  internet; BLD-C012), and refuses with `isolation_required` without it. In dev and test it may run in a child
  process of the worker (`gateway/speech_child.py`): a cleared environment, closed file descriptors, resource
  limits and a timeout, but the same user, filesystem and network as the worker, so it bounds a costly file and
  is not a security boundary against a decoder exploit. The library is installed only in images built with
  `--build-arg WITH_SPEECH=1`, and the model files come from `SPEECH_MODEL_PATH` (never fetched at run time,
  never in Git), like BGE-M3 (BLD-080). faster-whisper first; the engine interface lets AI4Bharat IndicConformer
  slot in for Indian languages ("coming soon").
- `fake` is refused outside dev and test (`fake_not_allowed`, BLD-C007).
- Hosted routes (`sarvam` first): a model call that sends raw voice to a third party. Voice cannot be tagged
  before it leaves (non-negotiable 2), so a hosted route refuses unless BOTH `SPEECH_HOSTED_APPROVAL` names the
  InfoSec and DPO approval AND the `speech.hosted` switch is on. Both are off at launch. Plain HTTP, no vendor
  SDK (non-negotiable 1); the vendor's reply is never logged or kept beyond the transcript.

Nothing here logs the recording or the text. Errors carry a code only.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from core import isolated, killswitch
from core.config import get_settings
from core.db import Conn

FAKE_MARKER = b"FAKE-TRANSCRIPT:"
FAKE_SAMPLE = (
    "Branch staff type every change of bank form twice because the scanned copy is hard to read, "
    "and it adds a day to each request."
)
HOSTED = frozenset({"sarvam"})


class SpeechUnavailable(Exception):
    """The route could not turn the recording into text. `code` is safe to log and store."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class HostedRefused(SpeechUnavailable):
    """A hosted route was asked for without its approval and its switch (DEC-096)."""


@dataclass(frozen=True)
class Transcript:
    text: str
    language: str | None
    seconds: float | None


class Engine(Protocol):
    name: str

    def transcribe(self, data: bytes, mime: str) -> Transcript: ...


def transcribe(data: bytes, mime: str, conn: Conn | None = None) -> Transcript:
    """Turn one recording into text through the configured route."""
    s = get_settings()
    mode = s.speech_mode
    if mode == "fake":
        if s.is_production_like:  # a sample sentence must never stand in for someone's words (BLD-C007)
            raise SpeechUnavailable("fake_not_allowed")
        return _fake(data)
    if mode == "local":
        if s.speech_engine_url:
            return _speech_service(data, mime)
        if s.is_production_like:  # the in-worker child is not a security boundary (BLD-C012)
            raise SpeechUnavailable("isolation_required")
        return local_engine().transcribe(data, mime)
    if mode in HOSTED:
        hosted_allowed(conn)
        return _sarvam(data, mime)
    raise SpeechUnavailable("unknown_mode")


def hosted_allowed(conn: Conn | None = None) -> None:
    """Raise unless a hosted route has its approval reference and its switch is on (both, every time)."""
    if not get_settings().speech_hosted_approval.strip():
        raise HostedRefused("hosted_not_approved")
    if not killswitch.is_on_fresh("speech.hosted", conn):  # past the cache: raw voice would leave (BLD-C011)
        raise HostedRefused("hosted_switched_off")


def _fake(data: bytes) -> Transcript:
    at = data.find(FAKE_MARKER)
    if at >= 0:
        text = data[at + len(FAKE_MARKER) :].split(b"\0", 1)[0].decode("utf-8", "replace").strip()
        return Transcript(text=text, language=None, seconds=None)
    return Transcript(text=FAKE_SAMPLE, language="en", seconds=None)


# ---- the engine on KFin's own server ----------------------------------------------------------------------

_engine: Engine | None = None


def local_engine() -> Engine:
    global _engine
    if _engine is None:
        name = get_settings().speech_local_engine
        if name == "faster-whisper":
            _engine = FasterWhisper()
        elif name == "indic-conformer":
            raise SpeechUnavailable("engine_coming_soon")
        else:
            raise SpeechUnavailable("unknown_engine")
    return _engine


def _speech_service(data: bytes, mime: str) -> Transcript:
    """The isolated speech service (`speech_service/service.py`, its own container on an internal network with
    no route to the database, the store or the internet; BLD-C012, BLD-C015). The recording goes over HTTP with
    the shared internal token; the answer must say which engine heard it, and a `fake` engine is refused outside
    dev and test. Errors carry a code only."""
    import httpx

    s = get_settings()
    try:
        r = httpx.post(
            f"{s.speech_engine_url.rstrip('/')}/transcribe",
            content=data,
            headers={
                "X-Speech-Token": s.speech_service_token,
                "X-Max-Seconds": str(s.speech_max_seconds + 15),
                "Content-Type": "application/octet-stream",
            },
            timeout=httpx.Timeout(s.speech_timeout_s + 15, connect=5.0),
        )
    except httpx.TimeoutException:
        raise SpeechUnavailable("engine_timeout") from None
    except httpx.HTTPError:
        raise SpeechUnavailable("engine_unreachable") from None
    try:
        body = r.json()
    except ValueError:
        body = {}
    if not isinstance(body, dict):
        body = {}
    if r.status_code == 401:
        raise SpeechUnavailable("engine_unauthorized")
    if r.status_code != 200:
        code = str(body.get("error") or f"engine_{r.status_code}")
        raise SpeechUnavailable(code if code.replace("_", "").isalnum() else f"engine_{r.status_code}")
    if body.get("engine") == "fake" and s.is_production_like:
        raise SpeechUnavailable(
            "fake_not_allowed"
        )  # a sample sentence must never stand in for someone's words
    text = body.get("text")
    if not isinstance(text, str):
        raise SpeechUnavailable("engine_bad_reply")
    language = body.get("language")
    seconds = body.get("seconds")
    return Transcript(
        text=text,
        language=language if isinstance(language, str) else None,
        seconds=float(seconds) if isinstance(seconds, int | float) else None,
    )


class FasterWhisper:
    """faster-whisper (CTranslate2) on CPU with int8 weights, about 1–2 GB of memory for a small or medium
    multilingual model, for dev and test only (BLD-C012). The decode and the transcription run in a child process
    (`gateway/speech_child.py`) with a cleared environment (no database URL, keys or tokens passed), no inherited
    file descriptors, memory and CPU limits and a timeout (BLD-C005), so a costly or crashing file costs one child.
    It still runs as the worker's user, sees the worker's filesystem (including `/proc/<pid>/environ` of the
    worker) and network: a decoder exploit could reach secrets and the database. Hence the isolated service
    outside dev and test. The model loads per note."""

    name = "faster-whisper"
    CHILD = Path(__file__).resolve().with_name("speech_child.py")

    def __init__(self) -> None:
        if not get_settings().speech_model_path:
            raise SpeechUnavailable("model_path_missing")

    def transcribe(self, data: bytes, mime: str) -> Transcript:
        s = get_settings()
        try:
            answer = isolated.run(
                self.CHILD,
                [s.speech_model_path, str(s.speech_max_seconds + 15), str(s.speech_threads)],
                data,
                timeout_s=s.speech_timeout_s,
                memory_mb=s.speech_memory_mb,
                cpu_s=s.speech_timeout_s * max(1, s.speech_threads),
                env={"OMP_NUM_THREADS": str(s.speech_threads), "HF_HUB_OFFLINE": "1"},
            )
        except isolated.IsolatedFailed as exc:
            raise SpeechUnavailable(f"engine_{exc.code}") from None
        if "error" in answer:
            raise SpeechUnavailable(str(answer["error"]))
        return Transcript(
            text=str(answer.get("text", "")),
            language=answer.get("language"),
            seconds=float(answer.get("seconds") or 0.0),
        )


# ---- hosted routes (off until InfoSec and the DPO approve) -------------------------------------------------


def _sarvam(data: bytes, mime: str) -> Transcript:
    """Sarvam's speech-to-text API, language detected. Built for DEC-096 and never exercised against the real
    service: check the request against Sarvam's current documentation before the switch goes on."""
    import httpx

    s = get_settings()
    if not s.speech_hosted_key:
        raise SpeechUnavailable("hosted_key_missing")
    try:
        r = httpx.post(
            s.speech_hosted_url,
            headers={"api-subscription-key": s.speech_hosted_key},
            files={"file": ("voice-note", data, mime)},
            data={"model": "saarika:v2.5", "language_code": "unknown"},
            timeout=60.0,
        )
    except httpx.HTTPError:
        raise SpeechUnavailable("hosted_unreachable") from None
    if r.status_code != 200:
        raise SpeechUnavailable(f"hosted_{r.status_code}")
    try:
        body = r.json()
        text = str(body["transcript"]).strip()
    except (ValueError, KeyError, TypeError):
        raise SpeechUnavailable("hosted_bad_reply") from None
    return Transcript(text=text, language=body.get("language_code"), seconds=None)
