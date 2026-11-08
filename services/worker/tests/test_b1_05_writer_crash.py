"""AT-B1-05: killing the repo writer mid-batch and restarting it commits each pending event exactly once
(idempotent on event ID)."""

import os
import re
import signal
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

import pytest

from tests import helpers

pytestmark = pytest.mark.stack

WORKER_DIR = helpers.ROOT / "services" / "worker"


def _writer(repo: Path, database: str, *, once: bool, fault: str | None = None) -> subprocess.Popen[str]:
    env = {
        **os.environ,
        "APP_ENV": "test",
        "COMPANY_REPO_PATH": str(repo),
        "DATABASE_URL": helpers.db_url(database),
        "REPO_WRITER_POLL_SECONDS": "0.1",
    }
    env.pop("REPO_WRITER_FAULT", None)
    if fault:
        env["REPO_WRITER_FAULT"] = fault
    # The venv interpreter directly (not `uv run`), so SIGKILL reaches the writer itself.
    cmd = [sys.executable, "-m", "repo_writer", *(["--once"] if once else [])]
    return subprocess.Popen(
        cmd, cwd=WORKER_DIR, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )


def _assert_exactly_once(db, repo: Path, event_ids: list[int]) -> None:
    trailers = [
        int(m.group(1))
        for c in helpers.git_log(repo)
        for m in [re.search(r"^outbox: (\d+)$", c, re.MULTILINE)]
        if m
    ]
    counts = Counter(trailers)
    assert sorted(counts) == sorted(event_ids), "every event committed"
    assert all(n == 1 for n in counts.values()), f"an event was committed twice: {counts}"
    rows = db.execute("SELECT id, commit_sha FROM outbox ORDER BY id").fetchall()
    assert all(r["commit_sha"] for r in rows)
    shas = {c.split("\x1f", 1)[0]: c for c in helpers.git_log(repo)}
    for r in rows:
        assert f"outbox: {r['id']}" in shas[r["commit_sha"]], "the recorded SHA is the commit for that event"


def test_crash_after_commit_before_db_update_is_recovered(db, company_repo: Path, test_database: str) -> None:
    events = [helpers.insert_event(db, helpers.insert_idea(db)) for _ in range(8)]
    crashed = _writer(company_repo, test_database, once=True, fault="crash_after_commit:3")
    assert crashed.wait(timeout=60) == 137
    # The third commit exists in Git but the database never heard about it.
    assert db.execute("SELECT count(*) AS n FROM outbox WHERE commit_sha IS NOT NULL").fetchone()["n"] == 2
    assert len(helpers.git_log(company_repo)) == 1 + 3

    rerun = _writer(company_repo, test_database, once=True)
    assert rerun.wait(timeout=60) == 0, rerun.stdout.read() if rerun.stdout else ""
    _assert_exactly_once(db, company_repo, events)
    assert len(helpers.git_log(company_repo)) == 1 + len(events)


def test_sigkill_during_a_batch_then_restart(db, company_repo: Path, test_database: str) -> None:
    events = [helpers.insert_event(db, helpers.insert_idea(db)) for _ in range(30)]
    proc = _writer(company_repo, test_database, once=False)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        done = db.execute("SELECT count(*) AS n FROM outbox WHERE commit_sha IS NOT NULL").fetchone()["n"]
        if done >= 3:
            break
        time.sleep(0.05)
    os.kill(proc.pid, signal.SIGKILL)
    proc.wait(timeout=10)
    committed = db.execute("SELECT count(*) AS n FROM outbox WHERE commit_sha IS NOT NULL").fetchone()["n"]
    assert 3 <= committed < len(events), "the kill must land mid-batch"

    rerun = _writer(company_repo, test_database, once=True)
    assert rerun.wait(timeout=90) == 0, rerun.stdout.read() if rerun.stdout else ""
    _assert_exactly_once(db, company_repo, events)
