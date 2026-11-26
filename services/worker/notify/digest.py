"""The decide-by digest (L-REVIEW.clock/3, `NOT DRAWN:` default; BLD-A203): once a working day, an email to the
review desk lead listing the ideas past their decide-by date that are still with the desk. No automatic decision.

There is no "review desk lead" role in the pack's roles (E-ENUMS.roles), so the digest goes to every reviewer until
one is named. It is queued by the scheduled `comms.digest` job and sent by `comms.send.send_due`, so it has the same
retries and email switch as every other message; it lists the ideas as they are when it is sent. Each person gets at
most one a day (the dedupe key holds the date).

Off at launch (BLD-B241: nothing is mailed about overdue ideas; the desk sees them on its list and in the summary
sentence). `DECIDE_BY_DIGEST=true` and a worker restart switch it on; while it is off nothing is queued, and a digest
queued before it was switched off is not sent.

The Inbox digest (DEC-133's after-launch rule with DEC-138's defaults; BLD-A255, L-NOTIFY/1, /3): `notify.post` sends
at once only decisions, reversals, merge notices, answer reminders and anything posted as Needs you. Every other
Inbox item is stored with `urgency = 'routine'` and waits. Once a working day, from the same `comms.digest` job,
`queue_inbox` gives each active person with an email address and email on one email row covering the items that
waited since their last digest (`payload` holds the window's two times only). `compose_inbox` builds it when it is
sent, from the items still unread then: one section per item, oldest first, each as that item's own email would read
(`notify.render.variables`), so it carries the idea title, what happened, any date and a link, never hidden details,
anyone's words or a reason, and names the sender exactly as the Inbox does for that reader (DEC-111, DEC-113). No
Teams digest, no new switch, no new template: `comms.email` off leaves it queued like any email.
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
from notify import AT_ONCE
from notify import render as inbox_render
from notify.render import long_date

log = get_logger("notify.digest")
EVENT = "review.decide_by_digest"
TEMPLATE = "desk/decide-by-digest"
OPEN = ("with_review_desk", "needs_you")
SHOWN = 20  # the longest list one email carries; the desk page has the rest

# The Inbox digest (BLD-A255). The template name is a label only: `comms.send.compose` routes the event here and the
# email is built from each item's own template, so there is no file to seed (an upgrade never re-seeds the server's
# company repo).
INBOX_EVENT = "inbox.digest"
INBOX_TEMPLATE = "inbox/digest"
INBOX_KEY = "inbox_digest"
# An Inbox item that waits for the digest: posted under DEC-138 as `routine` (so it had no outside message), not an
# at-once kind, not Needs you, never resolved (a resolved item was Needs you, so it went at once), and unread. Items
# posted before the rule (r6: every one emailed at once, `immediate`) and the club seed's (no urgency) are never in it.
_WAITING = (
    "n.channel = 'in_app' AND n.kind IS NOT NULL AND n.urgency = 'routine' AND NOT (n.kind = ANY(%(at_once)s::text[])) "
    "AND NOT n.needs_you AND n.resolved_at IS NULL AND n.read_at IS NULL"
)
_ITEM_COLUMNS = (
    "n.id, n.user_id, n.kind, n.event, n.template, n.payload, n.created_at, n.read_at, n.archived_at, n.needs_you, "
    "n.resolved_at, n.due_at, n.from_user_id, n.idea_uuid, n.actions, n.dedupe_key"
)


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


def enabled() -> bool:
    """The digest's setting (BLD-A203): off at launch, after BLD-B241."""
    return get_settings().decide_by_digest


def queue(conn: Conn, now: dt.datetime | None = None) -> int:
    """Queue today's digest for each recipient, on working days and only when something is past its date."""
    if not enabled():
        return 0  # off at launch (BLD-B241): the desk sees overdue ideas on its list, nothing is mailed
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


def waiting_items(conn: Conn, user_id: str, since: object, until: object) -> list[dict[str, Any]]:
    """The person's Inbox items that waited for the digest and are still unread now, created after `since` (None: from
    the first one) and up to `until`, oldest first (BLD-A255)."""
    rows = conn.execute(
        "SELECT " + _ITEM_COLUMNS + " FROM notifications n WHERE n.user_id = %(user)s AND " + _WAITING + " "  # noqa: S608 (fixed text)
        "AND (%(since)s::timestamptz IS NULL OR n.created_at > %(since)s::timestamptz) "
        "AND n.created_at <= %(until)s::timestamptz ORDER BY n.created_at, n.id",
        {"user": user_id, "since": since, "until": until, "at_once": sorted(AT_ONCE)},
    ).fetchall()
    return [dict(r) for r in rows]


def queue_inbox(conn: Conn, now: dt.datetime | None = None) -> int:
    """Queue today's Inbox digest (DEC-138, BLD-A255): on a working day, one email row for each active person with an
    email address and email on who has items that waited since the `until` of their last digest (none before: every
    item that waited), up to now. A weekend's or a holiday's items roll into the next working day's window. At most
    one a day per person (the key holds the IST date). Returns how many were queued."""
    now = now or dt.datetime.now(dt.UTC)
    if next_send_time(now, "routine") != now:
        return 0  # a weekend, a holiday or out of hours: the next working day's window carries the items
    key = f"{INBOX_KEY}:{now.astimezone(IST).date().isoformat()}"
    rows = conn.execute(
        "INSERT INTO notifications (user_id, channel, template, payload, event, urgency, state, send_after, "  # noqa: S608 (fixed text)
        "dedupe_key) SELECT w.user_id, 'email', %(template)s::text, "
        "jsonb_build_object('since', w.since, 'until', %(until)s::timestamptz), %(event)s::text, 'immediate', "
        "'queued', %(until)s::timestamptz, %(key)s::text FROM (SELECT u.id AS user_id, "
        "(SELECT (d.payload->>'until')::timestamptz FROM notifications d WHERE d.user_id = u.id "
        "AND d.channel = 'email' AND d.event = %(event)s::text "
        "ORDER BY d.id DESC LIMIT 1) AS since FROM users u LEFT JOIN comms_prefs p ON p.user_id = u.id "
        "WHERE u.active AND u.email <> '' AND coalesce(p.email, true)) w "
        "WHERE EXISTS (SELECT 1 FROM notifications n WHERE n.user_id = w.user_id AND " + _WAITING + " "
        "AND (w.since IS NULL OR n.created_at > w.since) AND n.created_at <= %(until)s::timestamptz) "
        "ON CONFLICT (user_id, channel, dedupe_key) WHERE dedupe_key IS NOT NULL DO NOTHING RETURNING id",
        {
            "template": INBOX_TEMPLATE,
            "event": INBOX_EVENT,
            "until": now,
            "key": key,
            "at_once": sorted(AT_ONCE),
        },
    ).fetchall()
    if rows:
        log.info("notify.inbox_digest_queued", person_count=len(rows))
    return len(rows)


def compose_inbox(
    conn: Conn, user_id: str, refs: dict[str, Any], now: dt.datetime | None = None
) -> email_html.Email | None:
    """The Inbox digest as it stands when it is sent (BLD-A255): its window's items still unread, oldest first, one
    section each as that item's own email reads, its link opening the in-app item. None when every one has been read
    (the row ends `nothing_to_send`)."""
    now = now or dt.datetime.now(dt.UTC)
    items = waiting_items(conn, user_id, refs.get("since"), refs.get("until"))
    if not items:
        return None
    sections = [
        inbox_render.variables(conn, item, user_id, now, absolute=True, item_id=item["id"]) for item in items
    ]
    return email_html.digest(sections, get_settings().app_base_url)
