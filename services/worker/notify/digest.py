"""The decide-by digest (L-REVIEW.clock/3, `NOT DRAWN:` default; BLD-A203): once a working day, an email to the
review desk lead listing the ideas past their decide-by date that are still with the desk. No automatic decision.

There is no "review desk lead" role in the pack's roles (E-ENUMS.roles), so the digest goes to every reviewer until
one is named. It is queued by the scheduled `comms.digest` job and sent by `comms.send.send_due`, so it has the same
retries and email switch as every other message; it lists the ideas as they are when it is sent. Each person gets at
most one a day (the dedupe key holds the date).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import replace
from typing import Any

from psycopg.types.json import Jsonb

from comms import email_html
from comms.route import IST, next_send_time
from comms.templates import load
from core.config import get_settings
from core.db import Conn
from core.logging import get_logger
from notify.render import long_date

log = get_logger("notify.digest")
EVENT = "review.decide_by_digest"
TEMPLATE = "desk/decide-by-digest"
OPEN = ("with_review_desk", "needs_you")
SHOWN = 20  # the longest list one email carries; the desk page has the rest


def overdue(conn: Conn, now: dt.datetime) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT i.idea_id, i.title, i.decide_by, u.name, u.first_name FROM ideas i LEFT JOIN users u ON u.id = "
        "i.reviewer_id WHERE i.decide_by < %s AND i.status = ANY(%s) ORDER BY i.decide_by, i.idea_id",
        (now, list(OPEN)),
    ).fetchall()
    return [dict(r) for r in rows]


def recipients(conn: Conn) -> list[str]:
    """The review desk lead; with no such role, every active reviewer."""
    rows = conn.execute(
        "SELECT DISTINCT g.user_id FROM role_grants g JOIN users u ON u.id = g.user_id WHERE g.role = 'reviewer' "
        "AND g.valid_to IS NULL AND u.active ORDER BY g.user_id"
    ).fetchall()
    return [str(r["user_id"]) for r in rows]


def queue(conn: Conn, now: dt.datetime | None = None) -> int:
    """Queue today's digest for each recipient, on working days and only when something is past its date."""
    now = now or dt.datetime.now(dt.UTC)
    if next_send_time(now, "routine") != now:
        return 0  # a weekend, a holiday or out of hours: the next working day's run carries it
    if not overdue(conn, now):
        return 0
    key = f"decide_by_digest:{now.astimezone(IST).date().isoformat()}"
    queued = 0
    for user in recipients(conn):
        row = conn.execute(
            "INSERT INTO notifications (user_id, channel, template, payload, event, urgency, state, send_after, "
            "dedupe_key) VALUES (%s, 'email', %s, %s, %s, 'immediate', 'queued', %s, %s) "
            "ON CONFLICT (user_id, channel, dedupe_key) WHERE dedupe_key IS NOT NULL DO NOTHING RETURNING id",
            (user, TEMPLATE, Jsonb({}), EVENT, now, key),
        ).fetchone()
        queued += 1 if row else 0
    if queued:
        log.info("notify.digest_queued", person_count=queued)
    return queued


def _days(late: dt.timedelta) -> str:
    days = max(1, late.days + (1 if late.seconds else 0))
    return "1 day" if days == 1 else f"{days} days"


def compose(conn: Conn, user_id: str, now: dt.datetime | None = None) -> email_html.Email:
    """The digest as it stands when it is sent: each idea's title and reference, how late, and who opened it."""
    now = now or dt.datetime.now(dt.UTC)
    rows = overdue(conn, now)
    me = conn.execute("SELECT name, first_name FROM users WHERE id = %s", (user_id,)).fetchone()
    first = str((me or {}).get("first_name") or str((me or {}).get("name") or "there").split()[0])
    lines = []
    for r in rows[:SHOWN]:
        who = f"opened by {r['first_name'] or str(r['name']).split()[0]}" if r["name"] else "not opened yet"
        title = (r["title"] or "").strip() or "Untitled idea"
        lines.append(
            f"{title} ({r['idea_id']}): due {long_date(r['decide_by']).split(',')[0]}, "
            f"{_days(now - r['decide_by'])} late, {who}"
        )
    tpl = load(TEMPLATE)
    rows_md = "\n".join(f"- {{{{digest.items.{i}}}}}" for i in range(len(lines)))
    tpl = replace(tpl, body=tpl.body.replace("- {{digest.item}}", rows_md))
    n = len(rows)
    data = {
        "recipient": {"first_name": first},
        "digest": {
            "items": lines,
            "count": n,
            "count_words": "1 idea is" if n == 1 else f"{n} ideas are",
            "more": max(0, n - SHOWN),
            "has_more": n > SHOWN,
        },
        "links": {"desk": f"{get_settings().app_base_url.rstrip('/')}/desk"},
    }
    return email_html.compose(tpl, data, get_settings().app_base_url)
