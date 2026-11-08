"""AT-B1-03: `make seed` creates the company repo at $COMPANY_REPO_PATH as a Git repo with one commit; the OKF
validator exits 0 on it; the validator exits non-zero on a fixture file with no `type`."""

import os
import subprocess
from pathlib import Path

import pytest

from okf.validate import main as validate
from repo_writer.git import Git
from tests import helpers

pytestmark = pytest.mark.stack


def test_seed_creates_a_valid_repo_with_one_commit(test_database: str, tmp_path: Path) -> None:
    repo = tmp_path / "kfin-ideas"
    env = {
        **os.environ,
        "COMPANY_REPO_PATH": str(repo),
        "DATABASE_URL": helpers.db_url(test_database),
        "APP_ENV": "test",
    }
    run = subprocess.run(
        ["uv", "run", "--frozen", "python", "-m", "bootstrap.seed"],
        cwd=helpers.ROOT / "services" / "worker",
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stdout[-2000:]
    git = Git(repo)
    assert git.is_repo()
    assert git.commit_count() == 1
    assert "event: repo.seeded" in git.run("log", "-1", "--format=%B")
    assert validate([str(repo), "--quiet"]) == 0

    # Re-running leaves the existing repo alone.
    again = subprocess.run(
        ["uv", "run", "--frozen", "python", "-m", "bootstrap.seed"],
        cwd=helpers.ROOT / "services" / "worker",
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert again.returncode == 0
    assert "already exists" in again.stdout
    assert git.commit_count() == 1


def test_validator_fails_on_a_file_with_no_type(company_repo: Path) -> None:
    (company_repo / "ideas" / "broken.md").write_text(
        "---\ntitle: No type here\n---\nBody\n", encoding="utf-8"
    )
    assert validate([str(company_repo), "--quiet"]) != 0
