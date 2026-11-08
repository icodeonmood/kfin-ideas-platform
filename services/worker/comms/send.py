"""Send email and digests (§3.7 steps 6–7). Plain text only: no tracking pixels, no open tracking, links to the
app. `comms.email` off: emails stay queued; in-app messages carry on. A failing send retries three times, then
the notification is marked failed (the in-app copy is already there)."""

from __future__ import annotations

import datetime as dt
import smtplib
from email.message import EmailMessage
from typing import Any
from urllib.parse import urlparse

from comms.render import variables
from comms.route import next_send_time
from comms.templates import render
from core import killswitch
from core.config import get_settings
from core.db import Conn
from core.logging import get_logger

log = get_logger("comms.send")
FROM = "The Garage <garage@kfintech.example>"
MAX_ATTEMPTS = 3


def _smtp(to: str, subject: str, body: str) -> None:
    url = urlparse(get_settings().smtp_url)
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = FROM, to, subject
    msg.set_content(body)  # text/plain: nothing to track
    with smtplib.SMTP(url.hostname or "localhost", url.port or 25, timeout=10) as s:
        s.send_message(msg)


def message_for(
    conn: Conn, user_id: str, event: str, template: str, refs: dict[str, Any]
) -> tuple[str, str, str]:
    return render(template, variables(conn, user_id, event, refs))


def send_due(conn: Conn, now: dt.datetime | None = None, limit: int = 50) -> int:
    if not killswitch.is_on("comms.email", conn):
        return 0
    now = now or dt.datetime.now(dt.UTC)
    sent = 0
    with conn.transaction():
        rows = conn.execute(
            "SELECT n.id, n.user_id, n.event, n.template, n.payload, n.attempts, u.email FROM notifications n "
            "JOIN users u ON u.id = n.user_id WHERE n.channel = 'email' AND n.state = 'queued' AND n.send_after <= %s "
            "ORDER BY n.send_after, n.id LIMIT %s FOR UPDATE OF n SKIP LOCKED",
            (now, limit),
        ).fetchall()
        for r in rows:
            try:
                subject, body, _ = message_for(
                    conn, str(r["user_id"]), r["event"], r["template"], r["payload"]
                )
                _smtp(r["email"], subject, body)
            except Exception as exc:
                failed = r["attempts"] + 1 >= MAX_ATTEMPTS
                conn.execute(
                    "UPDATE notifications SET attempts = attempts + 1, state = %s, error_code = %s, "
                    "send_after = now() + interval '5 minutes' WHERE id = %s",
                    ("failed" if failed else "queued", type(exc).__name__.lower()[:60], r["id"]),
                )
                log.warning("comms.send_failed", notification_id=r["id"], error_type=type(exc).__name__)
                continue
            conn.execute("UPDATE notifications SET state = 'sent', sent_at = now() WHERE id = %s", (r["id"],))
            sent += 1
    if sent:
        log.info("comms.sent", sent_count=sent)
    return sent


def send_digests(conn: Conn, now: dt.datetime | None = None) -> int:
    """One email per person with every held routine message, inside working hours only."""
    if not killswitch.is_on("comms.email", conn):
        return 0
    now = now or dt.datetime.now(dt.UTC)
    if next_send_time(now, "routine") != now:
        return 0
    users = conn.execute(
        "SELECT DISTINCT n.user_id, u.email FROM notifications n JOIN users u ON u.id = n.user_id "
        "WHERE n.channel = 'digest' AND n.state = 'held'"
    ).fetchall()
    count = 0
    for u in users:
        items = conn.execute(
            "SELECT id, event, template, payload FROM notifications WHERE user_id = %s AND channel = 'digest' "
            "AND state = 'held' ORDER BY created_at",
            (u["user_id"],),
        ).fetchall()
        parts = []
        for it in items:
            subject, body, _ = message_for(
                conn, str(u["user_id"]), it["event"], it["template"], it["payload"]
            )
            parts.append(f"## {subject}\n\n{body}")
        _smtp(u["email"], f"Your Garage update: {len(parts)} new", "\n\n".join(parts))
        conn.execute(
            "UPDATE notifications SET state = 'sent', sent_at = now() WHERE id = ANY(%s)",
            ([it["id"] for it in items],),
        )
        count += 1
    if count:
        log.info("comms.batched_sent", person_count=count)
    return count
