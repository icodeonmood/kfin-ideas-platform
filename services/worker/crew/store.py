"""Small database helpers for lane F (the crew deck and search): who is asking, the person's own area and office,
day labels, and refusals in the pack's error shape (A-API.conventions/2).

Conventions from the cut-over (20261121500100): ideas are keyed by `ideas.id` and named on the wire by their IDEA-
reference; a person who shares or helps is a contributor code, a signed-in person a `users.id`. Nothing here logs
or raises with idea text, names or queries (non-negotiable 3): refusals carry a code, and messages are the
screens' own fixed words.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass
from typing import Any

from core.db import Conn

IST = dt.timezone(dt.timedelta(hours=5, minutes=30), "IST")


class Refused(Exception):
    """An action the rules do not allow: `status` is the HTTP status, `code` the A-API error code, `message` text
    ready to show under `field`."""

    def __init__(self, status: int, code: str, message: str | None = None, field: str | None = None) -> None:
        super().__init__(code)
        self.status, self.code, self.message, self.field = status, code, message, field

    def body(self) -> dict[str, Any]:
        err: dict[str, Any] = {"code": self.code, "message": self.message or ""}
        if self.field:
            err["field"] = self.field
        return {"error": err}


@dataclass(frozen=True)
class Viewer:
    """The signed-in person: their user id, their contributor code (None before they first share or help), and
    their area and office from the directory."""

    user_id: str
    code: str | None
    first_name: str
    area: str | None
    city: str | None


def viewer(conn: Conn, user_id: str) -> Viewer:
    """The person asking, or 404 for an id that is not a person."""
    try:
        uuid.UUID(str(user_id))
    except ValueError:
        raise Refused(404, "not_found") from None
    row = conn.execute(
        "SELECT u.id, u.name, u.first_name, u.area, u.location, m.contributor_code "
        "FROM users u LEFT JOIN contributor_map m ON m.user_id = u.id WHERE u.id = %s",
        (user_id,),
    ).fetchone()
    if row is None:
        raise Refused(404, "not_found")
    name = str(row["name"] or "")
    return Viewer(
        str(row["id"]),
        str(row["contributor_code"]) if row["contributor_code"] else None,
        str(row["first_name"] or (name.split(" ")[0] if name else "")),
        row["area"],
        row["location"],
    )


def roles_of(conn: Conn, user_id: str) -> set[str]:
    return {
        str(r["role"])
        for r in conn.execute(
            "SELECT role FROM role_grants WHERE user_id = %s AND valid_from <= now() "
            "AND (valid_to IS NULL OR valid_to > now())",
            (user_id,),
        ).fetchall()
    }


# People on cards and in "Your crews" come from `similar.preview.person_refs`, which applies "hide my name" and
# leavers (BLD-F042); there is deliberately no name lookup here.


def now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def day_label(at: dt.datetime, current: dt.datetime, tz: dt.tzinfo = IST) -> str:
    """When something happened, as the screens say it in India time: "today", "yesterday", a weekday within the
    last week ("Saturday"), else the date ("12 November")."""
    day, today = at.astimezone(tz).date(), current.astimezone(tz).date()
    gap = (today - day).days
    if gap <= 0:
        return "today"
    if gap == 1:
        return "yesterday"
    if gap < 7:
        return at.astimezone(tz).strftime("%A")
    return f"{day.day} {at.astimezone(tz).strftime('%B')}"
