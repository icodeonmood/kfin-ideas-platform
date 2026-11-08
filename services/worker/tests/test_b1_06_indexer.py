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
