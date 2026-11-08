"""Nightly reconcile (§3.5; AT-B8-02 needs "reconcile reports no drift" after a restore): index drift is found
and fixed from the repo; idea files that disagree with the database on visibility are reported loudly."""

from __future__ import annotations

from typing import Any

import pytest

from reconcile import run
from tests import helpers

pytestmark = pytest.mark.stack


def test_a_clean_index_has_no_drift(world: Any, company_repo: Any, test_database: str) -> None:
    settings = helpers.settings_for(company_repo, test_database, embeddings_mode="hash")
    drift = run(settings)
    assert drift.total == 0 and drift.fixed == 0


def test_index_drift_is_found_and_fixed(world: Any, company_repo: Any, test_database: str) -> None:
    db = world
    settings = helpers.settings_for(company_repo, test_database, embeddings_mode="hash")
    gone = db.execute("SELECT repo_path FROM repo_files ORDER BY repo_path LIMIT 1").fetchone()["repo_path"]
    db.execute("DELETE FROM repo_files WHERE repo_path = %s", (gone,))  # lost from the index
    db.execute(
        "INSERT INTO repo_files (repo_path, kfin_id, file_type, trust, stage, visibility, commit_sha) "
        "VALUES ('ideas/2026/11/IDEA-2026-009999.md', 'IDEA-2026-009999', 'idea', 'machine', 'scanned', 'org', 'x')"
    )  # in the index but not in the repo
    flipped = db.execute(
        "UPDATE repo_files SET visibility = 'org' WHERE visibility = 'committee' RETURNING repo_path"
    ).fetchone()["repo_path"]  # the index says open, the file says committee-only

    drift = run(settings, fix=False)
    assert drift.missing_in_index == [gone]
    assert drift.stale_in_index == ["ideas/2026/11/IDEA-2026-009999.md"]
    assert flipped in drift.mismatched
    assert (
        db.execute("SELECT count(*) AS n FROM repo_files WHERE repo_path = %s", (gone,)).fetchone()["n"] == 0
    )

    fixed = run(settings)
    assert fixed.fixed == 3
    assert run(settings).total == 0  # a second run finds nothing
    assert (
        db.execute("SELECT visibility FROM repo_files WHERE repo_path = %s", (flipped,)).fetchone()[
            "visibility"
        ]
        == "committee"
    )


def test_an_idea_file_showing_the_wrong_visibility_is_reported(
    world: Any, company_repo: Any, test_database: str
) -> None:
    db = world
    settings = helpers.settings_for(company_repo, test_database, embeddings_mode="hash")
    row = db.execute(
        "SELECT repo_path, kfin_id FROM repo_files WHERE file_type = 'idea' AND visibility = 'committee' LIMIT 1"
    ).fetchone()
    db.execute(
        "INSERT INTO ideas (idea_id, submission_id, stage, contributor_code, visibility, repo_path, canvas, "
        "submitted_at) VALUES (%s, %s, 'reviewed', 'CTR-abc123', 'org', %s, '{}', now())",
        (row["kfin_id"], row["kfin_id"].replace("IDEA-", "SUB-"), row["repo_path"]),
    )
    drift = run(settings, fix=False)
    assert drift.idea_visibility_mismatch == [row["kfin_id"]]
    db.execute(
        "INSERT INTO outbox (event_type, aggregate_id, actor) VALUES ('idea.reviewed', %s, 'system')",
        (row["kfin_id"],),
    )
    assert run(settings, fix=False).idea_visibility_mismatch == []  # the writer has it queued: not drift yet


def test_a_file_that_cannot_be_fixed_does_not_block_the_rest(
    world: Any, company_repo: Any, test_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import index.indexer as ix

    db = world
    settings = helpers.settings_for(company_repo, test_database, embeddings_mode="hash")
    gone = [r["repo_path"] for r in db.execute("SELECT repo_path FROM repo_files ORDER BY repo_path LIMIT 2")]
    db.execute("DELETE FROM repo_files WHERE repo_path = ANY(%s)", (gone,))
    real = ix.Indexer._upsert

    def flaky(self: Any, conn: Any, rel: str, commit: str) -> bool:
        if rel == gone[0]:
            raise ValueError("odd file")
        return real(self, conn, rel, commit)

    monkeypatch.setattr(ix.Indexer, "_upsert", flaky)
    drift = run(settings)
    assert drift.unfixable == [gone[0]] and drift.fixed == 1
    assert db.execute("SELECT 1 FROM repo_files WHERE repo_path = %s", (gone[1],)).fetchone()


def test_no_fix_is_applied_if_the_indexer_moved_on_meanwhile(
    world: Any, company_repo: Any, test_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import reconcile as rc

    db = world
    settings = helpers.settings_for(company_repo, test_database, embeddings_mode="hash")
    gone = db.execute("SELECT repo_path FROM repo_files ORDER BY repo_path LIMIT 1").fetchone()["repo_path"]
    db.execute("DELETE FROM repo_files WHERE repo_path = %s", (gone,))
    real = rc._expected

    def then_the_indexer_commits(git: Any, commit: str) -> Any:
        out = real(git, commit)
        db.execute(
            "UPDATE index_state SET last_commit = %s", ("f" * 40,)
        )  # a newer commit, indexed meanwhile
        return out

    monkeypatch.setattr(rc, "_expected", then_the_indexer_commits)
    drift = run(settings)
    assert drift.missing_in_index == [gone] and drift.fixed == 0  # found, but left for the next run
    assert db.execute("SELECT 1 FROM repo_files WHERE repo_path = %s", (gone,)).fetchone() is None
