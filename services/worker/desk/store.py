"""Shared database helpers for the review side: loading an idea, people, sealing private text, refusals, audit.

Conventions from the cut-over (20261121500100): ideas are found by their IDEA- reference and keyed by `ideas.id`;
the sharer is a contributor code, staff are `users.id`; private text is stored as the masked copy, encrypted with
the context "<table>.<column>:<row id>"; audit entries carry IDs, never text (non-negotiable 3).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from psycopg.types.json import Jsonb

from core.crypto import decrypt_json, encrypt_json
from core.db import Conn


class Refused(Exception):
    """An action the rules do not allow. `code` is the A-API error code, `status` the HTTP status, `field` the field
    a message belongs under, `message` text ready to show (A-API.conventions/2). `audit` is written after the
    rollback, so a refusal that must leave a trace survives it."""

    def __init__(
        self,
        status: int,
        code: str,
        message: str | None = None,
        field: str | None = None,
        audit: tuple[str, str, str, dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(code)
        self.status, self.code, self.message, self.field, self.audit = status, code, message, field, audit

    def body(self) -> dict[str, Any]:
        err: dict[str, Any] = {"code": self.code, "message": self.message or ""}
        if self.field:
            err["field"] = self.field
        return {"error": err}


@contextmanager
def audited(conn: Conn) -> Iterator[None]:
    """Wrap outside `conn.transaction()`: a refusal that must leave a trace is audited once the work is undone."""
    try:
        yield
    except Refused as exc:
        if exc.audit:
            actor, action, entity, after = exc.audit
            audit(conn, actor, action, entity, after=after)
        raise


def audit(
    conn: Conn,
    actor: str,
    action: str,
    entity: str,
    *,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    """Every privileged action (non-negotiable 9). IDs and enums only."""
    conn.execute(
        "INSERT INTO audit_log (actor, action, entity, before, after) VALUES (%s, %s, %s, %s, %s)",
        (
            actor,
            action,
            entity,
            Jsonb(before) if before is not None else None,
            Jsonb(after) if after is not None else None,
        ),
    )


def actor(user_id: str) -> str:
    return f"user:{user_id}"


def seal(text: str, table: str, column: str, row_id: str | int) -> bytes:
    return encrypt_json({"text": text}, f"{table}.{column}:{row_id}")


def unseal(blob: bytes | None, table: str, column: str, row_id: str | int) -> str | None:
    if blob is None:
        return None
    return str(decrypt_json(bytes(blob), f"{table}.{column}:{row_id}")["text"])


def load_idea(conn: Conn, ref: str, *, lock: bool = False) -> dict[str, Any]:
    """An idea by its IDEA- reference (or its uuid), or 404."""
    column = "idea_id" if ref.startswith("IDEA-") else "id::text"
    row = conn.execute(
        f"SELECT * FROM ideas WHERE {column} = %s{' FOR UPDATE' if lock else ''}",  # noqa: S608 (fixed columns)
        (ref,),
    ).fetchone()
    if row is None or row["status"] == "draft":
        raise Refused(404, "not_found")
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


def own_codes(conn: Conn, idea: dict[str, Any]) -> set[str]:
    """The sharer, and the sharers of ideas merged into this one: all credited (L-MERGE.effects/2)."""
    codes = {str(idea["contributor_code"])}
    for r in conn.execute(
        "SELECT i.contributor_code FROM merges m JOIN ideas i ON i.id = m.merged_idea_uuid "
        "WHERE m.lead_idea_uuid = %s AND m.reversed_at IS NULL",
        (idea["id"],),
    ).fetchall():
        codes.add(str(r["contributor_code"]))
    return codes


def is_own(conn: Conn, user_id: str, idea: dict[str, Any]) -> bool:
    code = code_of(conn, user_id)
    return code is not None and code in own_codes(conn, idea)


def refuse_own(conn: Conn, user_id: str, idea: dict[str, Any], action: str) -> None:
    """A reviewer never reviews their own idea, and a committee member never reverses a decision on theirs
    (P-PRODUCT.roles/3, L-COMMITTEE.rules/9). The attempt is audited."""
    if is_own(conn, user_id, idea):
        raise Refused(
            403, "own_idea", "This is your own idea. Another reviewer takes it.",
            audit=(actor(user_id), "desk.own_idea_refused", f"idea:{idea['idea_id']}", {"action": action}),
        )  # fmt: skip


@dataclass(frozen=True)
class Person:
    """E-ENTITIES PersonRef, for viewers allowed to see names (the desk and the committee, DEC-104)."""

    id: str | None
    name: str
    first_name: str
    initials: str
    city: str | None
    area: str | None

    def as_json(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "first_name": self.first_name, "initials": self.initials,
                "city": self.city, "area": self.area}  # fmt: skip


UNKNOWN = Person(None, "A colleague", "A colleague", "1%", None, None)


def _person(row: dict[str, Any] | None) -> Person:
    if row is None:
        return UNKNOWN  # erased from contributor_map: anonymised everywhere
    name = str(row["name"])
    first = str(row.get("first_name") or name.split(" ")[0])
    initials = "".join(w[0] for w in name.split()[:2]).upper()
    return Person(str(row["id"]), name, first, initials, row.get("location"), row.get("area"))


def person_by_user(conn: Conn, user_id: str | None) -> Person:
    if not user_id:
        return UNKNOWN
    row = conn.execute(
        "SELECT id, name, first_name, location, area FROM users WHERE id = %s", (user_id,)
    ).fetchone()
    return _person(dict(row) if row else None)


def person_by_code(conn: Conn, code: str | None) -> Person:
    return person_by_user(conn, user_of(conn, code))


def now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)
