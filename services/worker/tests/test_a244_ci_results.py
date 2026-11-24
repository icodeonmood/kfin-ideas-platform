"""BLD-A244: CI keeps the go/no-go CI report (ARCHITECTURE §9.3, "Every B1-B7 acceptance test passes"): with
TEST_RESULTS set, `make test` and `make e2e` also write JUnit XML there, and the gates job uploads that folder and the
golden-set reports as `test-results` on every run. Unset, the targets run as before. File reads and `make -n` only."""

from __future__ import annotations

import shutil
import subprocess
from typing import Any

import pytest
import yaml

from tests import helpers

ROOT = helpers.ROOT


def _dry(*args: str) -> str:
    make = shutil.which("make")
    if make is None:
        pytest.skip("no make on this machine")
    return subprocess.run(
        [make, "-n", "-C", str(ROOT), *args], capture_output=True, text=True, check=True, timeout=60
    ).stdout


def test_bld_a244_test_targets_write_junit_only_when_test_results_is_set() -> None:
    plain = _dry("test-py", "test-web", "TEST_RESULTS=")
    assert "pytest -q" in plain and "npx vitest run" in plain
    assert "junit" not in plain
    out = _dry("test-py", "test-web", "TEST_RESULTS=/ci/test-results")
    assert "pytest -q --junitxml=/ci/test-results/pytest.xml" in out
    assert (
        "npx vitest run --reporter=default --reporter=junit --outputFile.junit=/ci/test-results/vitest.xml"
        in out
    )
    make = (ROOT / "Makefile").read_text("utf-8")
    assert '$(if $(TEST_RESULTS),E2E_JUNIT_FILE="$(TEST_RESULTS)/e2e.xml")' in make
    config = (ROOT / "apps" / "web" / "playwright.config.ts").read_text("utf-8")
    assert '["junit", { outputFile: process.env.E2E_JUNIT_FILE }]' in config
    assert ': [["list"]],' in config  # without it, the reporter is as before


def test_bld_a244_gates_upload_the_test_results_on_every_run_and_no_container_log() -> None:
    ci: dict[str, Any] = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text("utf-8"))
    gates = ci["jobs"]["gates"]
    assert gates["env"]["TEST_RESULTS"] == "${{ github.workspace }}/test-results"
    names = [s.get("name") for s in gates["steps"]]
    keep = gates["steps"][names.index("Keep the test results (the go/no-go CI report)")]
    assert keep["if"] == "always()"
    assert keep["uses"] == "actions/upload-artifact@v4"
    assert keep["with"]["name"] == "test-results"
    assert keep["with"]["path"].split() == ["test-results/", "eval/reports/*.json"]
    assert keep["with"]["retention-days"] == 30
    assert "container.log" not in keep["with"]["path"]
    # The report is kept after every test step has run, and the log check still comes first.
    assert names.index("Golden sets") < names.index("Keep the test results (the go/no-go CI report)")
    assert names.index("Container logs carry no idea text or personal data") < names.index(
        "Keep the test results (the go/no-go CI report)"
    )
