"""Database helpers for team-up, merge requests and crews.

Modelled on lane B's `desk.store` (not imported, so neither lane waits on the other). Conventions from the cut-over
(20261121500100): an idea is found by its IDEA- reference or its row id; a person who shares or teams up is a
contributor code; private text is the masked copy, sealed with "<table>.<column>:<row id>"; audit entries carry IDs,
never text (non-negotiable 3).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from psycopg.types.json import Jsonb

from core.db import Conn
from onepc.context import open_text, seal_text
from onepc.enums import CLOSED_STATUSES

UUID_LEN = 36


class Refused(Exception):
    """An action the rules do not allow, answered as `{error: {code, message, field?}}` (A-API.conventions/2).
    `audit` is written after the rollback, so a refused attempt that must leave a trace survives it."""

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
            who, action, entity, after = exc.audit
            audit(conn, who, action, entity, after=after)
        raise


def audit(
    conn: Conn,
    who: str,
    action: str,
    entity: str,
    *,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    """Every privileged action (non-negotiable 9). IDs, enums and counts only."""
    conn.execute(
        "INSERT INTO audit_log (actor, action, entity, before, after) VALUES (%s, %s, %s, %s, %s)",
        (
            who,
            action,
            entity,
            Jsonb(before) if before is not None else None,
            Jsonb(after) if after is not None else None,
        ),
    )


def actor(user_id: str) -> str:
    return f"user:{user_id}"


def entity_of(idea: dict[str, Any]) -> str:
    """`idea:IDEA-…` for a shared idea, `draft:<uuid>` for a draft (which has no reference yet)."""
    return f"idea:{idea['idea_id']}" if idea.get("idea_id") else f"draft:{idea['id']}"


def seal(text: str, table: str, column: str, row_id: str | int) -> bytes:
    """Private masked text for a `*_encrypted` column, sealed as the cut-over defines it (onepc.context)."""
    return seal_text(table, column, row_id, text)


def unseal(blob: bytes | None, table: str, column: str, row_id: str | int) -> str | None:
    return open_text(table, column, row_id, blob)


def is_closed(status: str) -> bool:
    """L-TEAMUP.rules/1: closed, withdrawn or merged away (E-ENUMS idea_status group `closed`)."""
    return status in CLOSED_STATUSES


def _looks_like_uuid(value: str) -> bool:
    return len(value) == UUID_LEN and value.count("-") == 4


def load_idea(conn: Conn, ref: str, *, lock: bool = False) -> dict[str, Any]:
    """A shared idea by its IDEA- reference (or its row id), or 404. Drafts are not shared ideas."""
    if ref.startswith("IDEA-"):
        column = "idea_id"
    elif _looks_like_uuid(ref):
        column = "id::text"
    else:
        raise Refused(404, "not_found")
    row = conn.execute(
        f"SELECT * FROM ideas WHERE {column} = %s{' FOR UPDATE' if lock else ''}",  # noqa: S608 (fixed columns)
        (ref,),
    ).fetchone()
    if row is None or row["status"] == "draft":
        raise Refused(404, "not_found")
    return dict(row)


def load_draft(conn: Conn, draft_id: str, code: str | None, *, lock: bool = False) -> dict[str, Any]:
    """The person's own draft by its row id, or 404 for anyone else's (a draft is its owner's alone)."""
    if not _looks_like_uuid(draft_id) or code is None:
        raise Refused(404, "not_found")
    row = conn.execute(
        f"SELECT * FROM ideas WHERE id::text = %s{' FOR UPDATE' if lock else ''}",  # noqa: S608 (fixed clause)
        (draft_id,),
    ).fetchone()
    if row is None or row["contributor_code"] != code:
        raise Refused(404, "not_found")
    return dict(row)


def lock_ideas(conn: Conn, *uuids: Any) -> dict[str, dict[str, Any]]:
    """Lock ideas in one stable order (by row id), so two answers touching the same pair cannot deadlock."""
    out: dict[str, dict[str, Any]] = {}
    for u in sorted({str(u) for u in uuids}):
        row = conn.execute("SELECT * FROM ideas WHERE id = %s FOR UPDATE", (u,)).fetchone()
        if row is not None:
            out[u] = dict(row)
    return out


def code_of(conn: Conn, user_id: str) -> str | None:
    if not _looks_like_uuid(user_id):
        return None
    row = conn.execute(
        "SELECT contributor_code FROM contributor_map WHERE user_id = %s", (user_id,)
    ).fetchone()
    return str(row["contributor_code"]) if row else None


def user_of(conn: Conn, code: str | None) -> str | None:
    if not code:
        return None
    row = conn.execute("SELECT user_id FROM contributor_map WHERE contributor_code = %s", (code,)).fetchone()
    return str(row["user_id"]) if row else None


def require_code(conn: Conn, user_id: str) -> str:
    """The signed-in person's contributor code. Sign-in assigns one; a person without one cannot team up."""
    code = code_of(conn, user_id)
    if code is None:
        raise Refused(403, "forbidden", "Sign in again to team up.")
    return code


def crew_codes(conn: Conn, idea_uuid: Any) -> list[str]:
    """The live crew, lead first, then in the order they joined."""
    return [
        str(r["contributor_code"])
        for r in conn.execute(
            "SELECT contributor_code FROM crew_members WHERE idea_uuid = %s AND left_at IS NULL "
            "ORDER BY role = 'lead' DESC, joined_at, id",
            (idea_uuid,),
        ).fetchall()
    ]


def lead_code(conn: Conn, idea: dict[str, Any]) -> str:
    """The idea's lead: its live `lead` crew row, else its sharer (L-TEAMUP.rules/10)."""
    row = conn.execute(
        "SELECT contributor_code FROM crew_members WHERE idea_uuid = %s AND role = 'lead' AND left_at IS NULL",
        (idea["id"],),
    ).fetchone()
    return str(row["contributor_code"]) if row else str(idea["contributor_code"])


def crew_role(conn: Conn, idea_uuid: Any, code: str) -> str | None:
    row = conn.execute(
        "SELECT role FROM crew_members WHERE idea_uuid = %s AND contributor_code = %s AND left_at IS NULL",
        (idea_uuid, code),
    ).fetchone()
    return str(row["role"]) if row else None


@dataclass(frozen=True)
class Person:
    """E-ENTITIES PersonRef. Names show in team-up (P-PRODUCT.privacy; DEC-104 hides them from the Wall only)."""

    id: str | None
    name: str
    first_name: str
    initials: str
    city: str | None
    area: str | None
    role_title: str | None = None

    def as_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {"id": self.id, "name": self.name, "first_name": self.first_name,
                               "initials": self.initials}  # fmt: skip
        if self.area:
            out["area"] = self.area
        if self.city:
            out["city"] = self.city
        return out


UNKNOWN = Person(None, "A colleague", "A colleague", "1%", None, None)


def person_by_user(conn: Conn, user_id: str | None) -> Person:
    if not user_id:
        return UNKNOWN
    row = conn.execute(
        "SELECT id, name, first_name, location, area, role_title FROM users WHERE id = %s", (user_id,)
    ).fetchone()
    if row is None:
        return UNKNOWN  # erased: anonymised everywhere
    name = str(row["name"])
    first = str(row["first_name"] or name.split(" ")[0])
    initials = "".join(w[0] for w in name.split()[:2]).upper()
    return Person(str(row["id"]), name, first, initials, row["location"], row["area"], row["role_title"])


def person_by_code(conn: Conn, code: str | None) -> Person:
    return person_by_user(conn, user_of(conn, code))


def now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


# --- A-API.conventions/3: repeating a create with the same Idempotency-Key returns the first result -------------
IDEMPOTENCY_KEY_MIN, IDEMPOTENCY_KEY_MAX = 8, 200


def _usable_key(key: str | None) -> str | None:
    if key and IDEMPOTENCY_KEY_MIN <= len(key) <= IDEMPOTENCY_KEY_MAX:
        return key
    return None


def remembered(conn: Conn, user_id: str, key: str | None, route: str) -> str | None:
    """The row id a create with this key already made, if it is still remembered (24 hours)."""
    k = _usable_key(key)
    if k is None:
        return None
    row = conn.execute(
        "SELECT response_json FROM idempotency_keys WHERE user_id = %s AND key = %s AND route = %s "
        "AND expires_at > now()",
        (user_id, k, route),
    ).fetchone()
    if row is None or not isinstance(row["response_json"], dict):
        return None
    made = row["response_json"].get("id")
    return str(made) if made else None


def remember(
    conn: Conn, user_id: str, key: str | None, route: str, body: dict[str, Any], made_id: str
) -> None:
    """Keep the created row's id (IDs only; the table's rule) against the key."""
    k = _usable_key(key)
    if k is None:
        return
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()
    conn.execute(
        "INSERT INTO idempotency_keys (key, user_id, route, request_hash, status, response_json) "
        "VALUES (%s, %s, %s, %s, 201, %s) ON CONFLICT (user_id, key) DO NOTHING",
        (k, user_id, route, digest, Jsonb({"id": made_id})),
    )
