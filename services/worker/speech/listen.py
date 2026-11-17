"""Listen to the whole idea, in Sarvam's voice (DEC-108 (4), L-LISTEN, C-LISTEN, J-REVIEW/2; BLD-C114).

- The script is lane B's: masked, in E-ENUMS.part order (`summary`, `often`, `who`, `cost`, `evidence`, `fix`), each
  part read as `spoken(title, text)` (`speech.adapters.listen_script`, until lane B's module lands).
- `speak` synthesises part by part with bulbul:v4-flash over streaming, a sentence a message, and yields MP3 as it
  arrives. Each part's length is computed from the audio that came back (MPEG frame headers counted, never
  estimated) and becomes the chapters: `{ parts: [{ part, start_s }], duration_s }` (L-LISTEN/1).
- Audio and chapters are cached together per (script version, voice): the object in the clean bucket under
  `listen/`, the row in `listen_cache`. A new version (an edit, an answer, a revised worth, L-LISTEN/3) replaces the
  idea's older ones. The script is masked, so nothing here holds a customer's detail.
- Prefetch: `enqueue_prefetch` when an idea is sent (job `listen.prefetch`), and every 15 minutes
  `listen.prefetch_due` for ideas with the desk that have no audio yet.
- If anything fails the player says "Couldn't prepare the audio. Try again." and the on-device voice stays the
  fallback (L-LISTEN/7, BLD-E010).

Logs carry IDs, counts and seconds only.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from psycopg.types.json import Jsonb

from attachments import store
from core import killswitch
from core.config import get_settings
from core.db import Conn
from core.logging import get_logger
from gateway import sarvam
from gateway.speech import SpeechUnavailable
from speech.adapters import (
    Script,
    ScriptRefused,
    ScriptUnavailable,
    listen_script,
    mask_for_service,
    spoken,
)

log = get_logger("listen")

PARTS = ("summary", "often", "who", "cost", "evidence", "fix")  # E-ENUMS.part, the player's order
LANG = "en-IN"
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
REF = re.compile(r"^IDEA-[0-9]{4}-[0-9]{6}$")
# Prefetched only once the checks are done and the sharer can no longer edit (BLD-C117).
DESK_STATUSES = ("with_review_desk", "needs_you")
# Nobody listens to these: a draft or one still being checked is the sharer's; a withdrawn idea is not found for anyone
# else (BLD-E011); a merged one is read as the idea it joined.
NOT_LISTENABLE = frozenset({"draft", "checking", "withdrawn", "merged"})
PREFETCH_BACKOFF = "6 hours"  # after a failed prefetch, the same script and voice wait this long (BLD-C117)


class ListenRefused(Exception):
    def __init__(self, status: int, code: str) -> None:
        super().__init__(code)
        self.status = status
        self.code = code


@dataclass(frozen=True)
class Cached:
    idea_uuid: str
    version: str
    voice: str
    store_key: str
    chapters: list[dict[str, Any]]
    duration_s: float
    byte_count: int

    def view(self) -> dict[str, Any]:
        return {"parts": self.chapters, "duration_s": self.duration_s}


@dataclass(frozen=True)
class Plan:
    idea_uuid: str
    script: Script
    voice: str
    cached: Cached | None


# ---- MP3 lengths, from the audio itself ---------------------------------------------------------------------

_BITRATES = {
    1: (0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320),  # MPEG-1 Layer III
    2: (0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160),  # MPEG-2 and 2.5 Layer III
}
_RATES = {3: (44100, 48000, 32000), 2: (22050, 24000, 16000), 0: (11025, 12000, 8000)}


def _syncsafe(four: bytes) -> int:
    return (four[0] & 0x7F) << 21 | (four[1] & 0x7F) << 14 | (four[2] & 0x7F) << 7 | (four[3] & 0x7F)


def mp3_seconds(data: bytes) -> float:
    """The length of MPEG Layer III audio, from its frame headers: frames x samples per frame / sample rate.
    ID3 tags are skipped. Raises ValueError when no frame is found (the length is never estimated)."""
    i, n, total = 0, len(data), 0.0
    frames = 0
    if data[:3] == b"ID3" and n >= 10:
        i = 10 + _syncsafe(data[6:10])
    while i + 4 <= n:
        b1, b2 = data[i + 1], data[i + 2]
        if data[i] != 0xFF or (b1 & 0xE0) != 0xE0:
            if data[i : i + 3] == b"ID3" and i + 10 <= n:  # a tag between segments
                i += 10 + _syncsafe(data[i + 6 : i + 10])
                continue
            i += 1
            continue
        version = (b1 >> 3) & 0x03  # 3 = MPEG-1, 2 = MPEG-2, 0 = MPEG-2.5
        layer = (b1 >> 1) & 0x03  # 1 = Layer III
        bitrate_index = (b2 >> 4) & 0x0F
        rate_index = (b2 >> 2) & 0x03
        if version == 1 or layer != 1 or bitrate_index in (0, 15) or rate_index == 3:
            i += 1
            continue
        rate = _RATES[version][rate_index]
        kbps = _BITRATES[1 if version == 3 else 2][bitrate_index]
        padding = (b2 >> 1) & 0x01
        samples = 1152 if version == 3 else 576
        length = (144 if version == 3 else 72) * kbps * 1000 // rate + padding
        if length < 4:
            i += 1
            continue
        frames += 1
        total += samples / rate
        i += length
    if frames == 0:
        raise ValueError("no_frames")
    return total


def strip_leading(data: bytes, *, final: bool = False) -> bytes | None:
    """A part's audio without its leading ID3 tag and its Xing, Info or VBRI header frame. Six parts become one
    stream, and a player reading the first part's header would take the whole file for that part's length. Returns
    None while more bytes are needed to decide (unless `final`)."""
    i = 0
    if data[:3] == b"ID3":
        if len(data) < 10:
            return data if final else None
        i = 10 + _syncsafe(data[6:10])
        if len(data) < i + 4:
            return data[i:] if final else None
    if len(data) < i + 4 or data[i] != 0xFF or (data[i + 1] & 0xE0) != 0xE0:
        return data[i:] if final or len(data) >= i + 4 else None
    b1, b2 = data[i + 1], data[i + 2]
    version, bitrate_index, rate_index = (b1 >> 3) & 0x03, (b2 >> 4) & 0x0F, (b2 >> 2) & 0x03
    if version == 1 or bitrate_index in (0, 15) or rate_index == 3:
        return data[i:]
    rate = _RATES[version][rate_index]
    kbps = _BITRATES[1 if version == 3 else 2][bitrate_index]
    length = (144 if version == 3 else 72) * kbps * 1000 // rate + ((b2 >> 1) & 0x01)
    if len(data) < i + length:
        return data[i:] if final else None
    frame = data[i : i + length]
    if any(tag in frame[:64] for tag in (b"Xing", b"Info", b"VBRI")):
        return data[i + length :]
    return data[i:]


# ---- the plan, the cache, the audio -------------------------------------------------------------------------


def _voice(voice: str | None = None) -> str:
    return voice or get_settings().sarvam_tts_speaker


def _idea_uuid(conn: Conn, ref: str) -> str:
    if UUID.match(ref):
        row = conn.execute("SELECT id, status FROM ideas WHERE id = %s", (ref,)).fetchone()
    elif REF.match(ref):
        row = conn.execute("SELECT id, status FROM ideas WHERE idea_id = %s", (ref,)).fetchone()
    else:
        row = None
    if row is None or row["status"] in NOT_LISTENABLE:
        raise ListenRefused(404, "not_found")
    return str(row["id"])


def cached(conn: Conn, idea_uuid: str, version: str, voice: str) -> Cached | None:
    row = conn.execute(
        "SELECT store_key, chapters, duration_s, byte_count FROM listen_cache "
        "WHERE idea_uuid = %s AND version = %s AND voice = %s",
        (idea_uuid, version, voice),
    ).fetchone()
    if row is None:
        return None
    return Cached(
        idea_uuid,
        version,
        voice,
        str(row["store_key"]),
        list(row["chapters"]),
        float(row["duration_s"]),
        int(row["byte_count"]),
    )


def prepare(conn: Conn, ref: str, *, voice: str | None = None) -> Plan:
    """The idea, its masked script and any cached audio. Raises ListenRefused 404 (a draft or missing idea) or
    503 (`script_unavailable`, `paused`)."""
    if not killswitch.is_on("desk.listen", conn):
        raise ListenRefused(503, "paused")
    idea_uuid = _idea_uuid(conn, ref)
    try:
        script = listen_script(conn, idea_uuid)
    except ScriptRefused:
        raise ListenRefused(404, "not_found") from None
    except ScriptUnavailable:
        raise ListenRefused(503, "script_unavailable") from None
    v = _voice(voice)
    return Plan(idea_uuid, script, v, cached(conn, idea_uuid, script.version, v))


def _ordered(script: Script) -> list[Any]:
    rank = {p: i for i, p in enumerate(PARTS)}
    return sorted(script.parts, key=lambda p: rank.get(p.part, len(PARTS)))


def outgoing(masked_script: Script) -> list[tuple[str, str]]:
    """Each part's text as it will go to Sarvam, in order, every one checked before anything is sent: a refusal at
    part 6 must not have paid for parts 1 to 5 (BLD-C117). Raises SarvamFailed `unmasked_text`."""
    texts = [(part.part, mask_for_service(spoken(part.title, part.text))) for part in _ordered(masked_script)]
    for _part, text in texts:
        sarvam.check_masked(text)
    return texts


def speak(
    conn: Conn, idea_uuid: str, masked_script: Script, *, lang: str = LANG, voice: str | None = None
) -> Iterator[bytes]:
    """Yield the idea's audio (MP3), part by part in E-ENUMS.part order, as Sarvam makes it. When every part is
    done, the audio and the chapters (each part's real length) are cached for (script version, voice)."""
    v = _voice(voice)
    hit = cached(conn, idea_uuid, masked_script.version, v)
    if hit is not None:
        yield store.get(get_settings().s3_bucket_clean, hit.store_key)
        return
    texts = outgoing(masked_script)
    # One synthesis per (idea, version, voice): a first listen and a prefetch, or two first listens, wait for each
    # other and the second is served from the cache (BLD-C117).
    key = f"listen:{idea_uuid}:{masked_script.version}:{v}"
    conn.execute("SELECT pg_advisory_lock(hashtext(%s))", (key,))
    try:
        hit = cached(conn, idea_uuid, masked_script.version, v)
        if hit is not None:
            yield store.get(get_settings().s3_bucket_clean, hit.store_key)
            return
        yield from _synthesise(conn, idea_uuid, masked_script.version, texts, lang, v)
    finally:
        conn.execute("SELECT pg_advisory_unlock(hashtext(%s))", (key,))


def _synthesise(
    conn: Conn, idea_uuid: str, version: str, texts: list[tuple[str, str]], lang: str, v: str
) -> Iterator[bytes]:
    audio = bytearray()
    chapters: list[dict[str, Any]] = []
    at = 0.0
    for part_name, text in texts:
        made = bytearray()
        head: bytearray | None = (
            bytearray()
        )  # the part's first bytes, until its leading tag and header are gone
        for chunk in sarvam.tts(text, lang=lang, speaker=v, conn=conn, ref_id=f"idea:{idea_uuid}"):
            if head is not None:
                head += chunk
                clean = strip_leading(bytes(head))
                if clean is None:
                    continue
                chunk, head = clean, None
            made += chunk
            yield chunk
        if head:  # a part shorter than its header check: what is left is the audio
            tail = strip_leading(bytes(head), final=True) or b""
            made += tail
            yield tail
        seconds = mp3_seconds(bytes(made))
        chapters.append({"part": part_name, "start_s": round(at, 2)})
        at += seconds
        audio += made
    _store(conn, idea_uuid, version, v, lang, bytes(audio), chapters, round(at, 2))


def _store(
    conn: Conn,
    idea_uuid: str,
    version: str,
    voice: str,
    lang: str,
    audio: bytes,
    chapters: list[dict[str, Any]],
    duration_s: float,
) -> None:
    bucket = get_settings().s3_bucket_clean
    key = f"listen/{idea_uuid}/{version}-{voice}.mp3"
    store.put(bucket, key, audio)
    old = conn.execute(
        "DELETE FROM listen_cache WHERE idea_uuid = %s AND NOT (version = %s AND voice = %s) RETURNING store_key",
        (idea_uuid, version, voice),
    ).fetchall()
    conn.execute(
        "INSERT INTO listen_cache (idea_uuid, version, voice, lang, store_key, chapters, duration_s, byte_count) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (idea_uuid, version, voice) DO UPDATE SET "
        "store_key = EXCLUDED.store_key, chapters = EXCLUDED.chapters, duration_s = EXCLUDED.duration_s, "
        "byte_count = EXCLUDED.byte_count, created_at = now()",
        (idea_uuid, version, voice, lang, key, Jsonb(chapters), duration_s, len(audio)),
    )
    for r in old:  # L-LISTEN/3: the audio of an older script goes
        try:
            store.delete(bucket, str(r["store_key"]))
        except Exception as exc:  # the sweep's 30-day backstop deletes it
            log.warning("listen.old_audio_kept", error_type=type(exc).__name__)
    log.info(
        "listen.cached",
        idea_uuid=idea_uuid,
        part_count=len(chapters),
        speech_seconds=duration_s,
        byte_count=len(audio),
    )


def chapters(conn: Conn, ref: str) -> dict[str, Any] | None:
    """The chapters once the audio is cached, else None (and a prefetch is queued)."""
    plan = prepare(conn, ref)
    if plan.cached is not None:
        return plan.cached.view()
    enqueue_prefetch(conn, plan.idea_uuid)
    return None


def enqueue_prefetch(conn: Conn, idea_uuid: str) -> None:
    """Make the audio before anyone asks: call when an idea is sent (lane C's submit), and from `chapters`."""
    conn.execute(
        "INSERT INTO jobs (type, payload, dedupe_key) VALUES ('listen.prefetch', %s, %s) "
        "ON CONFLICT (dedupe_key) WHERE dedupe_key IS NOT NULL AND state IN ('queued', 'running') DO NOTHING",
        (Jsonb({"idea_uuid": idea_uuid}), f"listen:{idea_uuid}"),
    )


def prefetch(conn: Conn, idea_uuid: str) -> bool:
    """Job `listen.prefetch`: make and cache the audio unless it is cached, paused, not possible yet, or failed for
    this script and voice in the last 6 hours (a failure is remembered, so nothing is billed again every 15
    minutes)."""
    if not killswitch.is_on("desk.listen", conn) or not killswitch.is_on("speech.hosted", conn):
        return False
    try:
        if get_settings().speech_mode == "sarvam":
            sarvam.allowed(conn)  # the approval, speech.hosted read fresh, and the key
        plan = prepare(conn, idea_uuid)
    except (ListenRefused, SpeechUnavailable):
        return False
    if plan.cached is not None or _failed_recently(conn, plan):
        return False
    try:
        for _ in speak(conn, plan.idea_uuid, plan.script, voice=plan.voice):
            pass
    except (SpeechUnavailable, ValueError) as exc:
        code = exc.code if isinstance(exc, SpeechUnavailable) else "audio_unreadable"
        conn.execute(
            "INSERT INTO listen_failures (idea_uuid, version, voice, error_code) VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (idea_uuid, version, voice) DO UPDATE SET error_code = EXCLUDED.error_code, "
            "failed_at = now(), attempts = listen_failures.attempts + 1",
            (plan.idea_uuid, plan.script.version, plan.voice, code[:60]),
        )
        log.info("listen.prefetch_failed", idea_uuid=plan.idea_uuid, reason_code=code)
        return False
    return True


def _failed_recently(conn: Conn, plan: Plan) -> bool:
    row = conn.execute(
        "SELECT 1 FROM listen_failures WHERE idea_uuid = %s AND version = %s AND voice = %s "
        "AND failed_at > now() - %s::interval",
        (plan.idea_uuid, plan.script.version, plan.voice, PREFETCH_BACKOFF),
    ).fetchone()
    return row is not None


def prefetch_due(conn: Conn, limit: int = 20) -> int:
    """Every 15 minutes: queue a prefetch for ideas with the desk that have no audio for any version yet."""
    rows = conn.execute(
        "SELECT i.id FROM ideas i WHERE i.status = ANY(%s) "
        "AND coalesce(i.status_changed_at, i.updated_at) > now() - interval '7 days' "
        "AND NOT EXISTS (SELECT 1 FROM listen_cache c WHERE c.idea_uuid = i.id) "
        "AND NOT EXISTS (SELECT 1 FROM listen_failures f WHERE f.idea_uuid = i.id "
        "AND f.failed_at > now() - interval '6 hours') "
        "ORDER BY coalesce(i.status_changed_at, i.updated_at) DESC LIMIT %s",
        (list(DESK_STATUSES), limit),
    ).fetchall()
    for r in rows:
        enqueue_prefetch(conn, str(r["id"]))
    return len(rows)


def sweep(conn: Conn) -> int:
    """Audio older than 30 days goes (L-LISTEN/5's window), from the bucket and the cache."""
    rows = conn.execute(
        "DELETE FROM listen_cache WHERE created_at < now() - interval '30 days' RETURNING store_key"
    ).fetchall()
    for r in rows:
        try:
            store.delete(get_settings().s3_bucket_clean, str(r["store_key"]))
        except Exception as exc:
            log.warning("listen.sweep_delete_failed", error_type=type(exc).__name__)
    return len(rows)


def byte_range(header: str, size: int) -> tuple[int, int] | None:
    """`Range: bytes=a-b` for the cached audio (seeking by chapter); None when absent or not satisfiable."""
    m = re.fullmatch(r"bytes=(\d*)-(\d*)", header.strip())
    if not m or (not m.group(1) and not m.group(2)):
        return None
    if m.group(1):
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else size - 1
    else:
        start, end = max(0, size - int(m.group(2))), size - 1
    if start >= size or start > end:
        return None
    return start, min(end, size - 1)
