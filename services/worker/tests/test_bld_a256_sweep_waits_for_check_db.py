"""BLD-A256 (L-HIDE.files, L-CONVO/7; the product lead's DEC-143 (e)): the hourly sweep of unsent conversation files
(`files.sweep`, `sweep_failed_copies`, BLD-C242) never takes a file still being checked, and counts the file's day
from its last change, not from when it was added. A message can carry only a checked file (`convo.messages`
`_check_files`), and while the assistant is off every file check waits for the gatekeeper in `checking`, so on r6 a
file added on Friday went on Saturday with its queued check, before it could ever be sent.

Against a migrated test database (a stack test by BLD-A251: CI only), with lane C's helpers: the object store faked
as in `test_1pc_c_convo_files_db.py`, and the virus scan, the sandbox's text layer and the file gatekeeper stood in
as in `test_c225_file_wait_db.py`. Rows are aged in their INSERT, never by an UPDATE: the `attachments_updated_at`
trigger sets `updated_at` on every UPDATE. Each case has a finished worker start sweep in place. Synthetic people,
files and values only (non-negotiable 11); the audit carries IDs only (non-negotiable 3)."""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from psycopg.types.json import Jsonb

from attachments import clamav, store
from attachments import files as F
from attachments.extract import Extracted
from convo.messages import send
from core import killswitch
from core.config import get_settings
from core.db import Conn
from hide import detect
from jobs import handlers  # noqa: F401 (registers the job types)
from jobs.runner import run_one
from tests import desk_fixtures as f
from tests import files as make
from tests.desk_fixtures import clean_up_desk_rows  # noqa: F401 (autouse: removes the people and ideas)

WORDS = "Investors call the branch about 40 times a day because the SMS only says R07."
WORKER = "test-a256"


# ---- lane C's helpers (test_1pc_c_convo_files_db.py, test_c225_file_wait_db.py) -----------------------------------


@pytest.fixture
def objects(monkeypatch: pytest.MonkeyPatch) -> dict[tuple[str, str], bytes]:
    """The object store as a dict: nothing here needs MinIO."""
    kept: dict[tuple[str, str], bytes] = {}
    monkeypatch.setattr(store, "put", lambda bucket, key, data: kept.__setitem__((bucket, key), data))
    monkeypatch.setattr(store, "delete", lambda bucket, key: kept.pop((bucket, key), None))
    monkeypatch.setattr(store, "exists", lambda bucket, key: (bucket, key) in kept)
    monkeypatch.setattr(store, "get", lambda bucket, key: kept[(bucket, key)])
    return kept


@pytest.fixture
def cast(db: Conn, company_repo: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    """Kavya shares an idea; Meera is the review desk."""
    monkeypatch.setenv("COMPANY_REPO_PATH", str(company_repo))
    get_settings.cache_clear()
    kavya = f.person(db, "Kavya Menon")
    out = {
        "kavya": kavya,
        "meera": f.person(db, "Meera Iyer", roles=("reviewer",)),
        "idea": f.idea(db, kavya),
    }
    yield out
    db.execute(
        "DELETE FROM jobs WHERE type = %s AND payload->>'attachment_id' IN (SELECT id FROM attachments "
        "WHERE idea_uuid = %s)",
        (F.JOB, out["idea"]["id"]),
    )
    get_settings.cache_clear()


def _one(db: Conn, sql: str, *args: Any) -> dict[str, Any]:
    row = db.execute(sql, args).fetchone()
    assert row is not None
    return dict(row)


def _row(
    db: Conn, idea: dict[str, Any], by: dict[str, str], *, state: str = "checked", hours_ago: float = 0,
    changed_hours_ago: float | None = None, checks: dict[str, Any] | None = None,
) -> str:  # fmt: skip
    """A conversation file on no entry, as the routes leave it, written directly (its copy is a key in the faked
    store). Added `hours_ago` and last changed `changed_hours_ago` (the same when not given), both in the INSERT."""
    changed = hours_ago if changed_hours_ago is None else changed_hours_ago
    att = F._next_id(db)
    db.execute(
        "INSERT INTO attachments (id, idea_uuid, uploaded_by_code, uploaded_by_user, name, mime, bytes, store_key, "
        "state, kind, file_state, checks, purpose, created_at, updated_at) "
        "VALUES (%s, %s, %s, %s, 'notes.pdf', 'application/pdf', 1200, %s, %s, 'file', %s, %s, 'conversation', "
        "now() - make_interval(secs => %s), now() - make_interval(secs => %s))",
        (att, idea["id"], by["code"], by["id"], f"files/{att}-{uuid.uuid4().hex}",
         "clean" if state == "checked" else "quarantine", state, Jsonb(checks or {"type": "pdf"}),
         hours_ago * 3600, changed * 3600),
    )  # fmt: skip
    return att


def _copy(db: Conn, objects: dict[Any, bytes], att: str, *buckets: str) -> str:
    """The file's copy in the faked buckets named (the clean one when none is), so a sweep has copies to delete."""
    key = str(_one(db, "SELECT store_key FROM attachments WHERE id = %s", att)["store_key"])
    for bucket in buckets or (get_settings().s3_bucket_clean,):
        objects[(bucket, key)] = b"%PDF-1.4 synthetic"
    return key


def _start_swept(db: Conn) -> None:
    """A worker start sweep that finished: the attachments sweep deletes nothing until one has (BLD-C242)."""
    db.execute(
        "INSERT INTO audit_log (actor, action, entity, after) VALUES "
        "('system:files', 'file.start_sweep', 'files:start_sweep', '{\"count\": 0, \"complete\": true}'::jsonb)"
    )


def _left(db: Conn, idea: dict[str, Any]) -> set[str]:
    return {r["id"] for r in db.execute("SELECT id FROM attachments WHERE idea_uuid = %s", (idea["id"],))}


def _swept(db: Conn, idea: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    rows = db.execute(
        "SELECT actor, after FROM audit_log WHERE entity = %s AND action = 'file.swept' ORDER BY id",
        (f"idea:{idea['id']}",),
    ).fetchall()
    return [(r["actor"], r["after"]) for r in rows]


def _job(db: Conn, att: str) -> dict[str, Any]:
    """The file's newest check job, with whether it is due."""
    return _one(
        db,
        "SELECT state, attempts, last_error, run_at <= now() AS due FROM jobs "
        "WHERE type = %s AND payload->>'attachment_id' = %s ORDER BY id DESC LIMIT 1",
        F.JOB, att,
    )  # fmt: skip


def _run(db: Conn, att: str) -> None:
    """Put this file's queued check job first in the queue, so `run_one` runs it."""
    db.execute(
        "UPDATE jobs SET run_at = '2000-01-01' WHERE type = %s AND state = 'queued' AND payload->>'attachment_id' = %s",
        (F.JOB, att),
    )
    assert run_one(db, WORKER)


def _switch(db: Conn, state: str, *names: str) -> None:
    """Flip switches straight in the table, as the Admin page does."""
    db.execute(
        "UPDATE kill_switches SET state = %s WHERE name = ANY(%s)",
        (state, list(names or ("ai.all", "agent.gatekeeper"))),
    )
    killswitch.clear_cache()


@pytest.fixture
def stood_in(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """A clean virus scan that counts its calls, the sandbox's text layer and the file gatekeeper with nothing found:
    the check's own steps without the stack's services. Returns the scans."""
    scans: list[int] = []

    def scan(data: bytes, timeout: float = 60.0) -> clamav.ScanResult:
        scans.append(len(data))
        return clamav.ScanResult(True, None)

    monkeypatch.setattr(F.clamav, "scan_bytes", scan)
    monkeypatch.setattr(
        F, "_extract", lambda kind, data, types: Extracted(pieces=[("page 1", WORDS)], pages=1, kind="pdf")
    )
    monkeypatch.setattr(F.hide_files, "gate_for", lambda conn, idea_uuid, text: detect.Gate([]))
    return scans


# ---- the cases -----------------------------------------------------------------------------------------------------


def test_bld_a256_l_hide_files_a_conversation_file_still_checking_is_never_swept(
    db: Conn, cast: dict[str, Any], objects: dict[Any, bytes]
) -> None:
    """(a) Waiting for the gatekeeper, added and last changed 72 hours ago, with its queued check: the sweep takes
    nothing, and the row, its stored copy and its queued job all stay. On r6 it went, job and all."""
    idea, meera = cast["idea"], cast["meera"]
    s = get_settings()
    att = _row(
        db, idea, meera, state="checking", hours_ago=72, checks={"type": "pdf", "waiting_for": F.GATEKEEPER}
    )
    key = _copy(db, objects, att, s.s3_bucket_quarantine)
    db.execute(
        "INSERT INTO jobs (type, payload, dedupe_key, last_error, run_at) "
        "VALUES (%s, %s, %s, %s, now() + make_interval(secs => %s))",
        (F.JOB, Jsonb({"attachment_id": att}), f"{F.JOB}:{att}", F.WAITING_GATEKEEPER, F.WAIT_STEP_S),
    )
    _start_swept(db)
    assert F.sweep_failed_copies(db) == 0
    row = _one(
        db,
        "SELECT file_state, checks->>'waiting_for' AS waiting_for, created_at < now() - interval '71 hours' AS added, "
        "updated_at < now() - interval '71 hours' AS changed FROM attachments WHERE id = %s",
        att,
    )  # fmt: skip
    assert row == {"file_state": "checking", "waiting_for": F.GATEKEEPER, "added": True, "changed": True}
    assert (s.s3_bucket_quarantine, key) in objects
    job = _job(db, att)
    assert (job["state"], job["attempts"], job["last_error"]) == ("queued", 0, F.WAITING_GATEKEEPER)
    assert _swept(db, idea) == []


def test_bld_a256_l_hide_files_a_checked_conversation_file_gets_a_day_from_the_end_of_its_check(
    db: Conn, cast: dict[str, Any], objects: dict[Any, bytes]
) -> None:
    """(b) Added 72 hours ago, its check ended 2 hours ago (`updated_at`): it stays, copy and all. On r6 it went
    within the hour of its check ending, before the person could send it."""
    idea, meera = cast["idea"], cast["meera"]
    s = get_settings()
    att = _row(db, idea, meera, hours_ago=72, changed_hours_ago=2)
    key = _copy(db, objects, att)
    _start_swept(db)
    assert F.sweep_failed_copies(db) == 0
    assert _left(db, idea) == {att}
    assert (s.s3_bucket_clean, key) in objects
    assert _swept(db, idea) == []


def test_bld_a256_l_hide_files_a_checked_conversation_file_unsent_a_day_after_its_check_is_swept(
    db: Conn, cast: dict[str, Any], objects: dict[Any, bytes]
) -> None:
    """(c) Added 72 hours ago, its check ended 25 hours ago: swept, its row and every stored copy, with one
    `file.swept` audit row that carries IDs only."""
    idea, meera = cast["idea"], cast["meera"]
    s = get_settings()
    att = _row(db, idea, meera, hours_ago=72, changed_hours_ago=25)
    key = _copy(db, objects, att, s.s3_bucket_clean, s.s3_bucket_quarantine)
    _start_swept(db)
    assert F.sweep_failed_copies(db) == 1
    assert _left(db, idea) == set()
    assert (s.s3_bucket_clean, key) not in objects and (s.s3_bucket_quarantine, key) not in objects
    assert _swept(db, idea) == [("system:files", {"file_id": att, "purpose": "conversation"})]
    assert F.sweep_failed_copies(db) == 0


def test_bld_a256_l_hide_files_a_failed_conversation_file_goes_in_one_sweep_with_its_copy(
    db: Conn, cast: dict[str, Any], objects: dict[Any, bytes]
) -> None:
    """(d) "Didn't upload", its check ended 25 hours ago (`checks.ended_at` and `updated_at`), its quarantine copy
    kept for Try again: ONE sweep removes its row and its copy, and counts it once. The conversation files go
    before `_sweep_failed`, whose `copy: gone` update would move `updated_at` and keep the row a second day."""
    idea, meera = cast["idea"], cast["meera"]
    s = get_settings()
    ended = (dt.datetime.now(dt.UTC) - dt.timedelta(hours=25)).isoformat()
    att = _row(
        db, idea, meera, state="upload_failed", hours_ago=26, changed_hours_ago=25,
        checks={"type": "pdf", "result": "check_failed", "waiting_for": F.NO_WAIT, "ended_at": ended},
    )  # fmt: skip
    key = _copy(db, objects, att, s.s3_bucket_quarantine)
    _start_swept(db)
    assert F.sweep_failed_copies(db) == 1
    assert _left(db, idea) == set()
    assert (s.s3_bucket_quarantine, key) not in objects
    assert _swept(db, idea) == [("system:files", {"file_id": att, "purpose": "conversation"})]


def test_bld_a256_l_convo_7_a_file_that_waited_three_days_is_checked_on_switch_on_and_sent(
    db: Conn,
    cast: dict[str, Any],
    objects: dict[Any, bytes],
    stood_in: list[int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """(e) The switch-on path end to end. Kavya adds a file for the conversation while the assistant is off: its check
    waits for the gatekeeper, and the hourly sweep leaves it however long it waits (here 3 days since it was added;
    `created_at` is aged by an UPDATE, so the trigger keeps `updated_at` fresh: case (a) ages both). The assistant
    comes back: the watch makes the check due, it passes, the sweep still leaves it (its day starts now), and her
    message carries it (L-CONVO/7)."""
    monkeypatch.setattr("convo.adapters.notify_post", lambda conn, kind, recipients, **kw: None)
    idea, kavya = cast["idea"], cast["kavya"]
    s = get_settings()
    att = str(
        F.accept(
            db, user_id=kavya["id"], name="branch-notes.pdf", data=make.pdf([WORDS]), idea_id=idea["idea_id"],
            purpose="conversation",
        )["id"]
    )  # fmt: skip
    key = str(_one(db, "SELECT store_key FROM attachments WHERE id = %s", att)["store_key"])
    try:
        _switch(db, "off", "ai.all")
        _run(db, att)  # the check waits before the virus scan, without using a try (BLD-C225)
        assert stood_in == []
        assert _job(db, att) == {
            "state": "queued",
            "attempts": 0,
            "last_error": F.WAITING_GATEKEEPER,
            "due": False,
        }
        db.execute("UPDATE attachments SET created_at = now() - interval '72 hours' WHERE id = %s", (att,))
        _start_swept(db)
        assert F.sweep_failed_copies(db) == 0
        row = _one(db, "SELECT file_state, checks->>'waiting_for' AS w FROM attachments WHERE id = %s", att)
        assert row == {"file_state": "checking", "w": F.GATEKEEPER}
        assert (s.s3_bucket_quarantine, key) in objects and _job(db, att)["state"] == "queued"

        _switch(db, "on")
        assert F.requeue_waiting(db) >= 1  # the ticker's watch (BLD-C226)
        assert _job(db, att)["due"] is True
        _run(db, att)
        assert len(stood_in) == 1
        assert _one(db, "SELECT file_state FROM attachments WHERE id = %s", att)["file_state"] == "checked"
        assert (s.s3_bucket_clean, key) in objects and (s.s3_bucket_quarantine, key) not in objects
        assert F.sweep_failed_copies(db) == 0  # a full day to send it from here
        assert _left(db, idea) == {att}

        out = send(db, idea["idea_id"], kavya["id"], {"file_ids": [att]})
        [sent] = out["entry"]["files"]
        assert (sent["id"], sent["state"]) == (att, "checked")
        on = _one(db, "SELECT conversation_entry_id AS entry FROM attachments WHERE id = %s", att)
        assert str(on["entry"]) == out["entry"]["id"]
        assert F.sweep_failed_copies(db) == 0 and _swept(db, idea) == []
    finally:
        _switch(db, "on")
