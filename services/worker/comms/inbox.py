"""The in-app inbox (§3.7): every message lands here, rendered for the person viewing it."""

from __future__ import annotations

from typing import Any

from comms.send import message_for
from core.db import Conn
from core.logging import get_logger

log = get_logger("comms.inbox")


def inbox(conn: Conn, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, event, template, payload, created_at, read_at FROM notifications WHERE user_id = %s "
        "AND channel = 'in_app' ORDER BY created_at DESC, id DESC LIMIT %s",
        (user_id, limit),
    ).fetchall()
    out = []
    for r in rows:
        try:
            subject, body, _ = message_for(conn, user_id, r["event"], r["template"], r["payload"])
        except Exception as exc:  # one message we cannot show must not hide all the others
            log.warning("comms.inbox_render_failed", notification_id=r["id"], error_type=type(exc).__name__)
            subject, body = "A message we can't show just now", "Please look again later.\n"
        out.append(
            {
                "id": r["id"],
                "subject": subject,
                "body": body,
                "at": r["created_at"].isoformat(),
                "read": r["read_at"] is not None,
            }
        )
    return out


def mark_read(conn: Conn, user_id: str, notification_id: int) -> bool:
    return (
        conn.execute(
            "UPDATE notifications SET read_at = coalesce(read_at, now()), state = CASE WHEN state = 'sent' "
            "THEN 'read' ELSE state END WHERE id = %s AND user_id = %s AND channel = 'in_app'",
            (notification_id, user_id),
        ).rowcount
        == 1
    )
