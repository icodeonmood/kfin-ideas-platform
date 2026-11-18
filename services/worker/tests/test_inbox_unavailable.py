"""C-INBOX-READER.reader and L-INBOX without a database (BLD-A195): when a tab holds items and not one of them can be
rendered (the demo's missing `comms/templates/inbox/`), the Inbox list is refused with `unavailable` (503), so the
web shows its unavailable line, never "Nothing here."; one item that fails still leaves the others; a failure is
logged with the item's id and kind only, never its words."""

from __future__ import annotations

import datetime as dt
import io
import json
from typing import Any

import pytest

from notify import inbox, render

USER = "6f1c2a9e-3b7d-4e0a-9c55-2f4b8d1e7a01"
NOW = dt.datetime(2026, 11, 18, 12, 0, tzinfo=dt.UTC)
SECRET = "Investors call to ask why a redemption was rejected"  # words that must never reach a log


class _Conn:
    """The two reads `inbox.items` makes: the tab's rows, then every tab's count."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def execute(self, *_: Any) -> _Conn:
        return self

    def fetchall(self) -> list[dict[str, Any]]:
        return self.rows

    def fetchone(self) -> dict[str, int]:
        n = len(self.rows)
        return {"all_": n, "needs_you": n, "unread": n, "archived": 0}


def _row(n: int, kind: str) -> dict[str, Any]:
    return {"id": n, "kind": kind, "payload": {}, "actions": [], "created_at": NOW}


def _lines(captured: io.StringIO, start: int) -> list[dict[str, Any]]:
    return [json.loads(line) for line in captured.getvalue()[start:].splitlines() if line.strip()]


def test_C_INBOX_READER_reader_a_tab_whose_items_all_fail_to_render_is_unavailable_not_empty(
    monkeypatch: pytest.MonkeyPatch, captured_logs: io.StringIO
) -> None:
    def broken(*_: Any, **__: Any) -> dict[str, Any]:
        raise FileNotFoundError(f"comms/templates/inbox/teamup_request.md: {SECRET}")

    monkeypatch.setattr(render, "item", broken)
    start = len(captured_logs.getvalue())
    with pytest.raises(inbox.InboxRefused) as refused:
        inbox.items(_Conn([_row(41, "teamup_request"), _row(42, "teamup_answer")]), USER, "all", NOW)  # type: ignore[arg-type]
    assert (refused.value.code, refused.value.status) == ("unavailable", 503)

    logged = _lines(captured_logs, start)
    failed = [line for line in logged if line["event"] == "notify.inbox_render_failed"]
    assert len(failed) == 2
    for line, (n, kind) in zip(failed, ((41, "teamup_request"), (42, "teamup_answer")), strict=True):
        assert line.get("notification_id") == n and line.get("inbox_kind") == kind
        assert line.get("error_type") == "FileNotFoundError"
    assert [line["inbox_tab"] for line in logged if line["event"] == "notify.inbox_unavailable"] == ["all"]
    assert SECRET not in captured_logs.getvalue()[start:]


def test_L_INBOX_one_item_that_fails_leaves_the_others_and_an_empty_tab_is_still_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def some(_conn: Any, row: dict[str, Any], *_: Any) -> dict[str, Any]:
        if row["kind"] == "teamup_request":
            raise KeyError("heading")
        return {"id": str(row["id"]), "kind": row["kind"]}

    monkeypatch.setattr(render, "item", some)
    got = inbox.items(_Conn([_row(41, "teamup_request"), _row(42, "stage_moved")]), USER, "all", NOW)  # type: ignore[arg-type]
    assert [it["id"] for it in got["items"]] == ["42"] and got["total"] == 2

    empty = inbox.items(_Conn([]), USER, "archived", NOW)  # type: ignore[arg-type]
    assert empty["items"] == [] and empty["total"] == 0  # the web says "Nothing here." for this one
