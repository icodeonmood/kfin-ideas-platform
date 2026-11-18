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
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def fetchone(self) -> dict[str, Any] | None:
        return self.rows[0] if self.rows else None

    def fetchall(self) -> list[dict[str, Any]]:
        return self.rows


class _Conn:
    """Records each savepoint and how it ended, and each statement's first words; `execute` fails, or answers the
    rows given for a table (none for any other)."""

    def __init__(self, *, fail: bool, rows: dict[str, list[dict[str, Any]]] | None = None) -> None:
        self.fail = fail
        self.rows = rows or {}
        self.savepoints: list[str] = []
        self.statements: list[str] = []

    @contextmanager
    def transaction(self) -> Iterator[None]:
        try:
            yield
        except BaseException:
            self.savepoints.append("rolled_back")
            raise
        self.savepoints.append("released")

    def execute(self, sql: str, *_: Any, **__: Any) -> _Result:
        self.statements.append(" ".join(sql.split()[:3]))
        if self.fail:
            raise RuntimeError("database error")
        table = next((t for t in self.rows if f"FROM {t} " in sql + " "), None)
        return _Result(self.rows[table] if table else [])


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

    assert match_shared(_Conn(fail=False), "u", found_while="sent") == -1  # type: ignore[arg-type]

    def broken(*_: Any, **__: Any) -> m.Run:  # anything else that escapes matching
        raise RuntimeError("index down")

    monkeypatch.setattr(m, "match_idea", broken)
    assert similar_for(_Conn(fail=False), "u", "A title", "A summary") is None  # type: ignore[arg-type]
    assert match_shared(_Conn(fail=False), "u", found_while="checking") == -1  # type: ignore[arg-type]


DRAFT = "3f1e0c1e-0000-4000-8000-000000000003"


def test_bld_c096_a_decrypt_failure_before_retrieval_is_a_failed_run_in_its_savepoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """L-SIMILAR.failure: the person's masked words cannot be opened (a key or decrypt error, before retrieval).
    The run fails inside its savepoint, the failure is recorded in a savepoint of its own, nothing is retrieved,
    and `match_shared` answers -1 ("couldn't check") without raising."""
    idea: dict[str, Any] = {
        "id": DRAFT, "idea_id": "IDEA-2026-000901", "contributor_code": "C-0901", "status": "checking",
        "kind": "problem", "title": "SIP failure SMS gives no reason", "summary": "", "area": None, "affects": [],
        "shared_at": None, "neutral_summary": None,
    }  # fmt: skip

    def cannot_open(*_: Any, **__: Any) -> str:
        raise ValueError("decrypt failed")

    def never(*_: Any, **__: Any) -> Any:
        raise AssertionError("retrieval must not run")

    monkeypatch.setattr(m, "open_text", cannot_open)
    monkeypatch.setattr(m, "retrieve", never)
    conn = _Conn(
        fail=False, rows={"ideas": [idea], "idea_messages": [{"id": 1, "text_encrypted": b"sealed"}]}
    )
    assert match_shared(conn, DRAFT, found_while="checking") == -1  # type: ignore[arg-type]
    assert conn.savepoints == ["rolled_back", "released"]  # the run rolled back; the failure recorded
    assert conn.statements[-1] == "INSERT INTO similar_runs"

    conn = _Conn(
        fail=False, rows={"ideas": [idea], "idea_messages": [{"id": 1, "text_encrypted": b"sealed"}]}
    )
    assert similar_for(conn, DRAFT, "SIP failure SMS gives no reason", "") is None  # type: ignore[arg-type]
    assert conn.savepoints == ["rolled_back", "released"]
