"""Drafts "By voice" (DEC-108 (1) and (2), L-DRAFT.voice, BLD-C112): the person speaks, the words appear as they
speak, and at the end their own words and an English copy go to the draft as one message.

The flow, one stream per note, held by the worker (the browser never holds the key):

1. `start`: `capture.voice` on, the person's own draft, at most `voice.max_per_hour` new notes an hour (voice notes
   and streams together). A live stream of theirs on another tab or device ends first ("replaced"). The worker
   opens Sarvam's streaming speech to text (`gateway.sarvam.stt_stream`, saaras:v4).
2. `chunk`: about 1 second of 16 kHz mono 16-bit PCM at a time, numbered from 0. Each is relayed to Sarvam as it
   arrives: never stored, decoded or opened here, so nothing is written to the store and there is no file scan
   (DEC-108 bends non-negotiable 2 for audio). The length is counted from the bytes (32,000 a second), so the
   3-minute cap is exact without decoding. `speech.hosted` is read fresh before every chunk goes out; if it or
   `capture.voice` has gone off, the stream ends and keeps what was heard. The answer carries the words heard so
   far, the person's own (`text`, with `spans` for the customer details found), for them alone.
3. `end` (or 20 seconds without a chunk, or the 3-minute cap): flush, wait briefly for the last words, close. The
   words are normalised (spoken numbers become digits), masked (`hide_text`, DEC-103), and the masked copy is
   tagged like a model call (names and client organisations as tags, then the leak check: BLD-C200), translated
   into English with mayura:v1, code-mixed, worded for the person's choice in Profile (`prefs`), its tags checked
   and swapped back for the sharer, then masked again (`_english`). The unmasked words are sealed with the vault
   key; only the masked copy and the masked English go anywhere else.
4. `voice_to_message`: lane C's draft builder (branch c/draft) takes it as a message (via `voice`) and the held
   copies are deleted. Otherwise `sweep` deletes them after 24 hours.

Polling, not server-sent events: `A-API.events` does not exist yet, so the chunk answers carry the words heard so
far, and `status` (`GET /api/drafts/:id/voice/:stream`) gives the rest. Nothing here logs text or audio: IDs,
counts, seconds and codes only.
"""

from __future__ import annotations

import contextlib
import json
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from psycopg.types.json import Jsonb

from core import killswitch
from core.config import get_settings
from core.crypto import decrypt_bytes, decrypt_json, encrypt_bytes, encrypt_json
from core.db import Conn, connect
from core.logging import get_logger
from gateway import sarvam
from gateway.speech import SpeechUnavailable
from hide.core import scope_for
from pii import vault
from pii.restore import restore
from speech import prefs
from speech.adapters import hide_text, mask_for_service
from voice.numbers import normalise

log = get_logger("voice_stream")

SAMPLE_RATE = sarvam.PCM_RATE
BYTES_PER_SECOND = sarvam.PCM_BYTES_PER_SECOND
MAX_CHUNK_BYTES = 2 * BYTES_PER_SECOND  # a chunk is about 1 second; 2 allows a late timeslice
IDLE_S = 20.0  # no chunk this long: the person left (J-RESUME/1); end and keep what was heard
WALL_MARGIN_S = 30.0  # the stream's clock may run this far past 3 minutes of audio before it is ended
# Shown before the person records (DEC-108 (5)): plain words, no vendor name (DEC-096). For HR's copy sign-off.
NOTICE = (
    "Your voice note goes to an Indian speech service to turn it into text. "
    "You can check the text before you send it."
)
EN_LABEL = (
    "Typed up in English"  # L-DRAFT.voice/4, `Ways` copy: the English copy is labelled as a translation
)
# mayura:v1 takes these as a source; any other language is sent as "auto".
MAYURA_SOURCES = frozenset(
    {"bn-IN", "en-IN", "gu-IN", "hi-IN", "kn-IN", "ml-IN", "mr-IN", "od-IN", "pa-IN", "ta-IN", "te-IN"}
)
LANGUAGES = {
    "as-IN": "Assamese", "bn-IN": "Bengali", "brx-IN": "Bodo", "doi-IN": "Dogri", "en-IN": "English",
    "gu-IN": "Gujarati", "hi-IN": "Hindi", "kn-IN": "Kannada", "kok-IN": "Konkani", "ks-IN": "Kashmiri",
    "mai-IN": "Maithili", "ml-IN": "Malayalam", "mni-IN": "Manipuri", "mr-IN": "Marathi", "ne-IN": "Nepali",
    "od-IN": "Odia", "pa-IN": "Punjabi", "sa-IN": "Sanskrit", "sat-IN": "Santali", "sd-IN": "Sindhi",
    "ta-IN": "Tamil", "te-IN": "Telugu", "ur-IN": "Urdu",
}  # fmt: skip
EndedBy = Literal["person", "idle", "limit", "replaced", "paused"]
# The English copy failed in the tagging or the swapping back, not at the service (BLD-C200): a code, never text.
TAGGING_FAILED = "translation_tagging_failed"


def max_seconds() -> int:
    return get_settings().speech_max_seconds  # 180: L-DRAFT.voice/1


def chunk_contract() -> dict[str, Any]:
    """What the browser sends (for the S-04 builder): raw little-endian 16-bit mono PCM at 16 kHz, about a second
    a chunk. Sarvam's streaming API takes only WAV or PCM, so the browser captures PCM with an AudioWorklet and
    downsamples to 16 kHz; MediaRecorder's WebM/Opus is not accepted."""
    return {
        "encoding": "pcm_s16le",
        "sample_rate": SAMPLE_RATE,
        "channels": 1,
        "chunk_seconds": 1,
        "max_chunk_bytes": MAX_CHUNK_BYTES,
        "max_seconds": max_seconds(),
        "idle_seconds": int(IDLE_S),
    }


class VoiceRefused(Exception):
    """`code` is safe to log and to show (via the screen's own copy)."""

    def __init__(self, status: int, code: str, body: dict[str, Any] | None = None) -> None:
        super().__init__(code)
        self.status = status
        self.code = code
        self.body = body or {}


@dataclass(frozen=True)
class VoiceMessage:
    """What the draft takes as one message (E-ENTITIES Message, `via: 'voice'`).

    - `text`: the person's own words as heard, unmasked. Theirs alone: store it sealed (`idea_words_sealed`), never
      anywhere else.
    - `text_masked`: the same words masked (DEC-103): the message's copy for the desk and the committee.
    - `spans`: where the details were in `text` ({start, end, kind}), for the person's own view.
    - `text_en`: the English translation of the masked words (tagged on the way out, BLD-C200), masked again;
      labelled `text_en_label`. The working copy for drafting, matching and the review desk (DEC-108 (1),
      DEC-095). None if the translation failed: run `_english` again on `text_masked` (never `sarvam.translate` alone).
    - `translated`: False when the person spoke English and `text_en` is `text_masked` as is.
    - `lang`, `language`, `seconds`, `summary`: "Voice message, 1 minute 12 seconds, in Telugu" (L-DRAFT.voice/4).
    """

    stream_id: str
    text: str
    text_masked: str
    spans: list[dict[str, Any]]
    text_en: str | None
    text_en_label: str
    translated: bool | None
    lang: str | None
    language: str | None
    seconds: float
    summary: str
    via: str = "voice"


# ---- the database, behind one small class so the logic can be tested without Postgres -----------------------


class Store:
    def __init__(self, conn: Conn) -> None:
        self.conn = conn

    def owned_draft(self, idea_uuid: str, by_code: str) -> str:
        """'draft', 'not_a_draft' or 'not_found' (someone else's draft looks missing)."""
        row = self.conn.execute(
            "SELECT status, contributor_code FROM ideas WHERE id = %s", (idea_uuid,)
        ).fetchone()
        if row is None or row["contributor_code"] != by_code:
            return "not_found"
        return "draft" if row["status"] == "draft" else "not_a_draft"

    def begin(self, stream_id: str, idea_uuid: str, by_code: str, per_hour: int) -> bool:
        """Insert the stream unless the person has reached the hourly limit (voice notes and streams together).
        One person's starts count one at a time (an advisory lock for the transaction)."""
        with self.conn.transaction():
            self.conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"voice:{by_code}",))
            row = self.conn.execute(
                "SELECT (SELECT count(*) FROM voice_notes WHERE uploaded_by_code = %s "
                "AND created_at > now() - interval '1 hour') + (SELECT count(*) FROM voice_streams "
                "WHERE by_code = %s AND created_at > now() - interval '1 hour') AS n",
                (by_code, by_code),
            ).fetchone()
            if row is not None and int(row["n"]) >= per_hour:
                return False
            self.conn.execute(
                "INSERT INTO voice_streams (id, idea_uuid, by_code) VALUES (%s, %s, %s)",
                (stream_id, idea_uuid, by_code),
            )
        return True

    def live_of(self, by_code: str) -> list[str]:
        rows = self.conn.execute(
            "SELECT id FROM voice_streams WHERE by_code = %s AND state = 'live'", (by_code,)
        ).fetchall()
        return [str(r["id"]) for r in rows]

    def row(self, stream_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM voice_streams WHERE id = %s", (stream_id,)).fetchone()
        return dict(row) if row else None

    def done(self, stream_id: str, values: dict[str, Any]) -> None:
        self.conn.execute(
            "UPDATE voice_streams SET state = 'done', ended_by = %s, ended_at = now(), speech_seconds = %s, "
            "chunk_count = %s, lang = %s, own_words_sealed = %s, masked_encrypted = %s, text_en_encrypted = %s, "
            "translated = %s, spans = %s, hidden_count = %s, failure = %s WHERE id = %s AND state = 'live'",
            (
                values["ended_by"],
                values["seconds"],
                values["chunks"],
                values["lang"],
                values["own_words_sealed"],
                values["masked_encrypted"],
                values["text_en_encrypted"],
                values["translated"],
                Jsonb(values["spans"]),
                values["hidden_count"],
                values.get("failure"),
                stream_id,
            ),
        )

    def failed(self, stream_id: str, code: str, ended_by: str | None, seconds: float, chunks: int) -> None:
        self.conn.execute(
            "UPDATE voice_streams SET state = 'failed', failure = %s, ended_by = %s, ended_at = now(), "
            "speech_seconds = %s, chunk_count = %s WHERE id = %s AND state = 'live'",
            (code, ended_by, seconds, chunks, stream_id),
        )

    def handed(self, stream_id: str) -> None:
        self.conn.execute(
            "UPDATE voice_streams SET handed_at = now(), own_words_sealed = NULL, masked_encrypted = NULL, "
            "text_en_encrypted = NULL WHERE id = %s",
            (stream_id,),
        )

    def sweep(self) -> tuple[int, int]:
        """What is held past 24 hours, and streams left live by a worker restart (10 minutes old)."""
        held = self.conn.execute(
            "UPDATE voice_streams SET own_words_sealed = NULL, masked_encrypted = NULL, text_en_encrypted = NULL "
            "WHERE own_words_sealed IS NOT NULL AND delete_after < now() RETURNING id"
        ).fetchall()
        lost = self.conn.execute(
            "UPDATE voice_streams SET state = 'failed', failure = 'stream_lost', ended_at = now() "
            "WHERE state = 'live' AND created_at < now() - interval '10 minutes' RETURNING id"
        ).fetchall()
        return len(held), len(lost)


StoreFactory = Callable[[Conn], Store]
_store: StoreFactory = Store  # tests swap in an in-memory store


# ---- the live streams this worker holds ------------------------------------------------------------------


@dataclass
class _Live:
    id: str
    idea_uuid: str
    by_code: str
    user_id: str | None
    stream: sarvam.SttStream
    started: float
    last_at: float
    next_seq: int = 0
    bytes: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)
    ending: bool = False  # set once, under the registry lock, by the one call that ends it
    # False for an answer to the review desk (lane B's BLD-B276): no English copy is made, so no text goes to
    # translation and no vault tags are made
    english: bool = True
    ended: threading.Event = field(default_factory=threading.Event)


_live: dict[str, _Live] = {}
_registry = threading.Lock()
_clock: Callable[[], float] = time.monotonic
_reaper: threading.Thread | None = None


def _hosted_check(conn: Conn) -> None:
    """Before anything goes out: `capture.voice`, and in the Sarvam route `speech.hosted` read fresh with the
    approval and the key (BLD-C011)."""
    if not killswitch.is_on("capture.voice", conn):
        raise SpeechUnavailable("voice_paused")
    if get_settings().speech_mode == "sarvam":
        sarvam.allowed(conn)


def start(conn: Conn, *, idea_uuid: str, by_code: str, user_id: str | None = None) -> dict[str, Any]:
    if not killswitch.is_on("capture.voice", conn):
        raise VoiceRefused(503, "voice_paused")
    owned = _store(conn).owned_draft(idea_uuid, by_code)
    if owned != "draft":
        raise VoiceRefused(404 if owned == "not_found" else 409, owned)
    return _open(conn, idea_uuid=idea_uuid, by_code=by_code, user_id=user_id)


def _open(
    conn: Conn, *, idea_uuid: str, by_code: str, user_id: str | None, english: bool = True
) -> dict[str, Any]:
    """Everything `start` does after its owner check: the person's other live stream ends ("replaced"), the hourly
    limit, Sarvam's stream, the registry and the reaper. Lane B's `desk.answer_voice` opens an answer's stream here
    after its own check, with `english=False` (BLD-B276). `capture.voice` is checked here too, so no caller can
    forget it."""
    if not killswitch.is_on("capture.voice", conn):
        raise VoiceRefused(503, "voice_paused")
    store = _store(conn)
    for other in store.live_of(by_code):  # the same person on another tab or device: that one ends first
        try:
            end(conn, other, idea_uuid=None, by_code=by_code, ended_by="replaced")
        except VoiceRefused:
            store.failed(other, "stream_lost", "replaced", 0, 0)
    from voice.service import limits

    stream_id = str(uuid.uuid4())
    if not store.begin(stream_id, idea_uuid, by_code, limits().max_per_hour):
        raise VoiceRefused(429, "too_many_this_hour")
    try:
        stream = sarvam.stt_stream(conn=conn, ref_id=stream_id)
    except SpeechUnavailable as exc:
        store.failed(stream_id, exc.code, None, 0, 0)
        log.info("voice_stream.refused", stream_id=stream_id, reason_code=exc.code)
        paused = exc.code in ("hosted_switched_off", "hosted_not_approved", "hosted_key_missing")
        raise VoiceRefused(
            503 if paused else 502, "voice_paused" if paused else "voice_unavailable"
        ) from None
    now = _clock()
    with _registry:
        _live[stream_id] = _Live(stream_id, idea_uuid, by_code, user_id, stream, now, now, english=english)
    _ensure_reaper()
    log.info("voice_stream.started", stream_id=stream_id)
    return {"id": stream_id, "state": "live", **chunk_contract()}


def _owned_live(stream_id: str, idea_uuid: str | None, by_code: str) -> _Live | None:
    with _registry:
        live = _live.get(stream_id)
    if live is None:
        return None
    if live.by_code != by_code or (idea_uuid is not None and live.idea_uuid != idea_uuid):
        raise VoiceRefused(404, "not_found")
    return live


def _gone(conn: Conn, stream_id: str, idea_uuid: str | None, by_code: str) -> VoiceRefused:
    """A stream this worker does not hold: ended (409 with its view), lost to a restart (410), or not theirs (404)."""
    row = _store(conn).row(stream_id)
    if (
        row is None
        or row["by_code"] != by_code
        or (idea_uuid is not None and str(row["idea_uuid"]) != idea_uuid)
    ):
        return VoiceRefused(404, "not_found")
    if row["state"] == "live":
        _store(conn).failed(
            stream_id, "stream_lost", None, float(row["speech_seconds"]), int(row["chunk_count"])
        )
        return VoiceRefused(410, "stream_lost")
    return VoiceRefused(409, "stream_ended", _view(row, by_code))


def chunk(
    conn: Conn, stream_id: str, *, idea_uuid: str, by_code: str, seq: int, data: bytes
) -> dict[str, Any]:
    live = _owned_live(stream_id, idea_uuid, by_code)
    if live is None:
        raise _gone(conn, stream_id, idea_uuid, by_code)
    if not data:
        raise VoiceRefused(400, "chunk_empty")
    if len(data) > MAX_CHUNK_BYTES:
        raise VoiceRefused(413, "chunk_too_large")
    if len(data) % 2:
        raise VoiceRefused(400, "not_pcm")  # 16-bit samples come in pairs of bytes
    if live.ending:
        raise VoiceRefused(409, "stream_ending")
    try:
        _hosted_check(conn)
    except SpeechUnavailable:
        body = end(conn, stream_id, idea_uuid=idea_uuid, by_code=by_code, ended_by="paused")
        raise VoiceRefused(503, "voice_paused", body) from None
    cap = max_seconds() * BYTES_PER_SECOND
    with live.lock:
        if seq < live.next_seq:  # a retry of a chunk already relayed: the same answer, nothing sent twice
            return _partial(live)
        if seq > live.next_seq:
            raise VoiceRefused(409, "chunk_out_of_order", {"next_seq": live.next_seq})
        send = data[: max(0, cap - live.bytes)]
        if send:
            with contextlib.suppress(
                SpeechUnavailable
            ):  # the reader records a failure; `end` keeps the words
                live.stream.send(send)
            live.bytes += len(send)
        live.next_seq = seq + 1
        live.last_at = _clock()
        at_cap = live.bytes >= cap
    if at_cap:
        return end(conn, stream_id, idea_uuid=idea_uuid, by_code=by_code, ended_by="limit")
    with live.lock:
        return _partial(live)


def _partial(live: _Live) -> dict[str, Any]:
    """The words so far, for the person alone (their own words; spans mark the details that others will not see)."""
    heard = live.stream.heard()
    text = heard.text
    return {
        "id": live.id,
        "state": "live",
        "next_seq": live.next_seq,
        "seconds": round(live.bytes / BYTES_PER_SECOND, 2),
        "text": text,
        "spans": hide_text(text).spans if text else [],
    }


def end(
    conn: Conn, stream_id: str, *, idea_uuid: str | None, by_code: str, ended_by: EndedBy = "person"
) -> dict[str, Any]:
    live = _owned_live(stream_id, idea_uuid, by_code)
    if live is None:
        gone = _gone(conn, stream_id, idea_uuid, by_code)
        if gone.code == "stream_ended":  # ending twice gives the same answer
            return gone.body
        raise gone
    with _registry:
        already = live.ending
        live.ending = True
    if already:  # another call (the person, the reaper) is ending it: answer with what it stores
        live.ended.wait(timeout=sarvam.STT_FINISH_WAIT_S + 10)
        row = _store(conn).row(stream_id)
        return _view(row, by_code) if row else {"id": stream_id, "state": "failed", "failure": "stream_lost"}
    try:
        return _finish(conn, live, ended_by)
    finally:
        with _registry:
            _live.pop(stream_id, None)
        live.ended.set()


def _finish(conn: Conn, live: _Live, ended_by: EndedBy) -> dict[str, Any]:
    stream_id = live.id
    by_code = live.by_code
    with live.lock:
        heard = live.stream.finish()
        failure = live.stream.failure
    seconds = round(live.bytes / BYTES_PER_SECOND, 2)
    sarvam.meter(
        conn,
        "stt_stream",
        sarvam.STT_MODEL,
        ref_id=stream_id,
        outcome="route_error" if failure and not heard.text else "ok",
        error_code=failure,
        seconds=seconds,
        started=live.started,
    )
    store = _store(conn)
    own = normalise(heard.text).strip() if heard.text else ""
    if not own:
        code = failure or "nothing_heard"
        store.failed(stream_id, code, ended_by, seconds, live.next_seq)
        log.info("voice_stream.failed", stream_id=stream_id, reason_code=code, chunk_count=live.next_seq)
        return {"id": stream_id, "state": "failed", "failure": code, "ended_by": ended_by}
    hidden = hide_text(own)
    lang = heard.language if heard.language in LANGUAGES else None
    if live.english:
        text_en, translated, translation_failure = _english(
            conn, stream_id, hidden.text, lang, live.user_id, idea_uuid=live.idea_uuid
        )
    else:  # an answer (BLD-B276): no English copy, and nothing reads as a failed one
        text_en, translated, translation_failure = None, False, None
    store.done(
        stream_id,
        {
            "ended_by": ended_by,
            "seconds": seconds,
            "chunks": live.next_seq,
            "lang": lang,
            "own_words_sealed": encrypt_bytes(own.encode(), _ctx("own_words", stream_id), kind="vault"),
            "masked_encrypted": encrypt_json({"text": hidden.text}, _ctx("masked", stream_id)),
            "text_en_encrypted": encrypt_json({"text": text_en}, _ctx("text_en", stream_id))
            if text_en is not None
            else None,
            "translated": translated,
            "spans": hidden.spans,
            "hidden_count": hidden.count,
            "failure": translation_failure,
        },
    )
    log.info(
        "voice_stream.done",
        stream_id=stream_id,
        speech_seconds=seconds,
        chunk_count=live.next_seq,
        hidden_count=hidden.count,
        reason_code=translation_failure or "ok",
    )
    row = store.row(stream_id)
    return _view(row, by_code) if row else {"id": stream_id, "state": "failed", "failure": "stream_lost"}


def _english(
    conn: Conn, stream_id: str, masked: str, lang: str | None, user_id: str | None, *, idea_uuid: str
) -> tuple[str | None, bool | None, str | None]:
    """The English copy of the masked words (text_en, translated, failure code), as a model call is made and its
    output kept (BLD-C200, non-negotiable 2; `draft.runs._restored`):

    1. masked for the service (`mask_for_service`: no pattern hit at all is left);
    2. tagged in the draft's vault scope and leak-checked (`sarvam.tag_for_service`): colleagues' and other names,
       client organisations and codes go as tags, never as written;
    3. translated (`sarvam.translate`), then every tag checked back (`sarvam.tags_back`). A tag the service broke
       fails the English copy (`translation_hosted_tags_broken`) the way any failed translation does: the person
       keeps their own words, with no English copy;
    4. the tags sent swapped back for the masked words they stand for, for the sharer, whose copy this is (it is read
       by them alone, and a model call re-tags it), then masked again as it returns (`hide_text`).

    Any other error in the tagging or the swapping back (the database, the vault key, a bad id) is
    `translation_tagging_failed`, like any failed translation: the person keeps their own words, never lost to a
    `stream_lost`. Both run in savepoints, so the caller's transaction stays usable for `store.done`. The translation
    itself runs outside any savepoint: no transaction is held open over the call, and its metering row is kept."""
    if lang == "en-IN":
        return masked, False, None
    gender = prefs.speaker_gender(prefs.refer_as(conn, user_id))
    try:
        scope = scope_for(idea_uuid)
        sent = sarvam.tag_for_service(mask_for_service(masked), conn=conn, scope_id=scope)  # in a savepoint
        got = sarvam.translate(
            sent.text,
            gender=gender,
            conn=conn,
            ref_id=f"stream:{stream_id}",
            source=lang if lang in MAYURA_SOURCES else "auto",
        )
        english = sarvam.tags_back(sent, got.text)
        if sent.tags:  # only the tags this call sent: tags_back let no other through
            with conn.transaction():  # a savepoint inside the caller's transaction
                known = vault.mapping(conn, scope)
            english = restore(english, {t: known[t] for t in sent.tags if t in known}, "real")
        return hide_text(english).text, got.translated, None
    except SpeechUnavailable as exc:  # the leak check's refusal, a broken tag, or the service's own failure
        return None, None, f"translation_{exc.code}"[:60]
    except Exception as exc:  # the type only: a message could quote a value
        log.warning(
            "voice_stream.translation_tagging_failed", stream_id=stream_id, error_type=type(exc).__name__
        )
        return None, None, TAGGING_FAILED


def _ctx(column: str, stream_id: str) -> str:
    return f"voice_streams.{column}:{stream_id}"


def _view(row: dict[str, Any], by_code: str) -> dict[str, Any]:
    """The person's view of a stream: for them alone (the caller checked they own the draft)."""
    stream_id = str(row["id"])
    if row["by_code"] != by_code:
        raise VoiceRefused(404, "not_found")
    if row["state"] == "failed":
        return {"id": stream_id, "state": "failed", "failure": row["failure"], "ended_by": row["ended_by"]}
    out: dict[str, Any] = {
        "id": stream_id,
        "state": row["state"],
        "seconds": float(row["speech_seconds"]),
        "ended_by": row["ended_by"],
    }
    if row["state"] != "done":
        return out
    if row["handed_at"] is not None or row["own_words_sealed"] is None:
        return {**out, "state": "handed" if row["handed_at"] is not None else "expired"}
    text = decrypt_bytes(bytes(row["own_words_sealed"]), _ctx("own_words", stream_id), kind="vault").decode()
    en = (
        decrypt_json(bytes(row["text_en_encrypted"]), _ctx("text_en", stream_id))["text"]
        if row["text_en_encrypted"] is not None
        else None
    )
    lang = row["lang"]
    return {
        **out,
        "text": text,
        "spans": row["spans"] if isinstance(row["spans"], list) else json.loads(row["spans"] or "[]"),
        "hidden_count": row["hidden_count"],
        "text_en": en,
        "text_en_label": EN_LABEL,
        "translated": row["translated"],
        "translation_failure": row["failure"],
        "lang": lang,
        "language": LANGUAGES.get(lang or ""),
        "summary": summary(float(row["speech_seconds"]), lang),
    }


def status(conn: Conn, stream_id: str, *, idea_uuid: str, by_code: str) -> dict[str, Any]:
    live = _owned_live(stream_id, idea_uuid, by_code)
    if live is not None:
        with live.lock:
            return _partial(live)
    row = _store(conn).row(stream_id)
    if row is None or str(row["idea_uuid"]) != idea_uuid or row["by_code"] != by_code:
        raise VoiceRefused(404, "not_found")
    if row["state"] == "live":  # this worker restarted mid-stream
        raise _gone(conn, stream_id, idea_uuid, by_code)
    return _view(row, by_code)


def voice_to_message(
    conn: Conn, stream_id: str, *, idea_uuid: str, by_code: str, consume: bool = True
) -> VoiceMessage | None:
    """Hand a finished voice note to the draft as one message (lane C's L-DRAFT builder owns messages).

    Call it from the message route (`POST /drafts/:id/messages` with `via: 'voice'` and the stream id) after the
    person has checked the words. Returns None when the stream is not theirs, not finished, already handed over or
    past its 24 hours. With `consume` (the default) the held copies are deleted once returned: store `text` sealed
    in `idea_words_sealed` and `text_masked` in `idea_messages`. If the person edited the words before sending,
    save their edited text instead and re-run `_english` on its masked copy (it tags before `sarvam.translate`).
    """
    row = _store(conn).row(stream_id)
    if (
        row is None
        or str(row["idea_uuid"]) != idea_uuid
        or row["by_code"] != by_code
        or row["state"] != "done"
    ):
        return None
    if row["handed_at"] is not None or row["own_words_sealed"] is None:
        return None
    view = _view(row, by_code)
    masked = decrypt_json(bytes(row["masked_encrypted"]), _ctx("masked", stream_id))["text"]
    message = VoiceMessage(
        stream_id=stream_id,
        text=view["text"],
        text_masked=masked,
        spans=view["spans"],
        text_en=view["text_en"],
        text_en_label=EN_LABEL,
        translated=view["translated"],
        lang=view["lang"],
        language=view["language"],
        seconds=view["seconds"],
        summary=view["summary"],
    )
    if consume:
        _store(conn).handed(stream_id)
        log.info("voice_stream.handed", stream_id=stream_id)
    return message


def summary(seconds: float, lang: str | None) -> str:
    """ "Voice message, 1 minute 12 seconds, in Telugu" (L-DRAFT.voice/4, `Ways` copy)."""
    total = round(seconds)
    minutes, secs = divmod(total, 60)
    parts = []
    if minutes:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if secs or not minutes:
        parts.append(f"{secs} second{'s' if secs != 1 else ''}")
    language = LANGUAGES.get(lang or "")
    return f"Voice message, {' '.join(parts)}" + (f", in {language}" if language else "")


# ---- ending streams nobody ends, and the sweep ------------------------------------------------------------


def reap(conn: Conn | None = None) -> int:
    """End every stream with no chunk for 20 seconds (the person left: J-RESUME/1 keeps what was heard) or past the
    3-minute clock. Runs every 2 seconds in the API process."""
    now = _clock()
    with _registry:
        due = [
            (live, "idle" if now - live.last_at >= IDLE_S else "limit")
            for live in _live.values()
            if not live.ending
            and (now - live.last_at >= IDLE_S or now - live.started >= max_seconds() + WALL_MARGIN_S)
        ]
    if not due:
        return 0
    own = conn is None
    c = conn or connect(autocommit=True)
    try:
        for live, why in due:
            try:
                end(c, live.id, idea_uuid=live.idea_uuid, by_code=live.by_code, ended_by=why)  # type: ignore[arg-type]
            except Exception as exc:  # one stream's trouble must not stop the rest
                log.warning("voice_stream.reap_failed", stream_id=live.id, error_type=type(exc).__name__)
    finally:
        if own:
            c.close()
    return len(due)


def _ensure_reaper() -> None:
    global _reaper
    if _reaper is not None and _reaper.is_alive():
        return

    def run() -> None:
        while True:
            time.sleep(2.0)
            try:
                reap()
            except Exception as exc:
                log.warning("voice_stream.reaper_failed", error_type=type(exc).__name__)

    _reaper = threading.Thread(target=run, name="voice-stream-reaper", daemon=True)
    _reaper.start()


def sweep(conn: Conn) -> int:
    """Every 15 minutes with `voice.sweep`: what is held past 24 hours is deleted; a stream left live by a restart
    is marked lost."""
    held, lost = _store(conn).sweep()
    if held or lost:
        log.info("voice_stream.swept", deleted_count=held, lost_count=lost)
    return held
