"""The two L-SIMILAR entry points other lane C modules import (BLD-C093): c/draft's `draft/adapters.py` calls
`similar_for`, c/sort-submit's `submit/adapters.py` calls `match_shared`. A rename or a signature change breaks this
branch, not theirs. So does a change to what they answer when matching cannot run (BLD-C096)."""

from __future__ import annotations

import inspect
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest

import similar
from similar import match_shared, similar_for
from similar import matching as m


def test_bld_c093_entry_points_keep_their_names_and_signatures() -> None:
    """L-SIMILAR.rules/4-5: the draft part and the send call keep their names."""
    assert set(similar.__all__) >= {"similar_for", "match_shared"}

    sig = inspect.signature(similar_for)
    assert list(sig.parameters) == ["conn", "idea_uuid", "title", "summary"]
    assert all(p.kind is p.POSITIONAL_OR_KEYWORD for p in sig.parameters.values())
    assert sig.return_annotation == "list[dict[str, Any]] | None"

    sig = inspect.signature(match_shared)
    assert list(sig.parameters) == ["conn", "idea_uuid", "found_while"]
    assert sig.parameters["found_while"].kind is inspect.Parameter.KEYWORD_ONLY
    assert sig.return_annotation == "int"


# ---- What the entry points answer when matching cannot run (BLD-C096). No database: a stand-in connection
# counts the savepoints and fails where it is told to.


class _Result:
    def __init__(self, row: dict[str, Any] | None) -> None:
        self.row = row

    def fetchone(self) -> dict[str, Any] | None:
        return self.row


class _Conn:
    """Records each savepoint and how it ended; `execute` fails, or finds no row."""

    def __init__(self, *, fail: bool) -> None:
        self.fail = fail
        self.savepoints: list[str] = []

    @contextmanager
    def transaction(self) -> Iterator[None]:
        try:
            yield
        except BaseException:
            self.savepoints.append("rolled_back")
            raise
        self.savepoints.append("released")

    def execute(self, *_: Any, **__: Any) -> _Result:
        if self.fail:
            raise RuntimeError("database error")
        return _Result(None)


def test_bld_c096_match_idea_runs_the_lookup_in_a_savepoint() -> None:
    """L-SIMILAR.failure: an error while reading the draft is a failed run, rolled back to its savepoint; an
    unknown ID is IdeaNotFound (a LookupError), also rolled back, so the caller's transaction is never aborted."""
    broken = _Conn(fail=True)
    assert m.match_idea(broken, "3f1e0c1e-0000-4000-8000-000000000001").state == "failed"  # type: ignore[arg-type]
    assert broken.savepoints == ["rolled_back", "rolled_back"]  # the run, then recording the failure

    empty = _Conn(fail=False)
    with pytest.raises(m.IdeaNotFound):
        m.match_idea(empty, "3f1e0c1e-0000-4000-8000-000000000002")  # type: ignore[arg-type]
    assert empty.savepoints == ["rolled_back"]


def test_bld_c096_entry_points_answer_none_and_minus_one_and_never_raise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """L-SIMILAR.failure, L-SIMILAR.rules/4-5: an unknown draft or a failed run is None from `similar_for` and -1
    ("couldn't check") from `match_shared`; so is a database error while reading the matches back."""

    def not_found(*_: Any, **__: Any) -> m.Run:
        raise m.IdeaNotFound("idea_not_found")

    monkeypatch.setattr(m, "match_idea", not_found)
    assert similar_for(_Conn(fail=True), "u", "A title", "A summary") is None  # type: ignore[arg-type]
    assert match_shared(_Conn(fail=True), "u", found_while="checking") == -1  # type: ignore[arg-type]

    monkeypatch.setattr(m, "match_idea", lambda *_, **__: m.Run("failed"))
    assert similar_for(_Conn(fail=True), "u", "A title", "A summary") is None  # type: ignore[arg-type]
    assert match_shared(_Conn(fail=True), "u", found_while="later") == -1  # type: ignore[arg-type]

    monkeypatch.setattr(m, "match_idea", lambda *_, **__: m.Run("done", 2, "code"))
    reading = _Conn(fail=True)
    assert similar_for(reading, "u", "A title", "A summary") is None  # type: ignore[arg-type]
    assert reading.savepoints == ["rolled_back"]
    assert match_shared(_Conn(fail=True), "u", found_while="later") == 2  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        match_shared(_Conn(fail=False), "u", found_while="sent")  # type: ignore[arg-type]
