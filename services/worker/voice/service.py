"""Voice notes in quick capture (DEC-096): accept a recording, turn it into text, hand the text back, delete it all.

1. Accept (`capture.voice` on, the idea still a draft): size and type by signature, at most a few waiting per
   draft and a few an hour per person (`rules/thresholds.md` `voice`). The recording goes to the quarantine bucket
   only; it is never moved to clean and no route opens it. No file name is kept.
2. Transcribe (job `voice.transcribe`): the virus scan first (non-negotiable 8), then the probe (`voice/probe.py`,
   a child process with a cleared environment and limits: allowed container and codec only, and the length read
   from the container's timestamps before anything decodes it, BLD-C005), then `gateway.speech`, then spoken
   numbers become digits (`voice.numbers`), then every value the level-1 patterns would block is left out of the
   text ("[PAN left out]"), so investor identifiers are never stored, even encrypted. The text is held encrypted
   (context `voice:<id>`) for the person to fetch, and the recording is deleted at once: nobody needs it after
   the text exists (stricter than DEC-096's "once shared or after 24 hours", BLD-C003).
3. The person's browser fetches the text, puts it in the box and deletes the held copy. Whatever is left goes
   when the idea is shared (`voice.purge`), when the draft is purged, or after 24 hours (`voice.sweep`).
4. A note that fails is deleted at once (recording and row marked deleted), so failures never hold up the next.
5. Nothing deletes an idea while it still has voice notes (the foreign key restricts it): every path that deletes
   ideas calls `drop_for_ideas` first, and the quarantine bucket's own rule expires `voice/` after a day as a
   backstop (BLD-C006).

Every deletion is audited with IDs and a reason code only. Nothing here logs the recording or its text.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from psycopg.types.json import Jsonb

from attachments import clamav, store
from core import isolated, killswitch
from core.config import get_settings
from core.crypto import decrypt_bytes, encrypt_bytes
from core.db import Conn
from core.logging import get_logger
from gateway import speech
from pii.patterns import scan
from rules import load_rule
from voice.numbers import normalise

log = get_logger("voice")

MAX_BYTES = 5 * 1024 * 1024  # 3 minutes of speech at 32 kbit/s is about 0.7 MB; room for other encoders
ACTOR = "process:voice-notes"
LIVE = ("quarantine", "transcribing", "ready")  # states that count as waiting
PROBE = Path(__file__).resolve().with_name("probe.py")
PROBE_MARGIN_S = 10  # container timestamps may run a little past the browser's 3-minute stop
STORE_BACKSTOP_S = 25 * 3600  # recordings older than this are deleted from the bucket whatever the rows say


@dataclass(frozen=True)
class Limits:
    max_waiting: int
    max_per_hour: int


def limits() -> Limits:
    """From `rules/thresholds.md` (`voice`); defaults while a company repo seeded before DEC-096 lacks them."""
    try:
        v = load_rule(Path(get_settings().company_repo_path), "thresholds").data.get("voice") or {}
    except Exception:  # an unreadable rules file must not stop voice notes from being limited
        v = {}
    return Limits(max_waiting=int(v.get("max_waiting", 3)), max_per_hour=int(v.get("max_per_hour", 10)))


# Codes worth retrying (the job runner backs off); every other failure is final and the person types instead.
RETRY = frozenset(
    {"hosted_unreachable", "hosted_429", "hosted_500", "hosted_502", "hosted_503", "hosted_504"}
    | {"engine_unreachable", "engine_not_ready", "engine_not_installed", "model_unavailable"}  # the service
)


class VoiceRefused(Exception):
    def __init__(self, status: int, code: str) -> None:
        super().__init__(code)
        self.status = status
        self.code = code


def sniff(data: bytes) -> str | None:
    """The recording's type by its first bytes: what browsers' MediaRecorder writes, plus WAV."""
    if data[:4] == b"\x1a\x45\xdf\xa3":
        return "audio/webm"
    if data[:4] == b"OggS":
        return "audio/ogg"
    if data[4:8] == b"ftyp":
        return "audio/mp4"
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "audio/wav"
    return None


def _key(voice_id: str) -> str:
    return f"voice/{voice_id}"


def accept(conn: Conn, *, idea_uuid: str, uploaded_by_code: str, data: bytes) -> dict[str, Any]:
    if not killswitch.is_on("capture.voice", conn):
        raise VoiceRefused(503, "voice_paused")
    if not data:
        raise VoiceRefused(400, "file_empty")
    if len(data) > MAX_BYTES:
        raise VoiceRefused(413, "file_too_large")
    mime = sniff(data)
    if mime is None:
        raise VoiceRefused(415, "type_not_allowed")
    with conn.transaction():
        idea = conn.execute(
            "SELECT stage, contributor_code FROM ideas WHERE id = %s FOR UPDATE", (idea_uuid,)
        ).fetchone()
        if idea is None or idea["contributor_code"] != uploaded_by_code:
            raise VoiceRefused(404, "not_found")
        if idea["stage"] != "draft":
            raise VoiceRefused(409, "not_a_draft")
        lim = limits()
        # One person's uploads count one at a time, whichever draft they go to: two at once cannot both slip
        # under the hourly limit (BLD-C013). Released when this transaction ends.
        conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"voice:{uploaded_by_code}",))
        this_hour = conn.execute(
            "SELECT count(*) AS n FROM voice_notes WHERE uploaded_by_code = %s AND created_at > now() - interval '1 hour'",
            (uploaded_by_code,),
        ).fetchone()
        if this_hour is not None and this_hour["n"] >= lim.max_per_hour:
            raise VoiceRefused(429, "too_many_this_hour")
        waiting = conn.execute(
            "SELECT count(*) AS n FROM voice_notes WHERE idea_uuid = %s AND deleted_at IS NULL AND state = ANY(%s)",
            (idea_uuid, list(LIVE)),
        ).fetchone()
        if waiting is not None and waiting["n"] >= lim.max_waiting:
            raise VoiceRefused(409, "too_many_waiting")
        voice_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO voice_notes (id, idea_uuid, uploaded_by_code, mime, bytes, store_key) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (voice_id, idea_uuid, uploaded_by_code, mime, len(data), _key(voice_id)),
        )
        store.put(
            get_settings().s3_bucket_quarantine, _key(voice_id), data
        )  # rolled back with the row if it fails
        conn.execute(
            "INSERT INTO jobs (type, payload, dedupe_key) VALUES ('voice.transcribe', %s, %s)",
            (Jsonb({"voice_note_id": voice_id}), f"voice:{voice_id}"),
        )
    log.info("voice.accepted", voice_id=voice_id, byte_count=len(data))
    return {"id": voice_id, "state": "quarantine"}


def leave_out_blocked(text: str) -> tuple[str, int]:
    """The text with every value the level-1 patterns block replaced by "[<label> left out]", and how many."""
    matches = sorted(
        (m for m in scan(text, kfin_domains=get_settings().kfin_domains) if m.action == "block"),
        key=lambda m: (m.start, -m.end),
    )
    kept: list[Any] = []
    for m in matches:  # drop overlaps, keeping the earliest, longest match
        if kept and m.start < kept[-1].end:
            continue
        kept.append(m)
    for m in reversed(kept):
        text = text[: m.start] + f"[{m.label} left out]" + text[m.end :]
    return text, len(kept)


def _drop_recording(conn: Conn, voice_id: str, store_key: str | None, reason_code: str) -> None:
    if store_key:
        store.delete(get_settings().s3_bucket_quarantine, store_key)
        conn.execute("UPDATE voice_notes SET store_key = NULL WHERE id = %s", (voice_id,))
        _audit(conn, voice_id, "voice_note.recording_deleted", reason_code)


def _audit(conn: Conn, voice_id: str, action: str, reason_code: str, by: str | None = None) -> None:
    after: dict[str, str] = {"reason_code": reason_code}
    if by:
        after["contributor_code"] = by  # an ID, never a name
    conn.execute(
        "INSERT INTO audit_log (actor, action, entity, after, reason) VALUES (%s, %s, %s, %s, %s)",
        (ACTOR, action, f"voice_note:{voice_id}", Jsonb(after), reason_code),
    )


def _fail(conn: Conn, row: dict[str, Any], code: str) -> str:
    """A note that cannot become text: the recording and anything held go now, and it stops counting as waiting
    (BLD-C008). The row keeps the state and the code, so the person's screen can say why."""
    voice_id = str(row["id"])
    with conn.transaction():
        live = conn.execute(
            "SELECT store_key, deleted_at FROM voice_notes WHERE id = %s FOR UPDATE", (voice_id,)
        ).fetchone()
        if live is None or live["deleted_at"] is not None:
            return "deleted"
        _drop_recording(conn, voice_id, live["store_key"], code)
        conn.execute(
            "UPDATE voice_notes SET state = 'failed', failure = %s, transcript_encrypted = NULL, deleted_at = now() "
            "WHERE id = %s",
            (code, voice_id),
        )
        _audit(conn, voice_id, "voice_note.deleted", code)
    log.info("voice.failed", voice_id=voice_id, reason_code=code)
    return "failed"


def _probe(data: bytes) -> str | None:
    """The container check in a limited child process (BLD-C005, BLD-C012). A refusal code, or None when it may be heard."""
    limit = get_settings().speech_max_seconds + PROBE_MARGIN_S
    try:
        answer = isolated.run(PROBE, [str(limit)], data, timeout_s=15, memory_mb=256, cpu_s=5)
    except isolated.IsolatedFailed:
        return "unreadable"
    if answer.get("ok") is True:
        return None
    code = str(answer.get("code") or "unreadable")
    return code if code in ("too_long", "codec_not_allowed", "type_not_allowed") else "unreadable"


def transcribe(conn: Conn, voice_id: str) -> str:
    """Run the checks and the speech route for one recording. Returns the final state. Raises
    `clamav.ScannerUnavailable` or `speech.SpeechUnavailable` (retryable codes only) for the runner to retry."""
    row = conn.execute(
        "SELECT id, mime, store_key, state, deleted_at FROM voice_notes WHERE id = %s", (voice_id,)
    ).fetchone()
    if row is None or row["deleted_at"] is not None or row["state"] not in ("quarantine", "transcribing"):
        return row["state"] if row else "missing"
    if not killswitch.is_on("capture.voice", conn):
        return _fail(conn, row, "voice_paused")  # paused: the recording goes, the person types instead
    if not row["store_key"]:
        return _fail(conn, row, "recording_missing")
    conn.execute("UPDATE voice_notes SET state = 'transcribing' WHERE id = %s", (voice_id,))
    data = store.get(get_settings().s3_bucket_quarantine, row["store_key"])
    try:
        scanned = clamav.scan_bytes(data)
    except clamav.ScannerUnavailable:
        conn.execute("UPDATE voice_notes SET state = 'quarantine' WHERE id = %s", (voice_id,))
        raise
    if not scanned.clean:
        return _fail(conn, row, "virus")
    refused = _probe(data)  # before anything decodes it
    if refused:
        return _fail(conn, row, refused)
    try:
        heard = speech.transcribe(data, row["mime"], conn)
    except speech.SpeechUnavailable as exc:
        if exc.code in RETRY:
            conn.execute("UPDATE voice_notes SET state = 'quarantine' WHERE id = %s", (voice_id,))
            raise
        return _fail(conn, row, exc.code)
    text, left_out = leave_out_blocked(normalise(heard.text))
    if not text.strip():
        return _fail(conn, row, "nothing_heard")
    with conn.transaction():
        live = conn.execute(
            "SELECT deleted_at FROM voice_notes WHERE id = %s FOR UPDATE", (voice_id,)
        ).fetchone()
        if live is None or live["deleted_at"] is not None:
            return "deleted"  # the person deleted it, or the draft went, while it was being heard
        conn.execute(
            "UPDATE voice_notes SET state = 'ready', transcript_encrypted = %s, removed_count = %s, language = %s "
            "WHERE id = %s",
            (
                encrypt_bytes(json.dumps({"text": text}).encode(), f"voice:{voice_id}"),
                left_out,
                (heard.language or "")[:16] or None,
                voice_id,
            ),
        )
        _drop_recording(conn, voice_id, row["store_key"], "transcribed")
    log.info("voice.ready", voice_id=voice_id, removed_count=left_out)
    return "ready"


def status(conn: Conn, voice_id: str, idea_uuid: str) -> dict[str, Any] | None:
    """The person's view of one recording (the web app checked they own the draft)."""
    row = conn.execute(
        "SELECT id, state, failure, transcript_encrypted, removed_count, deleted_at FROM voice_notes "
        "WHERE id = %s AND idea_uuid = %s",
        (voice_id, idea_uuid),
    ).fetchone()
    if row is None:
        return None
    if row["state"] == "failed":  # deleted at once, but the screen still says why
        return {"id": voice_id, "state": "failed", "failure": row["failure"]}
    if row["deleted_at"] is not None:
        return {"id": voice_id, "state": "deleted"}
    out: dict[str, Any] = {"id": voice_id, "state": row["state"]}
    if row["state"] == "ready" and row["transcript_encrypted"] is not None:
        held = json.loads(decrypt_bytes(bytes(row["transcript_encrypted"]), f"voice:{voice_id}"))
        out["transcript"] = held["text"]
        out["removed_count"] = row["removed_count"]
    return out


def remove(conn: Conn, voice_id: str, reason_code: str, by: str | None = None) -> bool:
    """Delete the recording (if still there) and the held text; the row stays as a tombstone for the audit."""
    with conn.transaction():
        row = conn.execute(
            "SELECT id, store_key, deleted_at FROM voice_notes WHERE id = %s FOR UPDATE", (voice_id,)
        ).fetchone()
        if row is None or row["deleted_at"] is not None:
            return False
        _drop_recording(conn, voice_id, row["store_key"], reason_code)
        # Deleted before it became text: it ends as failed with the reason (deleted_by_person, shared…), so the
        # person's screen can say why rather than show nothing (BLD-C013).
        conn.execute(
            "UPDATE voice_notes SET transcript_encrypted = NULL, deleted_at = now(), "
            "failure = CASE WHEN state IN ('ready', 'failed') THEN failure ELSE %s END, "
            "state = CASE WHEN state IN ('ready', 'failed') THEN state ELSE 'failed' END WHERE id = %s",
            (reason_code, voice_id),
        )
        _audit(conn, voice_id, "voice_note.deleted", reason_code, by)
    return True


def remove_for(conn: Conn, voice_id: str, idea_uuid: str, by: str | None = None) -> bool:
    """The person deletes one of their own (the web app checked they own the draft); the audit names their
    contributor code."""
    owned = conn.execute(
        "SELECT 1 FROM voice_notes WHERE id = %s AND idea_uuid = %s", (voice_id, idea_uuid)
    ).fetchone()
    return bool(owned) and remove(conn, voice_id, "deleted_by_person", by)


def purge_idea(conn: Conn, idea_uuid: str, reason_code: str) -> int:
    """Everything still held for one idea: on share (`shared`) or when its draft is purged (`draft_purged`)."""
    rows = conn.execute(
        "SELECT id FROM voice_notes WHERE idea_uuid = %s AND deleted_at IS NULL", (idea_uuid,)
    ).fetchall()
    return sum(remove(conn, str(r["id"]), reason_code) for r in rows)


def drop_for_ideas(conn: Conn, idea_uuids: list[str], reason_code: str) -> int:
    """Before any idea row is deleted (the foreign key restricts it, BLD-C006): each recording and held text goes
    (audited), then the rows. Used by the draft purge, the demo's removal and the test teardowns."""
    if not idea_uuids:
        return 0
    done = failed = 0
    for u in idea_uuids:
        try:
            done += purge_idea(conn, u, reason_code)
        except Exception:  # the store unreachable: the bucket's own rule and the sweep's backstop delete it
            failed += 1
            conn.execute(  # counted and audited, IDs only (BLD-C013)
                "INSERT INTO audit_log (actor, action, entity, after, reason) VALUES (%s, %s, %s, %s, %s)",
                (
                    ACTOR,
                    "voice_note.drop_incomplete",
                    f"idea:{u}",
                    Jsonb({"reason_code": reason_code, "left_to": "bucket_lifecycle_and_sweep"}),
                    reason_code,
                ),
            )
    conn.execute("DELETE FROM voice_notes WHERE idea_uuid = ANY(%s::uuid[])", (idea_uuids,))
    if failed:
        log.warning("voice.drop_incomplete", failed_count=failed)
    return done


def sweep(conn: Conn) -> int:
    """Every 15 minutes (`voice.sweep`): anything held past its 24 hours or for an idea that is no longer a draft;
    then, in the bucket itself, any `voice/` object older than 25 hours whatever the rows say. One failure is
    counted and the rest carry on."""
    rows = conn.execute(
        "SELECT v.id, (v.delete_after < now()) AS due FROM voice_notes v JOIN ideas i ON i.id = v.idea_uuid "
        "WHERE v.deleted_at IS NULL AND (v.delete_after < now() OR i.stage <> 'draft')"
    ).fetchall()
    done = failed = 0
    for r in rows:
        try:
            done += remove(conn, str(r["id"]), "retention_24h" if r["due"] else "shared")
        except Exception:  # one note's trouble (the store, a lock) must not stop the rest
            failed += 1
    try:
        orphans = store.delete_older(get_settings().s3_bucket_quarantine, "voice/", STORE_BACKSTOP_S)
    except Exception:
        orphans, failed = 0, failed + 1
    if done or failed or orphans:
        log.info("voice.swept", deleted_count=done, failed_count=failed, orphan_count=orphans)
    return done


def give_up(conn: Conn, voice_id: str) -> None:
    """The job kept failing (scanner or hosted route down): tell the person, delete the recording."""
    row = conn.execute(
        "SELECT id, store_key, deleted_at FROM voice_notes WHERE id = %s", (voice_id,)
    ).fetchone()
    if row is not None and row["deleted_at"] is None:
        _fail(conn, row, "retries_exhausted")
