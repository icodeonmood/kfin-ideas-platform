"""Regression tests from the B3 review against the real store and a fresh database: a file removed while it is
being checked never reaches the clean bucket; files cannot be added once an idea has left draft; a check that
gives up tells the person; the purge re-checks each draft's expiry."""

from __future__ import annotations

import secrets
from typing import Any

import pytest

from attachments import clamav, service, store
from core.config import get_settings
from core.db import connect
from jobs import handlers  # noqa: F401 - registers handlers
from jobs.runner import run_one
from tests import files
from tests.helpers import db_url

pytestmark = pytest.mark.stack
CODE = "CTR-0a1b2c"


@pytest.fixture
def fresh(db: Any, test_database: str) -> Any:
    # Start ATT numbers far from the dev database's so the shared buckets never see the same key.
    db.execute(
        "INSERT INTO id_counters (kind, period, last_value) "
        "SELECT 'ATT', to_char(now() AT TIME ZONE 'Asia/Kolkata', 'YYYY'), %s "
        "ON CONFLICT (kind, period) DO UPDATE SET last_value = EXCLUDED.last_value",
        (900_000 + secrets.randbelow(90_000),),
    )
    return db


def _idea(db: Any, stage: str = "draft") -> str:
    row = db.execute(
        "INSERT INTO ideas (stage, contributor_code, draft_expires_at) VALUES (%s, %s, now() + interval '1 day') "
        "RETURNING id",
        (stage, CODE),
    ).fetchone()
    return str(row["id"])


def _where(att_id: str) -> tuple[bool, bool]:
    s = get_settings()
    return store.exists(s.s3_bucket_quarantine, f"att/{att_id}"), store.exists(
        s.s3_bucket_clean, f"att/{att_id}"
    )


def test_removed_during_checks_never_reaches_clean(fresh: Any, test_database: str, monkeypatch: Any) -> None:
    idea = _idea(fresh)
    att = service.accept(
        fresh, idea_uuid=idea, uploaded_by_code=CODE, name="a.pdf", data=files.pdf(["Synthetic"])
    )["id"]
    other = connect(db_url(test_database), autocommit=True)

    def scan_then_remove(data: bytes, timeout: float = 60.0) -> clamav.ScanResult:
        service.remove(other, att)  # the owner removes the file mid-check
        return clamav.ScanResult(clean=True, signature=None)

    monkeypatch.setattr(clamav, "scan_bytes", scan_then_remove)
    assert service.process(fresh, att) == "missing"
    assert _where(att) == (False, False)
    other.close()


def test_no_new_files_once_submitted(fresh: Any) -> None:
    idea = _idea(fresh, stage="scanning")
    with pytest.raises(service.AttachmentRefused) as refused:
        service.accept(
            fresh, idea_uuid=idea, uploaded_by_code=CODE, name="a.pdf", data=files.pdf(["Synthetic"])
        )
    assert refused.value.code == "not_a_draft"


def test_a_check_that_gives_up_rejects_the_file(fresh: Any, monkeypatch: Any) -> None:
    idea = _idea(fresh)
    att = service.accept(
        fresh, idea_uuid=idea, uploaded_by_code=CODE, name="a.pdf", data=files.pdf(["Synthetic"])
    )["id"]
    fresh.execute("DELETE FROM jobs WHERE dedupe_key IS DISTINCT FROM %s", (f"attachment:{att}",))
    fresh.execute("UPDATE jobs SET max_attempts = 1 WHERE dedupe_key = %s", (f"attachment:{att}",))

    def down(data: bytes, timeout: float = 60.0) -> clamav.ScanResult:
        raise clamav.ScannerUnavailable("ConnectionRefusedError")

    monkeypatch.setattr(clamav, "scan_bytes", down)
    assert run_one(fresh, "test-worker")
    row = fresh.execute("SELECT state, rejection FROM attachments WHERE id = %s", (att,)).fetchone()
    assert row["state"] == "rejected" and row["rejection"]["code"] == "check_failed"
    assert _where(att) == (False, False)


def test_purge_keeps_a_draft_whose_expiry_moved(fresh: Any) -> None:
    expired = _idea(fresh)
    fresh.execute("UPDATE ideas SET draft_expires_at = now() - interval '1 day' WHERE id = %s", (expired,))
    att = service.accept(
        fresh, idea_uuid=expired, uploaded_by_code=CODE, name="a.pdf", data=files.pdf(["Synthetic"])
    )["id"]
    fresh.execute("DELETE FROM jobs")
    fresh.execute("INSERT INTO jobs (type) VALUES ('drafts.purge')")
    assert run_one(fresh, "test-worker")
    assert fresh.execute("SELECT 1 FROM ideas WHERE id = %s", (expired,)).fetchone() is None
    assert _where(att) == (False, False)
