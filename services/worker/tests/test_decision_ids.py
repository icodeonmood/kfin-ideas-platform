"""BLD-A161: decision IDs stay unique while several sessions add them in parallel."""

import subprocess
import sys
from pathlib import Path

import pytest

from tests import helpers

SCRIPT = helpers.ROOT / "scripts" / "ci" / "check_decision_ids.py"

LANES = "| Lane | Work |\n|---|---|\n| A | Lead build |\n| B | Parallel build |\n| C | Features |\n"
ROWS = (
    "| ID | Decision |\n|---|---|\n"
    "| DEC-001 | One |\n| DEC-002 | Two |\n"
    "| BLD-007 | Day one |\n| BLD-160 | Lane A's last plain number |\n| BLD-229 | Lane B's last plain number |\n"
    "| D1 | A dependency row, not a decision ID |\n"
)


def _run(tmp_path: Path, extra: str = "", lanes: str = LANES) -> subprocess.CompletedProcess[str]:
    path = tmp_path / "DECISIONS.md"
    path.write_text(f"# Decisions\n\n{lanes}\n{ROWS}{extra}", encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(path)], capture_output=True, text=True, check=False
    )


def test_the_repo_itself_is_clean() -> None:
    result = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "extra",
    [
        "| BLD-A161 | Lane A carries on |\n| BLD-B230 | Lane B carries on |\n",
        "| BLD-C001 | A new lane starts at one |\n| BLD-C002 | And counts on |\n",
        "| DEC-096 | The next product decision |\n",
    ],
)
def test_lettered_build_ids_and_the_next_dec_pass(tmp_path: Path, extra: str) -> None:
    assert _run(tmp_path, extra).returncode == 0


@pytest.mark.parametrize(
    ("extra", "says"),
    [
        ("| DEC-002 | Two sessions took the same number |\n", "already used"),
        ("| BLD-C001 | x |\n| BLD-C001 | y |\n", "already used"),
        ("| BLD-C001 | x |\n| BLD-C0001 | the same number, padded |\n", "already used"),
        ("| BLD-161 | Lane A forgot its letter |\n", "no lane letter"),
        ("| BLD-230 | Lane B forgot its letter |\n", "no lane letter"),
        ("| BLD-300 | A new lane used a plain range |\n", "no lane letter"),
        ("| BLD-E001 | A lane nobody registered |\n", "not in the lanes table"),
        ("| BLD-A157 | Lettered, but inside the plain numbers |\n", "carries on from BLD-A161"),
        ("| BLD-B229 | Lettered, but inside the plain numbers |\n", "carries on from BLD-B230"),
        ("| BLD-c001 | Lower-case lane |\n", "not a decision ID"),
        ("| DEC-96 | Too short |\n", "not a decision ID"),
    ],
)
def test_clashes_and_malformed_ids_fail(tmp_path: Path, extra: str, says: str) -> None:
    result = _run(tmp_path, extra)
    assert result.returncode == 1
    assert says in result.stderr


def test_a_lane_letter_registered_twice_fails(tmp_path: Path) -> None:
    result = _run(tmp_path, lanes=LANES + "| C | Design |\n")
    assert result.returncode == 1
    assert "registered twice" in result.stderr
