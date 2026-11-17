"""AT-B3-04 (server half): drafts never reach the company repo (see test_b1_04) and a job purges drafts older
than the retention period. The scheduler enqueues the purge once a day."""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from jobs import handlers  # noqa: F401 - registers handlers
from jobs.runner import HANDLERS, run_one
from jobs.schedule import DAILY, EVERY, RETIRED, WEEKLY, enqueue_due

pytestmark = pytest.mark.stack


def _draft(db: Any, days_left: int) -> str:
    return str(
        db.execute(
            "INSERT INTO ideas (stage, contributor_code, draft_encrypted, draft_expires_at) "
            "VALUES ('draft', 'CTR-0a1b2c', '\\x01'::bytea, now() + make_interval(days => %s)) RETURNING id",
            (days_left,),
        ).fetchone()["id"]
    )


def test_purge_removes_only_expired_drafts(db: Any) -> None:
    expired = _draft(db, -1)
    fresh = _draft(db, 29)
    db.execute("INSERT INTO jobs (type) VALUES ('drafts.purge')")
    assert run_one(db, "test-worker")
    ids = {str(r["id"]) for r in db.execute("SELECT id FROM ideas").fetchall()}
    assert expired not in ids and fresh in ids
    assert db.execute("SELECT state FROM jobs WHERE type = 'drafts.purge'").fetchone()["state"] == "done"


def test_purge_removes_an_expired_draft_with_a_link_and_carries_on(db: Any) -> None:
    """Review blocker 1 (L-HIDE.files, A-API.files): a link has no stored copy (its key is NULL). Removing it must not
    reach the store, so the purge succeeds and the next expired draft goes too."""
    from onepc.context import seal_text

    with_link, after = _draft(db, -2), _draft(db, -1)
    db.execute(
        "INSERT INTO attachments (id, idea_uuid, uploaded_by_code, name, bytes, state, kind, file_state, link_scope, "
        "url_encrypted) VALUES ('ATT-2026-990001', %s, 'CTR-0a1b2c', 'example.org/report', 0, 'quarantine', 'link', "
        "'ok', 'external', %s)",
        (
            with_link,
            seal_text("attachments", "url_encrypted", "ATT-2026-990001", "https://example.org/report"),
        ),
    )
    db.execute("INSERT INTO jobs (type, run_at) VALUES ('drafts.purge', '2000-01-01')")
    assert run_one(db, "test-worker")
    ids = {str(r["id"]) for r in db.execute("SELECT id FROM ideas").fetchall()}
    assert with_link not in ids and after not in ids
    assert db.execute("SELECT 1 FROM attachments WHERE id = 'ATT-2026-990001'").fetchone() is None
    job = db.execute(
        "SELECT state, last_error FROM jobs WHERE type = 'drafts.purge' ORDER BY id DESC"
    ).fetchone()
    assert (job["state"], job["last_error"]) == ("done", None)


def test_schedule_enqueues_once_a_day(db: Any) -> None:
    db.execute("DELETE FROM jobs")
    ist = ZoneInfo("Asia/Kolkata")

    def daily(at: datetime) -> list[str]:  # jobs that run every few minutes are tested on their own
        return [j for j in enqueue_due(db, at) if j not in EVERY]

    assert daily(datetime(2026, 11, 20, 1, 59, tzinfo=ist)) == []  # before 02:00 (reconcile)
    assert daily(datetime(2026, 11, 20, 2, 0, tzinfo=ist)) == ["reconcile"]  # drafts.purge at 03:30
    assert daily(datetime(2026, 11, 20, 3, 31, tzinfo=ist)) == ["drafts.purge"]
    assert daily(datetime(2026, 11, 20, 9, 0, tzinfo=ist)) == []  # learning.run is retired (DEC-106, R13)
    assert daily(datetime(2026, 11, 20, 9, 31, tzinfo=ist)) == ["delivery.tick"]  # 09:30
    assert daily(datetime(2026, 11, 20, 23, 0, tzinfo=ist)) == [
        "comms.digest"
    ]  # comms.nudges is retired (R16)
    assert daily(datetime(2026, 11, 21, 3, 31, tzinfo=ist)) == ["reconcile", "drafts.purge"]


def test_weekly_and_every_few_minutes(db: Any) -> None:
    db.execute("DELETE FROM jobs")
    ist = ZoneInfo("Asia/Kolkata")
    # The weekly clustering batch and the lens build are retired (DEC-106, R6, R12): never queued, at any hour.
    for at in (datetime(2026, 11, 22, 22, 0, tzinfo=ist), datetime(2026, 11, 23, 5, 0, tzinfo=ist)):
        queued = enqueue_due(db, at)
        assert "cluster.batch" not in queued and "lenses.build" not in queued
        assert "qualify.backfill" not in queued  # R7
    db.execute("DELETE FROM jobs")
    assert "attachments.recheck" in enqueue_due(db, datetime(2026, 11, 23, 10, 0, tzinfo=ist))
    assert "attachments.recheck" not in enqueue_due(db, datetime(2026, 11, 23, 10, 5, tzinfo=ist))
    assert "attachments.recheck" in enqueue_due(db, datetime(2026, 11, 23, 10, 15, tzinfo=ist))


def test_no_retired_job_is_scheduled() -> None:
    """DEC-106: nothing of a retired feature is queued by the scheduler; its handler stays until the cleanup."""
    assert RETIRED.isdisjoint({*DAILY, *WEEKLY, *EVERY})
    assert {"comms.nudges", "learning.run", "cluster.batch", "lenses.build", "qualify.backfill"} <= RETIRED
    assert set(HANDLERS) >= RETIRED


def test_jobs_for_later_blocks_wait_instead_of_failing(db: Any) -> None:
    db.execute("DELETE FROM jobs")
    db.execute("INSERT INTO jobs (type) VALUES ('match.weekly')")
    assert run_one(db, "test-worker") is False
    row = db.execute("SELECT state, attempts FROM jobs WHERE type = 'match.weekly'").fetchone()
    assert (row["state"], row["attempts"]) == ("queued", 0)
