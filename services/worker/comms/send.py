"""Send email and digests (§3.7 steps 6–7). Each email carries a plain-text part and a branded HTML part (DEC-061,
BLD-125): no tracking pixels, no open tracking, links to the app. `comms.email` off: emails stay queued; in-app messages carry on. A failing send retries three times, then
the notification is marked failed (the in-app copy is already there)."""

from __future__ import annotations

import datetime as dt
import smtplib
from email.message import EmailMessage
from typing import Any
from urllib.parse import urlparse

from comms import email_html
from comms.render import variables
from comms.route import IST, next_send_time
from comms.templates import load, render
from core import killswitch
from core.config import get_settings
from core.db import Conn
from core.logging import get_logger
from rules import load_rule

log = get_logger("comms.send")
FROM = "1% Club <onepercentclub@kfintech.example>"
MAX_ATTEMPTS = 3


def build_message(to: str, email: email_html.Email) -> EmailMessage:
    """multipart/alternative: the plain-text part first, the HTML part second (mail apps show the last one they
    can render)."""
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = FROM, to, email.subject
    msg.set_content(email.text)
    msg.add_alternative(email.html, subtype="html")
    return msg


def _smtp(to: str, email: email_html.Email) -> None:
    url = urlparse(get_settings().smtp_url)
    with smtplib.SMTP(url.hostname or "localhost", url.port or 25, timeout=10) as s:
        s.send_message(build_message(to, email))


def compose(conn: Conn, user_id: str, event: str, template: str, refs: dict[str, Any]) -> email_html.Email:
    base = get_settings().app_base_url
    if event == "ember.issue":  # the whole issue, as sent (BLD-128); the in-app copy is the short template
        from ember.render import compose as ember_email

        row = conn.execute(
            "SELECT id, content FROM ember_issues WHERE id = %s AND state = 'sent'", (refs.get("issue_id"),)
        ).fetchone()
        if row is None:
            raise LookupError("ember_issue_missing")
        return ember_email(row["content"], base, f"{base.rstrip('/')}/ember/{row['id']}")
    data = variables(conn, user_id, event, refs)
    return email_html.compose(load(template), data, base)


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
        _drop_inactive(conn)
        rows = conn.execute(
            "SELECT n.id, n.user_id, n.event, n.template, n.payload, n.attempts, n.urgency, u.email "
            "FROM notifications n JOIN users u ON u.id = n.user_id WHERE n.channel = 'email' AND n.state = 'queued' "
            "AND n.send_after <= %s AND u.active ORDER BY n.send_after, n.id LIMIT %s FOR UPDATE OF n SKIP LOCKED",
            (now, limit),
        ).fetchall()
        for r in rows:
            paused = (r["event"] == "ones.announced" and not killswitch.is_on("ones.public", conn)) or (
                r["event"] == "ember.issue"
                and not (killswitch.is_on("ember.send", conn) and killswitch.is_on("ones.public", conn))
            )
            if paused:
                # The Ones are off the wall, or The Ember is paused: the message waits instead of failing.
                conn.execute(
                    "UPDATE notifications SET send_after = %s WHERE id = %s",
                    (now + dt.timedelta(minutes=15), r["id"]),
                )
                continue
            if r["urgency"] == "routine" and _hold_back(conn, r, now):
                continue
            try:
                _smtp(r["email"], compose(conn, str(r["user_id"]), r["event"], r["template"], r["payload"]))
            except Exception as exc:
                failed = r["attempts"] + 1 >= MAX_ATTEMPTS
                conn.execute(
                    "UPDATE notifications SET attempts = attempts + 1, state = %s, error_code = %s, "
                    "send_after = now() + interval '5 minutes' WHERE id = %s",
                    ("failed" if failed else "queued", type(exc).__name__.lower()[:60], r["id"]),
                )
                log.warning("comms.send_failed", notification_id=r["id"], error_type=type(exc).__name__)
                continue
            conn.execute(
                "UPDATE notifications SET state = 'sent', sent_at = %s WHERE id = %s", (now, r["id"])
            )
            sent += 1
    if sent:
        log.info("comms.sent", sent_count=sent)
    return sent


def _drop_inactive(conn: Conn) -> None:
    """People who have left get nothing by email, even mail queued while they were here (B6 review)."""
    conn.execute(
        "UPDATE notifications n SET state = 'failed', error_code = 'recipient_inactive' FROM users u "
        "WHERE u.id = n.user_id AND NOT u.active AND n.channel IN ('email', 'digest') AND n.state IN ('queued', 'held')"
    )


def _hold_back(conn: Conn, r: dict[str, Any], now: dt.datetime) -> bool:
    """Routine mail is checked again at send time: a backlog (say, `comms.email` back on at night) still waits for
    working hours, and a second routine email on the same day goes to the digest instead."""
    at = next_send_time(now, "routine")
    if at != now:
        conn.execute("UPDATE notifications SET send_after = %s WHERE id = %s", (at, r["id"]))
        return True
    cap = int(
        (load_rule(get_settings().company_repo_path, "comms").data.get("limits") or {}).get(
            "non_urgent_emails_per_person_per_day", 1
        )
    )
    sent = conn.execute(
        "SELECT count(*) AS n FROM notifications WHERE user_id = %s AND channel = 'email' AND urgency = 'routine' "
        "AND state IN ('sent', 'read') AND (sent_at AT TIME ZONE 'Asia/Kolkata')::date = %s",
        (r["user_id"], now.astimezone(IST).date()),
    ).fetchone()
    if sent and int(sent["n"]) >= cap:
        conn.execute("UPDATE notifications SET channel = 'digest', state = 'held' WHERE id = %s", (r["id"],))
        return True
    return False


def send_digests(conn: Conn, now: dt.datetime | None = None) -> int:
    """One email per person with every held routine message, inside working hours only."""
    if not killswitch.is_on("comms.email", conn):
        return 0
    now = now or dt.datetime.now(dt.UTC)
    if next_send_time(now, "routine") != now:
        return 0
    with conn.transaction():
        _drop_inactive(conn)
    users = conn.execute(
        "SELECT DISTINCT n.user_id, u.email FROM notifications n JOIN users u ON u.id = n.user_id "
        "WHERE n.channel = 'digest' AND n.state = 'held' AND u.active"
    ).fetchall()
    count = 0
    for u in users:
        try:
            with conn.transaction():
                count += _send_digest(conn, u)
        except Exception as exc:  # one person's failure must not hold back everyone else's digest
            log.warning("comms.batched_failed", error_type=type(exc).__name__)
    if count:
        log.info("comms.batched_sent", person_count=count)
    return count


def _send_digest(conn: Conn, u: dict[str, Any]) -> int:
    items = conn.execute(
        "SELECT id, event, template, payload FROM notifications WHERE user_id = %s AND channel = 'digest' "
        "AND state = 'held' ORDER BY created_at FOR UPDATE SKIP LOCKED",
        (u["user_id"],),
    ).fetchall()
    if not items:
        return 0
    sections = [
        (load(it["template"]), variables(conn, str(u["user_id"]), it["event"], it["payload"])) for it in items
    ]
    _smtp(u["email"], email_html.digest(sections, get_settings().app_base_url))
    conn.execute(
        "UPDATE notifications SET state = 'sent', sent_at = now() WHERE id = ANY(%s)",
        ([it["id"] for it in items],),
    )
    return 1
