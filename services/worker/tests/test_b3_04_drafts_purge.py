"""AT-B3-04 (server half): drafts never reach the company repo (see test_b1_04) and a job purges drafts older
than the retention period. The scheduler enqueues the purge once a day."""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from jobs import handlers  # noqa: F401 - registers handlers
from jobs.runner import run_one
from jobs.schedule import enqueue_due

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


def test_schedule_enqueues_once_a_day(db: Any) -> None:
    db.execute("DELETE FROM jobs")
    ist = ZoneInfo("Asia/Kolkata")
    assert enqueue_due(db, datetime(2026, 11, 20, 2, 0, tzinfo=ist)) == []  # before 03:30
    assert enqueue_due(db, datetime(2026, 11, 20, 3, 31, tzinfo=ist)) == ["drafts.purge"]
    assert enqueue_due(db, datetime(2026, 11, 20, 9, 0, tzinfo=ist)) == []  # already today
    assert enqueue_due(db, datetime(2026, 11, 21, 3, 31, tzinfo=ist)) == ["drafts.purge"]


def test_jobs_for_later_blocks_wait_instead_of_failing(db: Any) -> None:
    db.execute("DELETE FROM jobs")
    db.execute("INSERT INTO jobs (type) VALUES ('scan.run')")
    assert run_one(db, "test-worker") is False
    row = db.execute("SELECT state, attempts FROM jobs WHERE type = 'scan.run'").fetchone()
    assert (row["state"], row["attempts"]) == ("queued", 0)
