"""Shared fixtures. Every log line written during the run is captured and scanned at the end (AT-B1-10)."""

from __future__ import annotations

import io
import logging
import os
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest

os.environ.setdefault("APP_ENV", "test")
# Host-side tests have no Tesseract; synthetic images carry their text in metadata (attachments/ocr.py). The
# worker container keeps the real OCR, which the stack tests reach through the API.
os.environ.setdefault("OCR_MODE", "fake")

_CAPTURE = io.StringIO()


def pytest_configure(config: pytest.Config) -> None:
    from core import logging as klog

    handler = logging.StreamHandler(_CAPTURE)
    handler.setFormatter(klog._JsonFormatter())
    logging.getLogger().addHandler(handler)


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """BLD-A251: a test that uses `test_database`, directly or through `db`, `world` or any fixture built on it, needs
    the running stack. Its database is created on the stack's Postgres (localhost) and migrated with the stack's dbmate
    container. Such a test gets the `stack` mark here, before `-m` deselects, so a local `-m "not stack"` run never
    reaches that Postgres, which is the live demo's. `make test` and CI select every test, as before."""
    for item in items:
        if "test_database" in getattr(item, "fixturenames", ()) and item.get_closest_marker("stack") is None:
            item.add_marker(pytest.mark.stack)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Fail the run if any log line emitted by real code paths broke the log rules."""
    from pii.log_rules import scan_log_lines

    lines = _CAPTURE.getvalue().splitlines()
    violations = scan_log_lines(lines)
    if violations:
        reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        if reporter is not None:
            reporter.write_line(
                f"LOG SCRUBBER: {len(violations)} violations in {len(lines)} captured log lines"
            )
            for v in violations[:20]:
                reporter.write_line(f"  line {v.line_no}: {v.kind} {v.where}")
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


@pytest.fixture
def captured_logs() -> Iterator[io.StringIO]:
    yield _CAPTURE


@pytest.fixture(scope="session")
def test_database() -> Iterator[str]:
    """A fresh database for this test run, migrated with the real dbmate container (needs `make up`)."""
    from core.config import get_settings
    from tests import helpers

    try:
        name = helpers.create_database()
    except Exception as exc:
        pytest.fail(
            f"Postgres is not reachable on localhost:{get_settings().postgres_port}; run `make up` first "
            f"({type(exc).__name__})"
        )
    result = helpers.dbmate(name, "up")
    if result.returncode != 0:
        helpers.drop_database(name)
        pytest.fail(f"dbmate up failed with exit code {result.returncode}")
    yield name
    helpers.drop_database(name)


@pytest.fixture
def db(test_database: str) -> Iterator[object]:
    """Autocommit connection to the test database; outbox, ideas and index tables are emptied first."""
    from core.db import connect
    from tests import helpers

    conn = connect(helpers.db_url(test_database), autocommit=True)
    conn.execute(
        "TRUNCATE outbox, ideas, idea_links, chunks, links, terms, repo_files, users, review_items, "
        "llm_calls, llm_cache, pseudonym_vault, vault_counters, sla_timers, comms_log "
        "RESTART IDENTITY CASCADE; "
        "UPDATE index_state SET last_commit = NULL; UPDATE kill_switches SET state = 'on'"
    )
    yield conn
    conn.close()


@pytest.fixture
def company_repo(tmp_path_factory: pytest.TempPathFactory) -> object:
    from tests import helpers

    return helpers.seeded_repo(tmp_path_factory.mktemp("repo") / "kfin-ideas")


MATCH_TEXT = "Ops re-check every SIP mandate by hand because bank fields are often missing at capture"


@pytest.fixture
def world(db: object, company_repo: object, test_database: str) -> Iterator[object]:
    """An indexed repo with a matching idea, a committee-only idea, a solution and an unrelated idea (B5)."""
    from core import killswitch
    from gateway import limits
    from gateway.routes import FAKE_SCRIPT
    from tests import repo_fixtures as rf

    killswitch.clear_cache()
    limits.reset()
    FAKE_SCRIPT.clear()
    repo = cast(Path, company_repo)
    rf.idea(repo, 11, MATCH_TEXT, "Manual checks on SIP mandates delay registration", systems=["GL-sip"])
    rf.idea(repo, 12, MATCH_TEXT + " at the desk", "Committee-only summary text", visibility="committee")
    rf.concept(
        repo, "solution", 4, MATCH_TEXT + "; an automated capture check fixed it", "Automated mandate checks"
    )
    rf.idea(repo, 13, "Canteen seating is cramped at lunch on the fourth floor", "Canteen seating")
    rf.commit_and_index(repo, test_database)
    yield db
    killswitch.clear_cache()
