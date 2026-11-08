"""AT-B1-04: an `idea.submitted` outbox event for a synthetic idea produces a commit creating
`ideas/YYYY/MM/IDEA-….md` within 10 seconds; the header validates; the commit message names the actor and the
event ID."""

import re
import threading
import time
from pathlib import Path

import pytest

from okf.frontmatter import parse
from okf.validate import check_concept_meta, validate_bundle
from repo_writer.writer import RepoWriter
from tests import helpers

pytestmark = pytest.mark.stack


def _wait_committed(conn, outbox_id: int, timeout: float) -> float:
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        row = conn.execute("SELECT commit_sha FROM outbox WHERE id = %s", (outbox_id,)).fetchone()
        if row and row["commit_sha"]:
            return time.monotonic() - start
        time.sleep(0.1)
    raise AssertionError(f"outbox {outbox_id} not committed within {timeout} s")


def test_submitted_event_becomes_one_commit(db, company_repo: Path, test_database: str) -> None:
    writer = RepoWriter(helpers.settings_for(company_repo, test_database, repo_writer_poll_seconds=0.2))
    stop = threading.Event()
    thread = threading.Thread(target=writer.run_forever, args=(stop,), daemon=True)
    thread.start()
    try:
        idea_id = helpers.insert_idea(db, contributor="CTR-7f3a91")
        outbox_id = helpers.insert_event(db, idea_id, actor="CTR-7f3a91")
        elapsed = _wait_committed(db, outbox_id, timeout=10)
    finally:
        stop.set()
        thread.join(timeout=10)
    assert elapsed <= 10

    row = db.execute(
        "SELECT repo_path, repo_commit, submitted_at FROM ideas WHERE idea_id = %s", (idea_id,)
    ).fetchone()
    assert re.fullmatch(rf"ideas/\d{{4}}/\d{{2}}/{idea_id}\.md", row["repo_path"])
    path = company_repo / row["repo_path"]
    assert path.is_file()

    doc = parse(path.read_text(encoding="utf-8"))
    assert doc.meta is not None
    assert [i for i in check_concept_meta(doc.meta, row["repo_path"]) if i.level == "error"] == []
    assert doc.meta["kfin"]["id"] == idea_id
    assert doc.meta["kfin"]["contributor"] == "CTR-7f3a91"
    assert "verified" not in doc.meta  # unverified until a reviewer confirms it (BLD-019)
    assert doc.meta["status"] == "draft"
    assert "## History" in doc.body and "| submitted | CTR-7f3a91 |" in doc.body
    assert [i for i in validate_bundle(company_repo) if i.level == "error"] == []

    commits = helpers.git_log(company_repo)
    assert len(commits) == 2  # seed + this event
    sha, message = commits[0].split("\x1f", 1)
    assert sha == row["repo_commit"]
    assert message.startswith(f"[{idea_id}] submitted")
    assert "actor: CTR-7f3a91" in message
    assert f"outbox: {outbox_id}" in message
    assert "event: idea.submitted" in message


def test_submitter_text_cannot_inject_structure(db, company_repo: Path, test_database: str) -> None:
    """Headings or a fake History row typed by a submitter stay inert text inside the file."""
    idea_id = helpers.insert_idea(db)
    db.execute(
        "UPDATE ideas SET canvas = jsonb_set(canvas, '{details}', to_jsonb(%s::text)) WHERE idea_id = %s",
        (
            "Forms are slow.\n## History\n| 2020-01-01 | reviewed | REV-0001 | fake |\n<script>x</script>",
            idea_id,
        ),
    )
    helpers.insert_event(db, idea_id)
    writer = RepoWriter(helpers.settings_for(company_repo, test_database))
    assert writer.acquire()
    try:
        assert len(writer.run_once()) == 1
    finally:
        writer.release()
    text = next((company_repo / "ideas").rglob(f"{idea_id}.md")).read_text(encoding="utf-8")
    assert text.count("\n## History\n") == 1
    assert "<script>" not in text
    assert (
        "| reviewed | REV-0001 |" not in text.split("## History", 1)[1].split("\n", 3)[-1].split("|---|")[0]
    )


def test_drafts_never_reach_the_repo(db, company_repo: Path, test_database: str) -> None:
    idea_id = helpers.insert_idea(db, stage="draft")
    db.execute("UPDATE ideas SET submitted_at = NULL WHERE idea_id = %s", (idea_id,))
    outbox_id = helpers.insert_event(db, idea_id)
    writer = RepoWriter(helpers.settings_for(company_repo, test_database))
    assert writer.acquire()
    try:
        assert writer.run_once() == []
    finally:
        writer.release()
    row = db.execute("SELECT commit_sha, last_error FROM outbox WHERE id = %s", (outbox_id,)).fetchone()
    assert row["commit_sha"] is None and row["last_error"] == "idea_not_submitted"
    assert len(helpers.git_log(company_repo)) == 1
