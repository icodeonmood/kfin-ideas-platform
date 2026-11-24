"""BLD-A251: a test that uses the `test_database` fixture is a stack test, marked or not. conftest's collection hook
gives it the `stack` mark, so `-m "not stack"` deselects it and a local run never creates a database on the stack's
Postgres (the live demo's). Collect-only runs no fixture, so these checks touch no database."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from tests import conftest

WORKER = Path(__file__).resolve().parents[1]


class _Item:
    def __init__(self, fixturenames: tuple[str, ...], marked: bool = False) -> None:
        self.fixturenames = fixturenames
        self.markers: list[Any] = [pytest.mark.stack.mark] if marked else []

    def get_closest_marker(self, name: str) -> Any:
        return next((m for m in self.markers if m.name == name), None)

    def add_marker(self, marker: Any) -> None:
        self.markers.append(marker.mark)


def test_bld_a251_a_test_on_test_database_gets_the_stack_mark_once() -> None:
    direct = _Item(("test_database",))
    through_db = _Item(("db", "test_database", "request"))
    already = _Item(("world", "db", "test_database"), marked=True)
    pure = _Item(("tmp_path", "monkeypatch"))
    conftest.pytest_collection_modifyitems(None, [direct, through_db, already, pure])  # type: ignore[arg-type, list-item]
    assert [m.name for m in direct.markers] == ["stack"]
    assert [m.name for m in through_db.markers] == ["stack"]
    assert [m.name for m in already.markers] == ["stack"]
    assert pure.markers == []


def _collect(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", *args],
        cwd=WORKER,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


def test_bld_a251_not_stack_deselects_an_unmarked_database_test_and_keeps_pure_ones() -> None:
    # test_sign_in_code_email.py has no stack mark; its tests use `db`, which needs `test_database`.
    unmarked = "tests/test_sign_in_code_email.py"
    every = _collect(unmarked)
    assert every.returncode == 0
    assert "test_sign_in_code_email.py::" in every.stdout
    local = _collect("-m", "not stack", unmarked)
    assert local.returncode == 5  # no tests collected: every one was deselected
    assert "test_sign_in_code_email.py::" not in local.stdout
    assert "deselected" in local.stdout
    # A pure unit file keeps every test under the same filter.
    pure = _collect("-m", "not stack", "tests/test_a251_stack_mark.py")
    assert pure.returncode == 0 and "deselected" not in pure.stdout
    assert (
        "test_a251_stack_mark.py::test_bld_a251_a_test_on_test_database_gets_the_stack_mark_once"
        in pure.stdout
    )
