"""The lead's three answers as Inbox buttons (BLD-F028, agreed with lanes A and E; L-TEAMUP.rules/5–6, S-H2B).

A `teamup_request` item offers the ops `decline`, `team_only` and `merge` (`requests.tell_lead`). Lane A's Inbox
checks the item is the person's and offers that op, then hands it to the handler registered here in its registry
(`notify.ops`). Each handler reads `refs.request_id` from the item and answers through `requests.answer`, the same
path and checks as `POST /team-up/:id/answer`, with no reason (a decline's reason is optional, L-TEAMUP.rules/5),
and returns the same dict. A refusal is audited there, exactly as on the route, then raised as lane A's
`InboxRefused` with the same code and status (the original is its cause), so the Inbox answers it as a refusal.

Lane A's registry may not be loaded yet (it lands after lane F): `register` then does nothing, and lane A's Inbox
answers `not_available` until it is.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.db import Conn
    from teamup.rules import Answer
    from teamup.store import Refused

KIND = "teamup_request"


def request_id_of(item_row: dict[str, Any]) -> str:
    """`refs.request_id` from lane A's item row (its refs are stored as the row's `payload`)."""
    refs = item_row.get("refs")
    if not isinstance(refs, dict):
        refs = item_row.get("payload")
    rid = refs.get("request_id") if isinstance(refs, dict) else None
    return rid if isinstance(rid, str) else ""


def _module(name: str) -> Any:
    try:
        return importlib.import_module(name)
    except ImportError:
        return None


def _inbox_refusal(exc: Refused) -> Exception | None:
    inbox = _module("notify.inbox")
    cls = getattr(inbox, "InboxRefused", None) if inbox is not None else None
    return cls(exc.code, exc.status) if cls is not None else None


def _answer(conn: Conn, user_id: str, item_row: dict[str, Any], ans: Answer) -> dict[str, Any]:
    from teamup import requests
    from teamup.store import Refused

    try:
        return requests.answer(conn, request_id_of(item_row), user_id, {"answer": ans})
    except Refused as exc:
        refusal = _inbox_refusal(exc)
        if refusal is None:
            raise
        raise refusal from exc


def decline(conn: Conn, user_id: str, item_row: dict[str, Any]) -> dict[str, Any]:
    return _answer(conn, user_id, item_row, "decline")


def team_only(conn: Conn, user_id: str, item_row: dict[str, Any]) -> dict[str, Any]:
    return _answer(conn, user_id, item_row, "team_only")


def merge(conn: Conn, user_id: str, item_row: dict[str, Any]) -> dict[str, Any]:
    return _answer(conn, user_id, item_row, "merge")


HANDLERS: dict[str, Callable[[Conn, str, dict[str, Any]], dict[str, Any]]] = {
    "decline": decline,
    "team_only": team_only,
    "merge": merge,
}


def register() -> bool:
    """Register the three handlers in lane A's Inbox registry, if it is loaded. Idempotent."""
    inbox_ops = _module("notify.ops")
    if inbox_ops is None or not hasattr(inbox_ops, "register"):
        return False
    for op, fn in HANDLERS.items():
        inbox_ops.register(KIND, op)(fn)
    return True
