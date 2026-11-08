"""AT-B1-10 (stack half): the running web and worker containers' logs pass the log scrubber.

The checker itself is proven in test_log_scrubber.py; every log line from this test run is scanned in
conftest.py. Here the same checker reads the containers' own output.
"""

import subprocess

import pytest

from pii.log_rules import scan_log_lines
from tests import helpers

pytestmark = pytest.mark.stack


def test_container_logs_are_clean() -> None:
    out = subprocess.run(
        [*helpers.COMPOSE, "logs", "--no-color", "--no-log-prefix", "worker", "web"],
        cwd=helpers.ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert out.returncode == 0
    lines = out.stdout.splitlines()
    assert lines, "expected some log output from the running services"
    violations = scan_log_lines(lines)
    assert violations == [], [f"{v.line_no}:{v.kind}:{v.where}" for v in violations[:10]]
