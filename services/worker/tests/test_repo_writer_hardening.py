"""Repo writer hardening from the B1 code review: stale Git locks, lost writer lock, unexpected errors,
recovery when the idea row is gone, and history fields that could break the History table."""

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from psycopg.types.json import Jsonb

from repo_writer.git import Git
from repo_writer.writer import LockLost, RepoWriter
from tests import helpers

pytestmark = pytest.mark.stack


def _writer(repo: Path, database: str) -> RepoWriter:
    w = RepoWriter(helpers.settings_for(repo, database))
    assert w.acquire()
    return w


def test_run_once_refuses_without_the_writer_lock(db: Any, company_repo: Path, test_database: str) -> None:
    with pytest.raises(LockLost):
        RepoWriter(helpers.settings_for(company_repo, test_database)).run_once()


def test_stale_git_lock_from_a_killed_writer_is_cleared(
    db: Any, company_repo: Path, test_database: str
) -> None:
    (company_repo / ".git" / "index.lock").write_text("", encoding="utf-8")
    helpers.insert_event(db, helpers.insert_idea(db))
    w = _writer(company_repo, test_database)
    try:
        assert len(w.run_once()) == 1
    finally:
        w.release()
    assert not (company_repo / ".git" / "index.lock").exists()


def test_unexpected_error_is_recorded_as_a_code_and_backs_off(
    db: Any, company_repo: Path, test_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    outbox_id = helpers.insert_event(db, helpers.insert_idea(db))
    w = _writer(company_repo, test_database)
    try:

        def boom(*_a: Any, **_k: Any) -> str:
            raise KeyError("Failing row contains SIP forms are slow")

        monkeypatch.setattr(w, "_write_idea_files", boom)
        assert w.run_once() == []
        row = db.execute(
            "SELECT attempts, last_error, commit_sha FROM outbox WHERE id = %s", (outbox_id,)
        ).fetchone()
        assert row["last_error"] == "KeyError" and row["attempts"] == 1 and row["commit_sha"] is None
        assert w.run_once() == []  # backing off: not retried at once
        assert (
            db.execute("SELECT attempts FROM outbox WHERE id = %s", (outbox_id,)).fetchone()["attempts"] == 1
        )
        monkeypatch.undo()
        w._retry_at.clear()
        assert len(w.run_once()) == 1  # recovers once the cause is gone
    finally:
        w.release()


def test_recovered_commit_is_recorded_even_if_the_idea_was_erased(
    db: Any, company_repo: Path, test_database: str
) -> None:
    idea_id = helpers.insert_idea(db)
    outbox_id = helpers.insert_event(db, idea_id)
    env = {
        "APP_ENV": "test",
        "COMPANY_REPO_PATH": str(company_repo),
        "DATABASE_URL": helpers.db_url(test_database),
        "REPO_WRITER_FAULT": "crash_after_commit:1",
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
    }
    crashed = subprocess.run(
        [sys.executable, "-m", "repo_writer", "--once"],
        cwd=helpers.ROOT / "services" / "worker",
        env=env,
        check=False,
    )
    assert crashed.returncode == 137
    db.execute("DELETE FROM ideas WHERE idea_id = %s", (idea_id,))  # e.g. erased before the writer came back
    w = _writer(company_repo, test_database)
    try:
        outcomes = w.run_once()
    finally:
        w.release()
    assert [o.recovered for o in outcomes] == [True]
    assert (
        db.execute("SELECT commit_sha FROM outbox WHERE id = %s", (outbox_id,)).fetchone()["commit_sha"]
        == Git(company_repo).head()
    )


@pytest.mark.parametrize("event_word", ["reviewed | REV-0001 | x", "reviewed\nmore", "Reviewed"])
def test_history_event_must_be_a_plain_word(
    db: Any, company_repo: Path, test_database: str, event_word: str
) -> None:
    idea_id = helpers.insert_idea(db)
    row = db.execute(
        "INSERT INTO outbox (event_type, aggregate_id, actor, payload) VALUES ('idea.updated', %s, 'system', %s) "
        "RETURNING id",
        (idea_id, Jsonb({"idea_id": idea_id, "history": [{"event": event_word, "note": ""}]})),
    ).fetchone()
    w = _writer(company_repo, test_database)
    try:
        assert w.run_once() == []
    finally:
        w.release()
    assert db.execute("SELECT last_error FROM outbox WHERE id = %s", (row["id"],)).fetchone()[
        "last_error"
    ] == ("history_event_invalid")
    assert len(helpers.git_log(company_repo)) == 1
