"""Database helpers for the conversation: the idea, people, refusals, sealing, audit.

Conventions from the cut-over (20261121500100): an idea is found by its IDEA- reference (or its uuid) and keyed by
`ideas.id`; sharers and crew are contributor codes, staff are `users.id`; a message is stored as the masked copy,
sealed with the context "conversation_entries.text_encrypted:<entry id>" (onepc.context), so the web app can open
what the worker wrote. Audit entries and logs carry IDs and codes, never words or names (non-negotiable 3).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any

from psycopg.types.json import Jsonb

from core.db import Conn
from onepc.context import open_text, seal_text
from onepc.words import REVIEW_DESK, REVIEW_DESK_START


class Refused(Exception):
    """What the rules do not allow, in the A-API error shape (A-API.conventions/2): `code` for the screen, `message`
    ready to show under `field`."""

    def __init__(self, status: int, code: str, message: str = "", field: str | None = None) -> None:
        super().__init__(code)
        self.status, self.code, self.message, self.field = status, code, message, field

    def body(self) -> dict[str, Any]:
        err: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.field:
            err["field"] = self.field
        return {"error": err}


def not_found() -> Refused:
    """404, never 403: the answer never says the conversation exists (L-CONVO/2)."""
    return Refused(404, "not_found")


TABLE, COLUMN = "conversation_entries", "text_encrypted"


def seal(text: str, entry_id: str) -> bytes:
    return seal_text(TABLE, COLUMN, entry_id, text)


def unseal(blob: bytes | memoryview | None, entry_id: str) -> str | None:
    return open_text(TABLE, COLUMN, entry_id, blob)


def now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def load_idea(conn: Conn, ref: str) -> dict[str, Any]:
    """A shared idea by its IDEA- reference or uuid; a draft or an unknown one is not found (404)."""
    row = conn.execute("SELECT * FROM ideas WHERE idea_id = %s OR id::text = %s", (ref, ref)).fetchone()
    if row is None or row["status"] == "draft":
        raise not_found()
    return dict(row)


def code_of(conn: Conn, user_id: str) -> str | None:
    row = conn.execute(
        "SELECT contributor_code FROM contributor_map WHERE user_id = %s", (user_id,)
    ).fetchone()
    return str(row["contributor_code"]) if row else None


def user_of(conn: Conn, code: str | None) -> str | None:
    if not code:
        return None
    row = conn.execute("SELECT user_id FROM contributor_map WHERE contributor_code = %s", (code,)).fetchone()
    return str(row["user_id"]) if row else None


def audit(conn: Conn, user_id: str, action: str, entity: str, after: dict[str, Any] | None = None) -> None:
    """IDs and enums only (non-negotiable 9)."""
    conn.execute(
        "INSERT INTO audit_log (actor, action, entity, after) VALUES (%s, %s, %s, %s)",
        (f"user:{user_id}", action, entity, Jsonb(after) if after is not None else None),
    )


@dataclass(frozen=True)
class Person:
    """E-ENTITIES PersonRef. `role_label` is "from the review desk" or "from the Ones Committee" for staff speaking
    as staff; `label` is how the timeline names them ("Meera from the review desk", "Ravi Nair", "You").

    `desk` marks the review desk itself (`DESK_PERSON`, DEC-111): what a reader outside the review desk and the Ones
    Committee sees in place of the person at the desk. It has no id, no initials and no avatar."""

    id: str | None
    name: str
    first_name: str
    initials: str
    city: str | None = None
    area: str | None = None
    role_label: str | None = None
    desk: bool = False

    def ref(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id or "",
            "name": self.name,
            "first_name": self.first_name,
            "initials": self.initials,
        }
        for key in ("area", "city", "role_label"):
            if getattr(self, key):
                out[key] = getattr(self, key)
        return out

    def as_staff(self, role_label: str) -> Person:
        return Person(self.id, self.name, self.first_name, self.initials, self.city, self.area, role_label)

    @property
    def label(self) -> str:
        if self.desk:
            return REVIEW_DESK_START  # DEC-111: "The review desk", at the start of a line or as a byline
        if self.role_label == "from the review desk":
            return f"{self.first_name} {self.role_label}"  # "Meera from the review desk" (Messages.md)
        if self.role_label:
            return f"{self.name} {self.role_label}"  # "Rohan Mehta from the Ones Committee"
        return self.name

    @property
    def mid(self) -> str:
        """The first name inside a sentence: "Reply to Kavya", "Answer the review desk’s 3 questions"."""
        return REVIEW_DESK if self.desk else self.first_name


UNKNOWN = Person(None, "A colleague", "A colleague", "1%")  # erased from contributor_map: anonymised
# DEC-111: the person at the review desk as a sharer, the crew, the build team or a mentioned person reads them.
DESK_PERSON = Person(None, REVIEW_DESK_START, REVIEW_DESK_START, "", desk=True)


class People:
    """Names resolved at read time, once per person per request."""

    def __init__(self, conn: Conn) -> None:
        self.conn = conn
        self._by_user: dict[str, Person] = {}
        self._code_user: dict[str, str | None] = {}

    def by_user(self, user_id: str | None) -> Person:
        if not user_id:
            return UNKNOWN
        if user_id not in self._by_user:
            row = self.conn.execute(
                "SELECT id, name, first_name, location, area FROM users WHERE id = %s", (user_id,)
            ).fetchone()
            self._by_user[user_id] = _person(dict(row)) if row else UNKNOWN
        return self._by_user[user_id]

    def user_of(self, code: str | None) -> str | None:
        if not code:
            return None
        if code not in self._code_user:
            self._code_user[code] = user_of(self.conn, code)
        return self._code_user[code]

    def by_code(self, code: str | None) -> Person:
        return self.by_user(self.user_of(code))


def _person(row: dict[str, Any]) -> Person:
    name = str(row["name"])
    first = str(row.get("first_name") or name.split(" ")[0])
    initials = "".join(w[0] for w in name.split()[:2]).upper()
    return Person(str(row["id"]), name, first, initials, row.get("location"), row.get("area"))
