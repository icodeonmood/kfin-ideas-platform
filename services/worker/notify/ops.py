"""Server operations an Inbox item can offer as a button (E-ENTITIES `Action.op`), registered by the lane that owns
them: lane F registers a team-up request's `decline`, `team_only` and `merge`. The Inbox only checks the item is the
person's and offers that op, then hands over; the owning lane checks everything else and posts any reply itself.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from core.db import Conn

Handler = Callable[[Conn, str, dict[str, Any]], dict[str, Any]]
_OPS: dict[tuple[str, str], Handler] = {}


def register(kind: str, op: str) -> Callable[[Handler], Handler]:
    """`@register("teamup_request", "merge")` over `fn(conn, user_id, item_row) -> dict`."""

    def wrap(fn: Handler) -> Handler:
        _OPS[(kind, op)] = fn
        return fn

    return wrap


def handler(kind: str, op: str) -> Handler | None:
    return _OPS.get((kind, op))
