"""Voice notes in quick capture over HTTP against the running stack (DEC-096, BLD-C003).

A recording is accepted only while `capture.voice` is on; the worker scans it, hears it (SPEECH_MODE=fake reads
the text a synthetic recording carries), joins spoken numbers, leaves out blocked values, holds the text
encrypted and deletes the recording at once. Only the owner sees the text; deleting it, sharing the idea or 24
hours removes what is held, each deletion audited with IDs only. Every switch is put back as it was found.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from typing import Any

import generators as g
import pytest

from attachments import store
from core import killswitch
from core.config import get_settings
from core.db import connect
from gateway.speech import FAKE_MARKER
from tests.web import Browser, people
from voice import service

pytestmark = pytest.mark.stack

WEBM = b"\x1a\x45\xdf\xa3" + bytes(32)
CACHE_S = 10.5


def recording(words: str) -> bytes:
    return WEBM + FAKE_MARKER + words.encode() + b"\0" + bytes(64)


def soon(check: Callable[[], bool], timeout: float = CACHE_S + 2) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return True
        time.sleep(0.5)
    return False


@pytest.fixture
def setup() -> Iterator[Any]:
    with connect(autocommit=True) as conn, people(conn) as make:
        before = killswitch.states(conn).get("capture.voice", "off")
        killswitch.set_switch(conn, "capture.voice", "on", reason="test: voice notes on", actor="test")
        killswitch.clear_cache()
        try:
            yield make, conn
        finally:
            killswitch.set_switch(
                conn, "capture.voice", before, reason="test: put back as found", actor="test"
            )
            killswitch.clear_cache()


def quick_draft(b: Browser) -> str:
    r = b.post("/api/submissions", json={"mode": "quick"})
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


def send(b: Browser, draft: str, data: bytes) -> Any:
    return b.post(f"/api/submissions/{draft}/voice", files={"file": ("voice-note", data, "audio/webm")})


def send_when_on(b: Browser, draft: str, data: bytes) -> dict[str, Any]:
    """The web app and worker read switches through a 10-second cache: wait for both to see it on."""
    out: dict[str, Any] = {}

    def attempt() -> bool:
        r = send(b, draft, data)
        out["r"] = r
        return r.status_code != 503

    assert soon(attempt), out["r"].text
    assert out["r"].status_code == 201, out["r"].text
    return dict(out["r"].json())


def settle(b: Browser, draft: str, voice_id: str, timeout: float = 90.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while True:
        r = b.get(f"/api/submissions/{draft}/voice/{voice_id}")
        assert r.status_code == 200, r.text
        body: dict[str, Any] = r.json()
        if body["state"] not in ("quarantine", "transcribing"):
            return body
        assert time.monotonic() < deadline, f"{voice_id} still {body['state']}"
        time.sleep(0.5)


def audits(conn: Any, voice_id: str) -> list[tuple[str, str]]:
    rows = conn.execute(
        "SELECT action, reason FROM audit_log WHERE entity = %s ORDER BY id", (f"voice_note:{voice_id}",)
    ).fetchall()
    return [(r["action"], r["reason"]) for r in rows]


def test_a_voice_note_becomes_text_and_the_recording_goes(setup: Any) -> None:
    make, conn = setup
    b = make().browser()
    draft = quick_draft(b)
    pan = g.pan(g.default_rng(21))
    spoken_pan = " ".join(
        ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"][int(c)]
        if c.isdigit()
        else c
        for c in pan
    )
    note = send_when_on(b, draft, recording(f"Forms are typed twice. The PAN was {spoken_pan} on the slip."))
    done = settle(b, draft, note["id"])
    assert done["state"] == "ready", done
    assert done["transcript"].startswith("Forms are typed twice.")
    assert "[PAN left out]" in done["transcript"] and pan not in done["transcript"]
    assert done["removed_count"] == 1

    # The recording is gone the moment it is text; only the encrypted text is held.
    row = conn.execute(
        "SELECT store_key, transcript_encrypted FROM voice_notes WHERE id = %s", (note["id"],)
    ).fetchone()
    assert row["store_key"] is None and row["transcript_encrypted"] is not None
    assert not store.exists(get_settings().s3_bucket_quarantine, f"voice/{note['id']}")
    assert not store.exists(get_settings().s3_bucket_clean, f"voice/{note['id']}")

    # The browser takes the text, then deletes the held copy.
    assert b.request("DELETE", f"/api/submissions/{draft}/voice/{note['id']}").status_code == 204
    assert b.get(f"/api/submissions/{draft}/voice/{note['id']}").json() == {
        "id": note["id"],
        "state": "deleted",
    }
    held = conn.execute(
        "SELECT transcript_encrypted FROM voice_notes WHERE id = %s", (note["id"],)
    ).fetchone()
    assert held["transcript_encrypted"] is None
    assert audits(conn, note["id"]) == [
        ("voice_note.recording_deleted", "transcribed"),
        ("voice_note.deleted", "deleted_by_person"),
    ]


def test_only_the_owner_sees_or_deletes_a_note(setup: Any) -> None:
    make, _conn = setup
    owner, other = make().browser(), make().browser()
    draft = quick_draft(owner)
    note = send_when_on(owner, draft, recording("Statements reach investors a week late."))
    settle(owner, draft, note["id"])
    assert other.get(f"/api/submissions/{draft}/voice/{note['id']}").status_code == 404
    assert other.request("DELETE", f"/api/submissions/{draft}/voice/{note['id']}").status_code == 404
    assert send(other, draft, recording("Not my draft.")).status_code == 404
    assert owner.get(f"/api/submissions/{draft}/voice/{note['id']}").json()["state"] == "ready"


def test_wrong_types_and_too_many_waiting_are_refused(setup: Any) -> None:
    make, _conn = setup
    b = make().browser()
    draft = quick_draft(b)
    send_when_on(b, draft, recording("First note about cheque slips."))
    assert send(b, draft, b"%PDF-1.7" + bytes(64)).json() == {"error": "type_not_allowed"}
    send(b, draft, recording("Second note."))
    send(b, draft, recording("Third note."))
    r = send(b, draft, recording("Fourth note."))
    assert r.status_code == 409 and r.json() == {"error": "too_many_waiting"}


def test_sharing_the_idea_deletes_what_is_held(setup: Any) -> None:
    make, conn = setup
    b = make().browser()
    draft = quick_draft(b)
    note = send_when_on(b, draft, recording("Change of bank requests wait two days for a signature check."))
    settle(b, draft, note["id"])
    every = {"no_personal_data": True, "own_work_or_credited": True, "ip_terms": True}
    details = "Change of bank requests wait two days for a signature check at the branch counter."
    r = b.post(
        f"/api/submissions/{draft}/submit", json={"canvas": {"details": details, "declarations": every}}
    )
    assert r.status_code == 202, r.text
    assert soon(
        lambda: (
            conn.execute("SELECT deleted_at FROM voice_notes WHERE id = %s", (note["id"],)).fetchone()[
                "deleted_at"
            ]
            is not None
        ),
        timeout=30,
    )
    assert ("voice_note.deleted", "shared") in audits(conn, note["id"])


def test_after_24_hours_the_sweep_deletes_it(setup: Any) -> None:
    make, conn = setup
    b = make().browser()
    draft = quick_draft(b)
    note = send_when_on(b, draft, recording("NAV files are re-sent by courier every Friday."))
    settle(b, draft, note["id"])
    conn.execute(
        "UPDATE voice_notes SET delete_after = now() - interval '1 minute' WHERE id = %s", (note["id"],)
    )
    service.sweep(conn)
    assert ("voice_note.deleted", "retention_24h") in audits(conn, note["id"])
    assert b.get(f"/api/submissions/{draft}/voice/{note['id']}").json()["state"] == "deleted"


def test_with_capture_voice_off_new_notes_are_refused_and_waiting_ones_are_deleted(setup: Any) -> None:
    make, conn = setup
    b = make().browser()
    draft = quick_draft(b)
    send_when_on(b, draft, recording("Warm-up note."))
    killswitch.set_switch(conn, "capture.voice", "off", reason="test: voice notes paused", actor="test")
    killswitch.clear_cache()
    assert soon(lambda: send(b, draft, recording("Paused.")).status_code == 503)
    # A recording that arrives while paused is never heard: the worker deletes it (in-process, no race with the
    # stack's worker: the row is written without a job).
    voice_id = "5f0c7a52-1d2e-4c3b-9a8f-0e1d2c3b4a59"
    conn.execute(
        "INSERT INTO voice_notes (id, idea_uuid, uploaded_by_code, mime, bytes, store_key) "
        "SELECT %s, id, contributor_code, 'audio/webm', 64, %s FROM ideas WHERE id = %s",
        (voice_id, f"voice/{voice_id}", draft),
    )
    store.put(get_settings().s3_bucket_quarantine, f"voice/{voice_id}", recording("Never heard."))
    assert service.transcribe(conn, voice_id) == "failed"
    assert not store.exists(get_settings().s3_bucket_quarantine, f"voice/{voice_id}")
    assert audits(conn, voice_id) == [("voice_note.recording_deleted", "voice_paused")]
