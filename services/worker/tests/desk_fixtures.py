"""Synthetic people and ideas for the review side's database tests (non-negotiable 11: invented names only).

Every helper writes through the same `db` connection the test uses (autocommit) and returns plain values.
"""

from __future__ import annotations

import datetime as dt
import secrets
import uuid
from typing import Any

from core.db import Conn

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
_counter = iter(range(1, 10**6))


def at(d: int, h: int = 0, mi: int = 0, m: int = 11, y: int = 2026) -> dt.datetime:
    return dt.datetime(y, m, d, h, mi, tzinfo=IST)


def person(conn: Conn, name: str, *, city: str = "Hyderabad", area: str = "Investor service",
           roles: tuple[str, ...] = ()) -> dict[str, str]:  # fmt: skip
    """A user with a contributor code and any roles ('reviewer', 'committee', 'admin')."""
    user_id = str(uuid.uuid4())
    code = f"CTR-{secrets.token_hex(3)}"
    conn.execute(
        "INSERT INTO users (id, emp_id_hash, name, email, first_name, location, area) VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (user_id, f"hash-{user_id}", name, f"{name.split()[0].lower()}.{next(_counter)}@example.test",
         name.split()[0], city, area),
    )  # fmt: skip
    conn.execute("INSERT INTO contributor_map (contributor_code, user_id) VALUES (%s, %s)", (code, user_id))
    for role in roles:
        conn.execute("INSERT INTO role_grants (user_id, role) VALUES (%s, %s)", (user_id, role))
    return {"id": user_id, "code": code, "name": name, "first_name": name.split()[0]}


def idea(conn: Conn, sharer: dict[str, str], *, title: str = "Investors call to ask why a redemption was rejected",
         status: str = "with_review_desk", shared_at: dt.datetime | None = None,
         decide_by: dt.datetime | None = None, **columns: Any) -> dict[str, Any]:  # fmt: skip
    """A shared idea with its sharer as crew lead. Returns the row."""
    shared_at = shared_at or at(14, 10)
    n = next(_counter)
    ref = f"IDEA-2026-{1400 + n:06d}"
    cols = {
        "idea_id": ref, "contributor_code": sharer["code"], "status": status, "title": title,
        "summary": "Investors call the branch because the SMS gives a code, not a reason.",
        "often": "About 40 calls a day at one branch.", "city": "Hyderabad", "area": "Investor service",
        "kind": "problem", "shared_at": shared_at, "decide_by": decide_by or at(20, 18),
        "edit_closes_at": shared_at + dt.timedelta(days=3), **columns,
    }  # fmt: skip
    names = ", ".join(cols)
    marks = ", ".join(["%s"] * len(cols))
    sql = f"INSERT INTO ideas ({names}) VALUES ({marks}) RETURNING *"  # noqa: S608 (column names are this file's own)
    row = conn.execute(sql, tuple(cols.values())).fetchone()
    assert row is not None
    conn.execute(
        "INSERT INTO crew_members (idea_uuid, contributor_code, role, via) VALUES (%s, %s, 'lead', 'shared')",
        (row["id"], sharer["code"]),
    )
    return dict(row)


def crew(conn: Conn, idea_row: dict[str, Any], member: dict[str, str]) -> None:
    conn.execute(
        "INSERT INTO crew_members (idea_uuid, contributor_code, role, via) VALUES (%s, %s, 'crew', 'teamup')",
        (idea_row["id"], member["code"]),
    )


def audit_actions(conn: Conn, entity_prefix: str = "") -> list[str]:
    return [
        r["action"]
        for r in conn.execute(
            "SELECT action FROM audit_log WHERE entity LIKE %s ORDER BY id", (f"{entity_prefix}%",)
        ).fetchall()
    ]


def events(conn: Conn, idea_uuid: Any) -> list[str]:
    return [
        str(r["event"] or r["type"])
        for r in conn.execute(
            "SELECT type, event FROM conversation_entries WHERE idea_uuid = %s ORDER BY at, id", (idea_uuid,)
        ).fetchall()
    ]
