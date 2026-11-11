"""Voice notes in quick capture over HTTP against the running stack (DEC-096, BLD-C003, BLD-C005 to C010).

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
from tests import voice_files as f
from tests.web import Browser, people
from voice import service

pytestmark = pytest.mark.stack

CACHE_S = 10.5


def recording(words: str) -> bytes:
    """A valid 2-second WAV that SPEECH_MODE=fake hears as `words` (the probe reads the container first)."""
    return f.wav(2, words=words)


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
    return b.post(f"/api/submissions/{draft}/voice", files={"file": ("voice-note", data, "audio/wav")})


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
    assert audits(conn, voice_id) == [
        ("voice_note.recording_deleted", "voice_paused"),
        ("voice_note.deleted", "voice_paused"),
    ]


def test_a_small_file_that_claims_hours_fails_as_too_long_and_frees_its_place(setup: Any) -> None:
    """BLD-C005, BLD-C008: the probe refuses it before any decoding; a failed note is deleted at once and no longer
    counts towards the three waiting, and its screen still says why."""
    make, conn = setup
    b = make().browser()
    draft = quick_draft(b)
    first = send_when_on(b, draft, f.long_low_bitrate_wav(4000))
    done = settle(b, draft, first["id"])
    assert done == {"id": first["id"], "state": "failed", "failure": "too_long"}
    row = conn.execute(
        "SELECT store_key, deleted_at FROM voice_notes WHERE id = %s", (first["id"],)
    ).fetchone()
    assert row["store_key"] is None and row["deleted_at"] is not None
    assert ("voice_note.deleted", "too_long") in audits(conn, first["id"])
    for _ in range(2):  # two more fail the same way; three failures must not lock voice notes
        settle(b, draft, send(b, draft, f.webm_lasting(10 * 3600)).json()["id"])
    assert send(b, draft, recording("A real note after three failures.")).status_code == 201


def test_each_person_has_an_hourly_limit(setup: Any) -> None:
    """BLD-C005: a rules value (`voice.max_per_hour`, 10 by default), with its own reason code."""
    make, conn = setup
    person = make()
    b = person.browser()
    draft = quick_draft(b)
    send_when_on(b, draft, recording("The first note this hour."))
    for _ in range(service.limits().max_per_hour - 1):  # earlier notes this hour, already gone
        conn.execute(
            "INSERT INTO voice_notes (id, idea_uuid, uploaded_by_code, mime, bytes, state, failure, deleted_at) "
            "VALUES (gen_random_uuid(), %s, %s, 'audio/wav', 64, 'failed', 'nothing_heard', now())",
            (draft, person.contributor_code),
        )
    r = send(b, draft, recording("One too many."))
    assert r.status_code == 429 and r.json() == {"error": "too_many_this_hour"}


def test_an_idea_with_voice_notes_cannot_be_deleted_except_through_the_purge(setup: Any) -> None:
    """BLD-C006: the foreign key restricts; the draft purge deletes the recordings first, audited."""
    import psycopg

    from jobs.handlers import purge_drafts

    make, conn = setup
    b = make().browser()
    draft = quick_draft(b)
    note = send_when_on(b, draft, recording("Change of address forms are re-typed."))
    settle(b, draft, note["id"])
    with pytest.raises(psycopg.errors.ForeignKeyViolation), conn.transaction():
        conn.execute("DELETE FROM ideas WHERE id = %s", (draft,))
    conn.execute("UPDATE ideas SET draft_expires_at = now() - interval '1 minute' WHERE id = %s", (draft,))
    purge_drafts(conn, {})
    assert conn.execute("SELECT 1 FROM ideas WHERE id = %s", (draft,)).fetchone() is None
    assert conn.execute("SELECT 1 FROM voice_notes WHERE id = %s", (note["id"],)).fetchone() is None
    assert ("voice_note.deleted", "draft_purged") in audits(conn, note["id"])


def test_the_audit_names_who_deleted_a_note_by_contributor_code(setup: Any) -> None:
    make, conn = setup
    person = make()
    b = person.browser()
    draft = quick_draft(b)
    note = send_when_on(b, draft, recording("Statements reach investors late."))
    settle(b, draft, note["id"])
    assert b.request("DELETE", f"/api/submissions/{draft}/voice/{note['id']}").status_code == 204
    row = conn.execute(
        "SELECT after FROM audit_log WHERE entity = %s AND action = 'voice_note.deleted'",
        (f"voice_note:{note['id']}",),
    ).fetchone()
    assert row["after"] == {"reason_code": "deleted_by_person", "contributor_code": person.contributor_code}


def test_one_failing_note_does_not_stop_the_sweep(setup: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """BLD-C006: errors are counted per note and the rest are still deleted."""
    make, conn = setup
    b = make().browser()
    draft = quick_draft(b)
    ids = []
    for words in ("First held note.", "Second held note."):
        note = send_when_on(b, draft, recording(words))
        settle(b, draft, note["id"])
        ids.append(note["id"])
    conn.execute(
        "UPDATE voice_notes SET delete_after = now() - interval '1 minute' WHERE id = ANY(%s::uuid[])", (ids,)
    )
    real = service.remove

    def flaky(c: Any, voice_id: str, reason_code: str, by: str | None = None) -> bool:
        if voice_id == ids[0]:
            raise RuntimeError("store down for this one")
        return real(c, voice_id, reason_code, by)

    monkeypatch.setattr(service, "remove", flaky)
    assert service.sweep(conn) >= 1
    assert ("voice_note.deleted", "retention_24h") in audits(conn, ids[1])


def test_a_note_deleted_before_it_is_text_says_why(setup: Any) -> None:
    """BLD-C013: deleted mid-flight, it ends as failed with the reason, and the person's status says so."""
    make, conn = setup
    person = make()
    b = person.browser()
    draft = quick_draft(b)
    voice_id = "7a1e0c52-1d2e-4c3b-9a8f-0e1d2c3b4a60"
    conn.execute(  # still waiting to be heard (no job, so no race with the stack's worker)
        "INSERT INTO voice_notes (id, idea_uuid, uploaded_by_code, mime, bytes) VALUES (%s, %s, %s, 'audio/wav', 64)",
        (voice_id, draft, person.contributor_code),
    )
    assert b.request("DELETE", f"/api/submissions/{draft}/voice/{voice_id}").status_code == 204
    assert b.get(f"/api/submissions/{draft}/voice/{voice_id}").json() == {
        "id": voice_id,
        "state": "failed",
        "failure": "deleted_by_person",
    }


def test_a_store_failure_while_dropping_is_counted_and_audited(
    setup: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BLD-C013: the rows still go (the bucket rule and the sweep catch the object), and the audit says so."""
    make, conn = setup
    b = make().browser()
    draft = quick_draft(b)
    note = send_when_on(b, draft, recording("Dividend letters are posted twice."))
    settle(b, draft, note["id"])

    def store_down(c: Any, idea_uuid: str, reason_code: str) -> int:
        raise RuntimeError("store unreachable")

    monkeypatch.setattr(service, "purge_idea", store_down)
    service.drop_for_ideas(conn, [draft], "test_store_down")
    assert conn.execute("SELECT 1 FROM voice_notes WHERE id = %s", (note["id"],)).fetchone() is None
    row = conn.execute(
        "SELECT after FROM audit_log WHERE entity = %s AND action = 'voice_note.drop_incomplete'",
        (f"idea:{draft}",),
    ).fetchone()
    assert row["after"] == {"reason_code": "test_store_down", "left_to": "bucket_lifecycle_and_sweep"}
