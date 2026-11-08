"""Shared fixtures. Every log line written during the run is captured and scanned at the end (AT-B1-10)."""

from __future__ import annotations

import io
import logging
import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("APP_ENV", "test")

_CAPTURE = io.StringIO()


def pytest_configure(config: pytest.Config) -> None:
    from core import logging as klog

    handler = logging.StreamHandler(_CAPTURE)
    handler.setFormatter(klog._JsonFormatter())
    logging.getLogger().addHandler(handler)


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
    from tests import helpers

    try:
        name = helpers.create_database()
    except Exception as exc:
        pytest.fail(
            f"Postgres is not reachable on localhost:5432; run `make up` first ({type(exc).__name__})"
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
        "TRUNCATE outbox, ideas, idea_links, chunks, links, terms, repo_files, users, review_items "
        "RESTART IDENTITY CASCADE; "
        "UPDATE index_state SET last_commit = NULL; UPDATE kill_switches SET state = 'on'"
    )
    yield conn
    conn.close()


@pytest.fixture
def company_repo(tmp_path_factory: pytest.TempPathFactory) -> object:
    from tests import helpers

    return helpers.seeded_repo(tmp_path_factory.mktemp("repo") / "kfin-ideas")
