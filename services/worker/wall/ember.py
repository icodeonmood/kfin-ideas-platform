"""The Ember on the Wall (L-WALL.ember, S-WALL.ember): the latest issue and the next one as "Coming soon".

Issues stay in `ember_issues` (one row per month; the admin drafts and sends it, unchanged). The pack's content is
editorial: `OPEN:` authoring is outside draft 0, default "a simple content record per issue". So an issue's words
are read from its `content` record as `headline` and `items` (the three numbered lines); an issue sent before that
record existed shows its number and month with no headline, never words made up here.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from core.db import Conn
from wall.common import IST, month_label, public_text

ITEMS = 3


def _words(content: Any) -> tuple[str | None, list[str]]:
    c = content if isinstance(content, dict) else {}
    headline = public_text(c.get("headline"))
    raw = c.get("items")
    items = [t for t in (public_text(x) for x in raw) if t] if isinstance(raw, list) else []
    return headline, items[:ITEMS]


def _next_month(d: dt.date) -> dt.date:
    return dt.date(d.year + (d.month == 12), d.month % 12 + 1, 1)


def ember(conn: Conn, now: dt.datetime | None = None) -> list[dict[str, Any]]:
    """`EmberIssue[]` (A-API.wall): the latest sent issue (`latest`), then the next month's (`coming_soon`)."""
    now = now or dt.datetime.now(dt.UTC)
    sent = conn.execute(
        "SELECT id, month, content, row_number() OVER (ORDER BY month) AS n FROM ember_issues "
        "WHERE state = 'sent' ORDER BY month DESC LIMIT 1"
    ).fetchone()
    out: list[dict[str, Any]] = []
    if sent is not None:
        headline, items = _words(sent["content"])
        out.append(
            {
                "number": int(sent["n"]), "month": month_label(sent["month"]), "headline": headline,
                "items": items, "state": "latest", "to": f"/ember/{int(sent['id'])}",
            }
        )  # fmt: skip
        number = int(sent["n"]) + 1
        month = _next_month(sent["month"])
    else:
        number = 1
        today = now.astimezone(IST).date()
        month = dt.date(today.year, today.month, 1)
    upcoming = conn.execute(
        "SELECT content FROM ember_issues WHERE state <> 'sent' AND month = %s", (month,)
    ).fetchone()
    headline, _ = _words(upcoming["content"] if upcoming else None)
    out.append(
        {
            "number": number,
            "month": month_label(month),
            "headline": headline,
            "items": [],
            "state": "coming_soon",
        }
    )
    return out
