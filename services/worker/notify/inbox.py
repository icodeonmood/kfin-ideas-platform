"""L-INBOX: the one list of what waits on a person and what changed (S-H5, A-API.inbox).

The Inbox holds the typed items `notify.post` writes, one per E-ENUMS.inbox kind (L-INBOX.kinds). In-app messages
the old routes still write (`comms.route`, kind NULL: a new One, a tier change, The Ember) are not Inbox items:
they keep going out by email, and a new One gets no Inbox item at launch (BLD-A186, BLD-A202). The tab counts, the
unread total for the sidebar and Home's "Needs you" come from the same rows, so they always agree (L-INBOX.rules/1,
V-ACC.track/8).
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Literal

from core.db import Conn
from core.logging import get_logger
from notify import render

log = get_logger("notify.inbox")

Tab = Literal["all", "needs_you", "unread", "archived"]
TABS: tuple[Tab, ...] = ("all", "needs_you", "unread", "archived")
LIMIT = 200  # newest first; older items stay in the database

_COLUMNS = (
    "id, user_id, kind, event, template, payload, created_at, read_at, archived_at, needs_you, resolved_at, due_at, "
    "from_user_id, idea_uuid, actions, dedupe_key"
)
_OPEN = "n.needs_you AND n.resolved_at IS NULL"
_ITEM = "n.channel = 'in_app' AND n.kind IS NOT NULL"  # an Inbox item (BLD-A202)
_WHERE = {
    "all": "n.archived_at IS NULL",
    "needs_you": f"n.archived_at IS NULL AND {_OPEN}",
    "unread": "n.archived_at IS NULL AND n.read_at IS NULL",
    "archived": "n.archived_at IS NOT NULL",
}


class InboxRefused(Exception):
    def __init__(self, code: str, status: int = 409) -> None:
        super().__init__(code)
        self.code, self.status = code, status


def counts(conn: Conn, user_id: str) -> dict[str, int]:
    """Per-tab counts. `unread` is the sidebar and tab-bar number; `needs_you` is Home's total."""
    row = conn.execute(
        "SELECT count(*) FILTER (WHERE " + _WHERE["all"] + ") AS all_, "
        "count(*) FILTER (WHERE " + _WHERE["needs_you"] + ") AS needs_you, "
        "count(*) FILTER (WHERE " + _WHERE["unread"] + ") AS unread, "
        "count(*) FILTER (WHERE " + _WHERE["archived"] + ") AS archived "
        "FROM notifications n WHERE n.user_id = %s AND " + _ITEM,
        (user_id,),
    ).fetchone()
    assert row is not None
    return {
        "all": int(row["all_"]),
        "needs_you": int(row["needs_you"]),
        "unread": int(row["unread"]),
        "archived": int(row["archived"]),
    }


def _render(conn: Conn, row: dict[str, Any], user_id: str, now: dt.datetime) -> dict[str, Any] | None:
    try:
        return render.item(conn, row, user_id, now)
    except Exception as exc:  # one item we cannot show must not hide all the others
        # IDs and the kind only: never the item's words, nor the exception's text (non-negotiable 3).
        log.warning(
            "notify.inbox_render_failed",
            notification_id=row["id"],
            inbox_kind=str(row.get("kind") or ""),
            error_type=type(exc).__name__,
        )
        return None


def items(conn: Conn, user_id: str, tab: str = "all", now: dt.datetime | None = None) -> dict[str, Any]:
    """`GET /inbox`: the tab's items, newest first, with every tab's count and the unread total (A-API.inbox). An
    item that cannot be rendered is left out; when that leaves none of the tab's items, it is refused with
    `unavailable` (503), so the web shows the Inbox's unavailable line instead of an empty list."""
    if tab not in TABS:
        raise InboxRefused("bad_tab", 400)
    now = now or dt.datetime.now(dt.UTC)
    sql = f"SELECT {_COLUMNS} FROM notifications n WHERE n.user_id = %s AND {_ITEM} AND {_WHERE[tab]} "  # noqa: S608 (fixed lists)
    rows = conn.execute(
        sql + "ORDER BY n.created_at DESC, n.id DESC LIMIT %s",
        (user_id, LIMIT),
    ).fetchall()
    out = [it for it in (_render(conn, dict(r), user_id, now) for r in rows) if it is not None]
    if rows and not out:
        # The tab holds items and not one of them could be shown (the demo's missing `comms/templates/inbox/`):
        # the Inbox says it cannot load just now, never "Nothing here." (C-INBOX-READER.reader, BLD-A195).
        log.warning("notify.inbox_unavailable", inbox_tab=tab, item_count=len(rows))
        raise InboxRefused("unavailable", 503)
    c = counts(conn, user_id)
    return {"items": out, "total": c[tab], "counts": c, "unread": c["unread"]}


def needs_you(conn: Conn, user_id: str, top: int = 2, now: dt.datetime | None = None) -> dict[str, Any]:
    """Home's "Needs you": the total and the first items, soonest due first (L-INBOX.rules/1)."""
    now = now or dt.datetime.now(dt.UTC)
    sql = (
        f"SELECT {_COLUMNS} FROM notifications n WHERE n.user_id = %s AND {_ITEM} AND {_WHERE['needs_you']} "  # noqa: S608 (fixed lists)
    )
    rows = conn.execute(
        sql + "ORDER BY n.due_at NULLS LAST, n.created_at DESC LIMIT %s",
        (user_id, top),
    ).fetchall()
    shown = [it for it in (_render(conn, dict(r), user_id, now) for r in rows) if it is not None]
    return {"total": counts(conn, user_id)["needs_you"], "top": shown}


def _own(conn: Conn, user_id: str, item_id: int) -> dict[str, Any]:
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM notifications n WHERE n.id = %s AND n.user_id = %s AND {_ITEM}",  # noqa: S608
        (item_id, user_id),
    ).fetchone()
    if row is None:
        raise InboxRefused("not_found", 404)
    return dict(row)


def mark_read(conn: Conn, user_id: str, item_id: int) -> dict[str, int]:
    """Opening an item in the reader marks it read (L-INBOX.rules/3); every count comes back with it."""
    _own(conn, user_id, item_id)
    conn.execute(
        "UPDATE notifications SET read_at = coalesce(read_at, now()), state = CASE WHEN state = 'sent' THEN 'read' "
        "ELSE state END WHERE id = %s AND user_id = %s",
        (item_id, user_id),
    )
    return counts(conn, user_id)


def mark_unread(conn: Conn, user_id: str, item_id: int) -> dict[str, int]:
    _own(conn, user_id, item_id)
    conn.execute(
        "UPDATE notifications SET read_at = NULL, state = CASE WHEN state = 'read' THEN 'sent' ELSE state END "
        "WHERE id = %s AND user_id = %s",
        (item_id, user_id),
    )
    return counts(conn, user_id)


def mark_all_read(conn: Conn, user_id: str) -> dict[str, int]:
    sql = f"UPDATE notifications n SET read_at = now(), state = CASE WHEN state = 'sent' THEN 'read' ELSE state END WHERE n.user_id = %s AND {_ITEM} AND n.read_at IS NULL AND n.archived_at IS NULL"  # noqa: S608 (fixed text)
    conn.execute(sql, (user_id,))
    return counts(conn, user_id)


def archive(conn: Conn, user_id: str, item_id: int) -> dict[str, int]:
    """Archiving hides an item from All; an item that still needs the person cannot be archived (L-INBOX.rules/5).
    An archived item counts as read, so the unread number never includes something out of sight."""
    row = _own(conn, user_id, item_id)
    if row["needs_you"] and row["resolved_at"] is None:
        raise InboxRefused("needs_you")
    conn.execute(
        "UPDATE notifications SET archived_at = coalesce(archived_at, now()), read_at = coalesce(read_at, now()), "
        "state = CASE WHEN state = 'sent' THEN 'read' ELSE state END WHERE id = %s AND user_id = %s",
        (item_id, user_id),
    )
    return counts(conn, user_id)


def action(conn: Conn, user_id: str, item_id: int, op: str) -> dict[str, Any]:
    """`POST /inbox/:id/actions/:op`: run one of the item's server operations (a request's Decline, Team up only or
    Merge it) through the lane that owns it (`notify.ops`). The item must offer that op."""
    from notify import ops

    row = _own(conn, user_id, item_id)
    offered = {str(a.get("op")) for a in (row.get("actions") or []) if a.get("op")}
    if op not in offered:
        raise InboxRefused("not_offered", 404)
    handler = ops.handler(str(row["kind"]), op)
    if handler is None:
        raise InboxRefused("not_available")
    result = handler(conn, user_id, row)
    return {"result": result, "counts": counts(conn, user_id)}
