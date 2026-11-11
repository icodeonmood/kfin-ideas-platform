"""The repo writer never touches a company repo while `make seed` is writing it (BLD-A167).

CI failed now and then at "Seed the company repo" with a GitError, and passed on a re-run. The worker's repo writer
was already polling. Between the seed's `git init` and its first commit, it read the half-seeded repo as a dirty
tree left by a crashed write, cleared git's lock files and reset it. The same could happen to a dev refresh of the
seed files on a running stack. The seed now leaves a marker beside the repo while it writes, and the writer skips
its rounds while the marker is there, or while the repo has no commit yet.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from repo_writer.git import SEED_MARKER_STALE_S, Git, seed_in_progress, seed_marker, seeding
from repo_writer.writer import RepoWriter
from tests import helpers


def test_the_marker_is_held_while_seeding_and_removed_after(tmp_path: Path) -> None:
    repo = tmp_path / "kfin-ideas"
    with seeding(repo, settle_s=0):
        assert seed_in_progress(repo)
        with pytest.raises(SystemExit), seeding(repo, settle_s=0):  # a second seed waits for the first
            pass
    assert not seed_in_progress(repo) and not seed_marker(repo).exists()


def test_an_interrupt_during_the_settle_wait_removes_the_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "kfin-ideas"

    def interrupted(_: float) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr("repo_writer.git.time.sleep", interrupted)
    with pytest.raises(KeyboardInterrupt), seeding(repo):
        pass
    assert not seed_marker(repo).exists()


def test_a_marker_left_by_a_seed_that_died_goes_stale(tmp_path: Path) -> None:
    repo = tmp_path / "kfin-ideas"
    seed_marker(repo).write_text("1\n", encoding="utf-8")
    old = time.time() - SEED_MARKER_STALE_S - 5
    os.utime(seed_marker(repo), (old, old))
    assert not seed_in_progress(repo)
    with seeding(repo, settle_s=0):  # taken over
        assert seed_in_progress(repo)


def test_the_writer_waits_while_a_seed_writes_then_carries_on(
    db, company_repo: Path, test_database: str
) -> None:
    idea_id = helpers.insert_idea(db)
    outbox_id = helpers.insert_event(db, idea_id)
    half_written = company_repo / "rules" / "half-written-by-seed.md"
    writer = RepoWriter(helpers.settings_for(company_repo, test_database))
    assert writer.acquire()
    try:
        with seeding(company_repo, settle_s=0):
            half_written.write_text("not committed yet\n", encoding="utf-8")
            assert writer.run_once() == []  # no reset, no commit
            assert half_written.exists()
            row = db.execute("SELECT committed_at FROM outbox WHERE id = %s", (outbox_id,)).fetchone()
            assert row["committed_at"] is None
            half_written.unlink()  # the seed's own commit would take it in; here it simply goes
        assert [o.outbox_id for o in writer.run_once()] == [outbox_id]
    finally:
        writer.release()


def test_the_writer_waits_for_a_repo_with_no_commit_yet(db, tmp_path: Path, test_database: str) -> None:
    repo = tmp_path / "kfin-ideas"
    repo.mkdir()
    (repo / "README.md").write_text("seed copy in progress\n", encoding="utf-8")
    Git(repo).init()
    writer = RepoWriter(helpers.settings_for(repo, test_database))
    assert writer.acquire()
    try:
        assert writer.run_once() == []
        assert (repo / "README.md").exists()  # not reset away
    finally:
        writer.release()
