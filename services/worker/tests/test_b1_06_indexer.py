"""AT-B1-06: after a commit the indexer upserts `chunks` for changed files within 60 seconds
(`EMBEDDINGS_MODE=hash`); deleting a file removes its chunks."""

import threading
import time
from pathlib import Path

import pytest

from embeddings import hash_embed
from index.indexer import Indexer
from repo_writer.git import Git
from repo_writer.writer import RepoWriter
from tests import helpers

pytestmark = pytest.mark.stack


def _wait(predicate, timeout: float) -> float:
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        if predicate():
            return time.monotonic() - start
        time.sleep(0.2)
    raise AssertionError(f"condition not met within {timeout} s")


def test_commit_then_delete(db, company_repo: Path, test_database: str) -> None:
    settings = helpers.settings_for(
        company_repo, test_database, index_poll_seconds=1.0, embeddings_mode="hash"
    )
    indexer = Indexer(settings)
    indexer.run_once()  # index the seed first
    seeded = db.execute("SELECT count(*) AS n FROM chunks").fetchone()["n"]
    assert seeded > 0

    stop = threading.Event()
    thread = threading.Thread(target=indexer.run_forever, args=(stop,), daemon=True)
    thread.start()
    try:
        idea_id = helpers.insert_idea(db)
        helpers.insert_event(db, idea_id)
        writer = RepoWriter(settings)
        assert writer.acquire()
        try:
            writer.run_once()
        finally:
            writer.release()
        rel = db.execute("SELECT repo_path FROM ideas WHERE idea_id = %s", (idea_id,)).fetchone()["repo_path"]

        def has_chunk() -> bool:
            r = db.execute("SELECT count(*) AS n FROM chunks WHERE repo_path = %s", (rel,)).fetchone()
            return bool(r["n"] == 1)

        assert _wait(has_chunk, timeout=60) <= 60
        chunk = db.execute(
            "SELECT file_type, section, trust, visibility, stage, vector_dims(embedding) AS dims, "
            "(embedding <=> %s::vector) AS distance FROM chunks WHERE repo_path = %s",
            (str(hash_embed("SIP registrations slip because ops re-check forms by hand")), rel),
        ).fetchone()
        assert chunk["file_type"] == "idea" and chunk["section"] == "card"
        assert chunk["trust"] == "unverified" and chunk["visibility"] == "org" and chunk["stage"] == "scanned"
        assert chunk["dims"] == 1024
        assert chunk["distance"] < 1.0  # overlapping words → positive cosine in hash mode
        links = {
            r["to_path"]
            for r in db.execute("SELECT to_path FROM links WHERE from_path = %s", (rel,)).fetchall()
        }
        assert "taxonomy/glossary/GL-nigo.md" in links  # frontmatter reference resolved to the glossary file

        # Delete the file (a test-only commit in a temp repo) and the chunks go.
        git = Git(company_repo)
        git.run("rm", "-q", rel)
        git.run("commit", "-q", "-m", "test: delete", "--author", "Test <t@localhost>")
        assert _wait(lambda: not has_chunk(), timeout=60) <= 60
        assert db.execute("SELECT count(*) AS n FROM links WHERE from_path = %s", (rel,)).fetchone()["n"] == 0
    finally:
        stop.set()
        thread.join(timeout=10)


def test_rebuild_matches_incremental(db, company_repo: Path, test_database: str) -> None:
    settings = helpers.settings_for(company_repo, test_database)
    Indexer(settings).run_once()
    before = db.execute("SELECT count(*) AS n, count(DISTINCT repo_path) AS f FROM chunks").fetchone()
    result = Indexer(settings).run_once(rebuild=True)
    after = db.execute("SELECT count(*) AS n, count(DISTINCT repo_path) AS f FROM chunks").fetchone()
    assert result.rebuilt and before == after
    assert db.execute("SELECT count(*) AS n FROM terms WHERE glossary_id = 'GL-nigo'").fetchone()["n"] >= 2


def test_odd_files_are_skipped_not_fatal(db, company_repo: Path, test_database: str) -> None:
    """A malformed concept file is logged and skipped; the index still advances (review finding)."""
    settings = helpers.settings_for(company_repo, test_database)
    Indexer(settings).run_once()
    (company_repo / "solutions" / "SOL-0001.md").write_text(
        "---\ntype: solution\nkfin:\n  id: SOL-0001\n  areas: 5\n  stage: {odd: 1}\n---\n## What it does\nA fix.\n",
        encoding="utf-8",
    )
    (company_repo / "solutions" / "SOL-0002.md").write_bytes(
        b"---\ntype: solution\n---\n\xff\xfe not utf-8\n"
    )
    git = Git(company_repo)
    git.run("add", "-A")
    git.run("commit", "-q", "-m", "test: odd files", "--author", "Test <t@localhost>")
    result = Indexer(settings).run_once()
    assert result.to_commit == git.head()
    assert db.execute("SELECT last_commit FROM index_state").fetchone()["last_commit"] == git.head()
    row = db.execute(
        "SELECT area_ids, stage FROM chunks WHERE repo_path = 'solutions/SOL-0001.md'"
    ).fetchone()
    assert row["area_ids"] == ["5"] and row["stage"] is None


def test_deleting_a_target_reverts_links_to_ids(db, company_repo: Path, test_database: str) -> None:
    settings = helpers.settings_for(company_repo, test_database)
    Indexer(settings).run_once()
    idea_id = helpers.insert_idea(db)
    helpers.insert_event(db, idea_id)
    writer = RepoWriter(settings)
    assert writer.acquire()
    try:
        writer.run_once()
    finally:
        writer.release()
    Indexer(settings).run_once()
    rel = db.execute("SELECT repo_path FROM ideas WHERE idea_id = %s", (idea_id,)).fetchone()["repo_path"]
    assert db.execute(
        "SELECT 1 FROM links WHERE from_path = %s AND to_path = 'taxonomy/glossary/GL-nigo.md'", (rel,)
    ).fetchone()
    git = Git(company_repo)
    git.run("rm", "-q", "taxonomy/glossary/GL-nigo.md")
    git.run("commit", "-q", "-m", "test: delete a glossary term", "--author", "Test <t@localhost>")
    Indexer(settings).run_once()
    targets = {
        r["to_path"] for r in db.execute("SELECT to_path FROM links WHERE from_path = %s", (rel,)).fetchall()
    }
    assert "taxonomy/glossary/GL-nigo.md" not in targets
    assert "id:GL-nigo" in targets
