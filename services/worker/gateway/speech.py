"""Speech to text for voice notes in quick capture (DEC-096). The route is set by `SPEECH_MODE`.

- `fake` (dev and tests): a synthetic test recording carries its own text after the marker `FAKE-TRANSCRIPT:`;
  any other recording gives one fixed sample sentence. No audio is decoded.
- `local`: the engine runs inside the worker on KFin's own server, with no network. The library is installed
  only in images built with `--build-arg WITH_SPEECH=1` and the model files come from `SPEECH_MODEL_PATH`
  (never fetched at run time, never in Git), like BGE-M3 (BLD-080). faster-whisper first; the engine interface
  lets AI4Bharat IndicConformer slot in for Indian languages ("coming soon").
- Hosted routes (`sarvam` first): a model call that sends raw voice to a third party. Voice cannot be tagged
  before it leaves (non-negotiable 2), so a hosted route refuses unless BOTH `SPEECH_HOSTED_APPROVAL` names the
  InfoSec and DPO approval AND the `speech.hosted` switch is on. Both are off at launch. Plain HTTP, no vendor
  SDK (non-negotiable 1); the vendor's reply is never logged or kept beyond the transcript.

Nothing here logs the recording or the text. Errors carry a code only.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any, Protocol

from core import killswitch
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
    mode = get_settings().speech_mode
    if mode == "fake":
        return _fake(data)
    if mode == "local":
        return local_engine().transcribe(data, mime)
    if mode in HOSTED:
        hosted_allowed(conn)
        return _sarvam(data, mime)
    raise SpeechUnavailable("unknown_mode")


def hosted_allowed(conn: Conn | None = None) -> None:
    """Raise unless a hosted route has its approval reference and its switch is on (both, every time)."""
    if not get_settings().speech_hosted_approval.strip():
        raise HostedRefused("hosted_not_approved")
    if not killswitch.is_on("speech.hosted", conn):
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


class FasterWhisper:
    """faster-whisper (CTranslate2) on CPU with int8 weights: about 1–2 GB of memory for a small or medium
    multilingual model. The language is detected; voice-activity filtering drops silence."""

    name = "faster-whisper"

    def __init__(self) -> None:
        try:
            from faster_whisper import WhisperModel  # type: ignore[import-not-found]
        except ImportError:
            raise SpeechUnavailable("engine_not_installed") from None  # needs WITH_SPEECH=1
        path = get_settings().speech_model_path
        if not path:
            raise SpeechUnavailable("model_path_missing")
        self._model: Any = WhisperModel(path, device="cpu", compute_type="int8", local_files_only=True)

    def transcribe(self, data: bytes, mime: str) -> Transcript:
        limit = get_settings().speech_max_seconds
        try:
            segments, info = self._model.transcribe(io.BytesIO(data), beam_size=1, vad_filter=True)
            if info.duration and info.duration > limit + 15:
                raise SpeechUnavailable("too_long")
            text = " ".join(s.text.strip() for s in segments).strip()
        except SpeechUnavailable:
            raise
        except Exception:  # decoder and model errors can carry audio details: keep only a code
            raise SpeechUnavailable("unreadable") from None
        return Transcript(text=text, language=info.language, seconds=float(info.duration or 0.0))


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
