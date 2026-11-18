"""The sharer's own draft or idea, found by its row id (a draft) or its reference (a shared idea). Someone else's
looks exactly like a missing one (`NotFound`), so a request never confirms that an idea exists."""

from __future__ import annotations

import re
from typing import Any

from core.db import Conn
from submit.errors import NotFound

UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
REF = re.compile(r"^IDEA-[0-9]{4}-[0-9]{6}$")


def code_of(conn: Conn, user_id: str) -> str | None:
    if not UUID.match(user_id or ""):
        return None
    row = conn.execute(
        "SELECT contributor_code FROM contributor_map WHERE user_id = %s", (user_id,)
    ).fetchone()
    return str(row["contributor_code"]) if row else None


def find(conn: Conn, key: str, *, lock: bool = False) -> dict[str, Any] | None:
    if UUID.match(key or ""):
        where = "id = %s"
    elif REF.match(key or ""):
        where = "idea_id = %s"
    else:
        return None
    row = conn.execute(
        f"SELECT * FROM ideas WHERE {where}{' FOR UPDATE' if lock else ''}",  # noqa: S608 - fixed fragments
        (key,),
    ).fetchone()
    return dict(row) if row else None


def load_own(conn: Conn, key: str, user_id: str, *, lock: bool = False) -> tuple[dict[str, Any], str]:
    """The idea and the sharer's contributor code, or NotFound."""
    code = code_of(conn, user_id)
    idea = find(conn, key, lock=lock)
    if code is None or idea is None or idea["contributor_code"] != code:
        raise NotFound
    return idea, code


def audit(conn: Conn, user_id: str, action: str, idea: dict[str, Any], after: dict[str, Any]) -> None:
    """Every action a person takes on their idea, with IDs, codes and counts only (non-negotiables 3 and 9)."""
    from psycopg.types.json import Jsonb

    entity = f"idea:{idea['idea_id'] or idea['id']}"
    conn.execute(
        "INSERT INTO audit_log (actor, action, entity, after) VALUES (%s, %s, %s, %s)",
        (f"user:{user_id}", action, entity, Jsonb(after)),
    )
