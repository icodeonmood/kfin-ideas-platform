"""Synthetic people, ideas, Ones and measurements for lane E's Wall, Ones and Profile database tests (non-negotiable
11: invented names only, none of the pack's demo cast). Every helper writes through the test's own `db` connection
(autocommit) and returns plain values."""

from __future__ import annotations

import datetime as dt
import secrets
import uuid
from typing import Any

from psycopg.types.json import Jsonb

from core.crypto import encrypt_json
from core.db import Conn
from onepc.context import seal_text

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
NOW = dt.datetime(2026, 11, 16, 14, 0, tzinfo=IST)  # a Monday afternoon, launch week
_n = iter(range(1, 10**6))


def ago(*, days: float = 0, hours: float = 0) -> dt.datetime:
    return NOW - dt.timedelta(days=days, hours=hours)


def person(
    conn: Conn, name: str, *, area: str = "Investor service", city: str = "Pune", roles: tuple[str, ...] = (),
    tier: int = 1, show_name: bool | None = None,
) -> dict[str, str]:  # fmt: skip
    uid = str(uuid.uuid4())
    code = f"CTR-{secrets.token_hex(3)}"
    conn.execute(
        "INSERT INTO users (id, emp_id_hash, name, email, first_name, location, area, tier) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (uid, f"hash-{uid}", name, f"{name.split()[0].lower()}.{next(_n)}@kfintech.example", name.split()[0],
         city, area, tier),
    )  # fmt: skip
    conn.execute("INSERT INTO contributor_map (contributor_code, user_id) VALUES (%s, %s)", (code, uid))
    for role in ("employee", *roles):
        conn.execute("INSERT INTO role_grants (user_id, role) VALUES (%s, %s)", (uid, role))
    if show_name is not None:
        conn.execute("INSERT INTO person_settings (user_id, show_name_on_wall) VALUES (%s, %s)", (uid, show_name))
    return {"id": uid, "code": code, "name": name}


def idea(
    conn: Conn, sharer: dict[str, str], *, title: str, status: str = "with_review_desk", kind: str = "problem",
    area: str = "Investor service", shared_at: dt.datetime | None = None, **columns: Any,
) -> dict[str, Any]:  # fmt: skip
    """A shared idea with its sharer as the crew's lead."""
    shared_at = shared_at or ago(days=1)
    cols = {
        "idea_id": f"IDEA-2026-{900000 + next(_n):06d}", "contributor_code": sharer["code"], "status": status,
        "title": title, "summary": f"Short summary: {title.lower()}.", "city": "Pune", "area": area, "kind": kind,
        "shared_at": shared_at, "status_changed_at": shared_at, **columns,
    }  # fmt: skip
    names, marks = ", ".join(cols), ", ".join(["%s"] * len(cols))
    row = conn.execute(
        f"INSERT INTO ideas ({names}) VALUES ({marks}) RETURNING *",  # noqa: S608 (this file's own column names)
        tuple(cols.values()),
    ).fetchone()
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


def opened(conn: Conn, idea_row: dict[str, Any], viewer: dict[str, str], days_ago: int = 0) -> None:
    day = (NOW - dt.timedelta(days=days_ago)).astimezone(IST).date()
    conn.execute(
        "INSERT INTO idea_opens (idea_uuid, user_id, day) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
        (idea_row["id"], viewer["id"], day),
    )


def one(
    conn: Conn, who: dict[str, str], *, number: int, tier: int = 1, way_in: str = "accepted_idea",
    idea_ref: str | None = None, inducted_at: dt.datetime | None = None, window_days: int = 30,
    brief: str | None = None,
) -> int:  # fmt: skip
    inducted_at = inducted_at or ago(days=2)
    row = conn.execute(
        "INSERT INTO ones (induction_no, user_id, number, way_in, idea_id, tier, inducted_at, swap_until) VALUES ("
        "next_number('ONE', ''), %s, %s, %s, %s, %s, %s, %s) RETURNING id",
        (who["id"], number, way_in, idea_ref, tier, inducted_at, inducted_at + dt.timedelta(days=window_days)),
    ).fetchone()
    assert row is not None
    oid = int(row["id"])
    conn.execute(
        "INSERT INTO one_number_history (one_id, number, how, from_at) VALUES (%s, %s, 'allocated', %s)",
        (oid, number, inducted_at),
    )
    if brief:
        conn.execute(
            "UPDATE ones SET brief_encrypted = %s, brief_approved_at = %s WHERE id = %s",
            (encrypt_json({"text": brief}, f"one:{oid}:brief"), inducted_at, oid),
        )
    return oid


def post(
    conn: Conn, one_id: int, idea_row: dict[str, Any] | None, text: str, *, value: str = "620",
    line: str = "hours a month saved", hours_ago: float = 5,
) -> str:  # fmt: skip
    pid = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO one_posts (id, one_id, idea_uuid, text_encrypted, figure_value, figure_line, posted_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (pid, one_id, idea_row["id"] if idea_row else None, seal_text("one_posts", "text_encrypted", pid, text),
         value, line, ago(hours=hours_ago)),
    )  # fmt: skip
    return pid


def measurement(
    conn: Conn, idea_row: dict[str, Any], mark: str, results: dict[str, Any] | None, *,
    finance: bool = False, due_at: dt.datetime | None = None,
) -> None:  # fmt: skip
    """A 30- or 90-day measurement; `results=None` is one still due."""
    filled = None if results is None else ago(days=1)
    conn.execute(
        "INSERT INTO delivery_measurements (idea_uuid, mark, due_at, results, filled_at, finance_confirmed_at) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (idea_row["id"], mark, due_at or ago(days=2), Jsonb(results or {}), filled, filled if finance else None),
    )
