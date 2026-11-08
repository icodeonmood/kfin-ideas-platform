"""The writer pushes to the company repo's remote without ever blocking commits (§2.7)."""

import time
from pathlib import Path

import pytest

from core.config import Settings
from repo_writer.git import Git
from repo_writer.writer import RepoWriter
from tests import helpers


def test_env_comment_values_are_treated_as_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMPANY_REPO_REMOTE", "# internal Git remote; empty = local only")
    assert Settings().company_repo_remote == ""


def test_push_failure_backs_off_without_sleeping(tmp_path: Path) -> None:
    repo = helpers.seeded_repo(tmp_path / "kfin-ideas")
    Git(repo).run("remote", "add", "origin", str(tmp_path / "missing-remote.git"))
    writer = RepoWriter(Settings(company_repo_path=repo, company_repo_remote="origin"))
    start = time.monotonic()
    writer._push()
    writer._push()  # not due yet: returns at once
    assert time.monotonic() - start < 2
    assert writer._push_failures == 1 and writer._next_push_at > time.monotonic()


def test_push_succeeds_to_a_bare_remote(tmp_path: Path) -> None:
    repo = helpers.seeded_repo(tmp_path / "kfin-ideas")
    bare = tmp_path / "mirror.git"
    Git(tmp_path).run("init", "-q", "--bare", "-b", "main", str(bare))
    Git(repo).run("remote", "add", "origin", str(bare))
    writer = RepoWriter(Settings(company_repo_path=repo, company_repo_remote="origin"))
    writer._push()
    assert writer._push_failures == 0
    assert Git(bare).run("rev-parse", "main").strip() == Git(repo).head()
