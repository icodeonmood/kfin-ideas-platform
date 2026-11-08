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
