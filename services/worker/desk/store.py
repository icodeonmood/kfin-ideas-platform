"""Shared database helpers for the review side: loading an idea, people, sealing private text, refusals, audit.

Conventions from the cut-over (20261121500100): ideas are found by their IDEA- reference and keyed by `ideas.id`;
the sharer is a contributor code, staff are `users.id`; private text is stored as the masked copy, encrypted with
the context "<table>.<column>:<row id>"; audit entries carry IDs, never text (non-negotiable 3).
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from psycopg.types.json import Jsonb

from core.db import Conn
from onepc.context import open_text, seal_text


class Refused(Exception):
    """An action the rules do not allow. `code` is the A-API error code, `status` the HTTP status, `field` the field
    a message belongs under, `message` text ready to show (A-API.conventions/2). `audit` is written after the
    rollback, so a refusal that must leave a trace survives it. `extra` adds fixed facts the screen needs beside the
    message (the wording check's words), never idea text."""

    def __init__(
        self,
        status: int,
        code: str,
        message: str | None = None,
        field: str | None = None,
        audit: tuple[str, str, str, dict[str, Any]] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(code)
        self.status, self.code, self.message, self.field, self.audit = status, code, message, field, audit
        self.extra = extra or {}

    def body(self) -> dict[str, Any]:
        err: dict[str, Any] = {**self.extra, "code": self.code, "message": self.message or ""}
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
    """Private masked text for a `*_encrypted` column, sealed as the cut-over defines it (onepc.context, BLD-E006),
    so the web app can open what the worker wrote."""
    return seal_text(table, column, row_id, text)


def unseal(blob: bytes | None, table: str, column: str, row_id: str | int) -> str | None:
    return open_text(table, column, row_id, blob)


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


# P-PRODUCT.privacy (DEC-104): the review desk and the Ones Committee read a sharer's private words, answers, the worth
# note and a decision's reason; admins see the stage only. `core_committee` and `core_chair` (its chair, a role of its
# own elsewhere in the worker, as in `similar.preview.DESK_ROLES`) are the committee's roles until lane E retires them
# with the old pages: they read only. Only the review desk acts on an idea from the desk.
READERS = frozenset({"reviewer", "committee", "core_committee", "core_chair"})
REVIEWERS = frozenset({"reviewer"})
_NOT_YOURS = {
    READERS: "Only the review desk and the Ones Committee can see this.",
    REVIEWERS: "Only the review desk can do this.",
}


# Files by check state (E-ENUMS.file). Everyone allowed to see an idea's files sees the checked ones; a file in which
# the scan found a customer detail can still be sent (DEC-107) and opens only for its sharer, the review desk and the
# Ones Committee, marked `customer_detail`; never for the crew or anyone else. Nobody else sees a file still
# uploading or checking, infected, locked or failed. `SHOWN_FILE` takes the states as its one parameter; a file from
# before the cut-over has no `file_state` and counts when the old pipeline marked it clean.
FILES_CHECKED: tuple[str, ...] = ("checked", "hidden_checked", "ok")
CUSTOMER_DETAIL = "personal_data_found"
DESK_SEES: tuple[str, ...] = (*FILES_CHECKED, CUSTOMER_DETAIL)
SHOWN_FILE = "(file_state = ANY(%s) OR (file_state IS NULL AND state = 'clean'))"


def has_role(conn: Conn, user_id: str, roles: Iterable[str]) -> bool:
    """A live grant of any of `roles` (role_grants, from and to dates). Anything that is not a user id has none."""
    try:
        uuid.UUID(str(user_id))
    except ValueError:
        return False
    return (
        conn.execute(
            "SELECT 1 FROM role_grants WHERE user_id = %s AND role = ANY(%s) AND valid_from <= now() "
            "AND (valid_to IS NULL OR valid_to > now()) LIMIT 1",
            (user_id, sorted(roles)),
        ).fetchone()
        is not None
    )


def require_role(conn: Conn, user_id: str, roles: frozenset[str]) -> None:
    """403 `forbidden` unless the person holds one of `roles`: every desk read needs READERS, every desk write
    REVIEWERS. The web app's capabilities let admins reach the desk routes; the worker does not (P-PRODUCT.privacy)."""
    if not has_role(conn, user_id, roles):
        raise Refused(403, "forbidden", _NOT_YOURS.get(roles, _NOT_YOURS[REVIEWERS]))


def own_codes(conn: Conn, idea: dict[str, Any]) -> set[str]:
    """The sharer, and the sharers of every idea merged into this one, through chains of merges: all are credited
    (L-MERGE.effects/2), so none of them may review, decide or reverse it."""
    codes = {str(idea["contributor_code"])}
    for r in conn.execute(
        "WITH RECURSIVE joined(id) AS ("
        "  SELECT merged_idea_uuid FROM merges WHERE lead_idea_uuid = %s AND reversed_at IS NULL"
        "  UNION SELECT m.merged_idea_uuid FROM merges m JOIN joined j ON m.lead_idea_uuid = j.id"
        "    WHERE m.reversed_at IS NULL"
        ") SELECT i.contributor_code FROM joined j JOIN ideas i ON i.id = j.id",
        (idea["id"],),
    ).fetchall():
        codes.add(str(r["contributor_code"]))
    return codes


def sharers_and_crew(conn: Conn, idea: dict[str, Any]) -> list[str]:
    """L-INBOX.kinds: who hears of a decision on the idea, as user ids, each once: every credited sharer
    (`own_codes`) and every live crew member (not left). Codes erased from contributor_map are skipped."""
    codes = sorted(own_codes(conn, idea)) + [
        str(r["contributor_code"])
        for r in conn.execute(
            "SELECT contributor_code FROM crew_members WHERE idea_uuid = %s AND left_at IS NULL ORDER BY joined_at, id",
            (idea["id"],),
        ).fetchall()
    ]
    return list(dict.fromkeys(u for c in dict.fromkeys(codes) if (u := user_of(conn, c))))


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
