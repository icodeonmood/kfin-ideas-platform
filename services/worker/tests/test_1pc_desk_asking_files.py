"""The files on an answer as the sharer's set and the desk read them (`desk.asking._files`), without a database: a
link's `type` is "link", as E-ENTITIES FileItem and lane E's `FileItem` in api.ts read it; a file keeps its MIME type
(S-R3.rules/3, S-R2 answers under each part)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

from core.db import Conn
from desk import asking

ANSWER = "6f1d2c3b-4a5e-4f60-8172-93a4b5c6d7e8"


class _Rows:
    def __init__(self, rows: Sequence[dict[str, Any]]) -> None:
        self._rows = list(rows)

    def fetchall(self) -> list[dict[str, Any]]:
        return self._rows


class _Conn:
    """Answers the one SELECT `_files` makes with the rows given, and records what it was asked."""

    def __init__(self, rows: Sequence[dict[str, Any]]) -> None:
        self.rows = rows
        self.asked: list[tuple[str, tuple[Any, ...]]] = []

    def execute(self, sql: str, params: tuple[Any, ...]) -> _Rows:
        self.asked.append((sql, params))
        return _Rows(self.rows)


def _row(n: int, kind: str, name: str, mime: str | None, state: str = "checked") -> dict[str, Any]:
    return {
        "id": f"ATT-2026-{n:06d}",
        "answer_id": ANSWER,
        "kind": kind,
        "name": name,
        "mime": mime,
        "bytes": 0 if kind == "link" else 2048,
        "pages": None,
        "file_state": state,
        "hidden_note": None,
    }


def test_E_ENTITIES_files_FileItem_a_link_on_an_answer_has_type_link_and_a_file_its_mime_type() -> None:
    conn = _Conn(
        [
            _row(911, "link", "Rejection codes sheet", None),
            _row(912, "file", "sms-screenshot.png", "image/png"),
        ]
    )
    files = asking._files(cast(Conn, conn), [ANSWER])[ANSWER]
    assert [(f["kind"], f["type"]) for f in files] == [("link", "link"), ("file", "image/png")]
    assert files[0]["customer_detail"] is False
    assert conn.asked and conn.asked[0][1] == ([ANSWER],)


def test_E_ENTITIES_files_no_answers_asks_nothing() -> None:
    conn = _Conn([])
    assert asking._files(cast(Conn, conn), []) == {}
    assert conn.asked == []
