"""Synthetic people and ideas for lane F's database tests: the crew deck and search (non-negotiable 11: invented
names and made-up text only, none of the pack's demo cast).

Every helper writes through the test's own `db` connection (autocommit) and returns plain values.
"""

from __future__ import annotations

import datetime as dt
import secrets
import uuid
from typing import Any

from core.db import Conn
from onepc.context import seal_text

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
NOW = dt.datetime(2026, 11, 17, 12, 0, tzinfo=IST)  # Tuesday
_counter = iter(range(1, 10**6))


def ago(days: float) -> dt.datetime:
    return NOW - dt.timedelta(days=days)


def person(
    conn: Conn,
    name: str,
    *,
    city: str = "Hyderabad",
    area: str = "Investor service",
    roles: tuple[str, ...] = (),
    code: bool = True,
) -> dict[str, Any]:
    """A user, with a contributor code unless `code=False` (someone who has never shared or helped)."""
    user_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO users (id, emp_id_hash, name, email, first_name, location, area) VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (user_id, f"hash-{user_id}", name, f"{name.split()[0].lower()}.{next(_counter)}@example.test",
         name.split()[0], city, area),
    )  # fmt: skip
    ctr = f"CTR-{secrets.token_hex(3)}" if code else None
    if ctr:
        conn.execute("INSERT INTO contributor_map (contributor_code, user_id) VALUES (%s, %s)", (ctr, user_id))
    for role in roles:
        conn.execute("INSERT INTO role_grants (user_id, role) VALUES (%s, %s)", (user_id, role))
    return {"id": user_id, "code": ctr, "name": name, "first_name": name.split()[0]}


def idea(
    conn: Conn,
    sharer: dict[str, Any],
    title: str,
    *,
    summary: str = "Branches hear the same question every day. Nobody has a written answer to give.",
    status: str = "with_review_desk",
    shared_days: float | None = 3,
    area: str = "Operations",
    city: str = "Mumbai",
    helpers: tuple[str, ...] = (),
    helper_text: str | None = None,
    **columns: Any,
) -> dict[str, Any]:
    """An idea with its sharer as crew lead once shared. A draft (`shared_days=None`) has no reference."""
    shared = ago(shared_days) if shared_days is not None else None
    n = next(_counter)
    cols = {
        "idea_id": f"IDEA-2026-{7000 + n:06d}" if shared else None,
        "contributor_code": sharer["code"], "status": "draft" if shared is None else status, "kind": "problem",
        "title": title, "summary": summary, "area": area, "city": city if shared else None, "shared_at": shared,
        "helper_picks": list(helpers), "helper_text": helper_text, **columns,
    }  # fmt: skip
    names = ", ".join(cols)
    marks = ", ".join(["%s"] * len(cols))
    row = conn.execute(f"INSERT INTO ideas ({names}) VALUES ({marks}) RETURNING *", tuple(cols.values())).fetchone()  # noqa: S608 (this file's own columns)
    assert row is not None
    if shared is not None:
        conn.execute(
            "INSERT INTO crew_members (idea_uuid, contributor_code, role, via, joined_at) "
            "VALUES (%s, %s, 'lead', 'shared', %s)",
            (row["id"], sharer["code"], shared),
        )
    return dict(row)


def join(conn: Conn, idea_row: dict[str, Any], member: dict[str, Any], *, days: float = 1) -> None:
    conn.execute(
        "INSERT INTO crew_members (idea_uuid, contributor_code, role, via, joined_at) VALUES (%s, %s, 'crew', 'teamup', %s)",
        (idea_row["id"], member["code"], ago(days)),
    )


def request(conn: Conn, idea_row: dict[str, Any], who: dict[str, Any], *, state: str = "sent", days: float = 0.5) -> str:
    rid = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO teamup_requests (id, idea_uuid, from_code, note_encrypted, state, sent_at) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (rid, idea_row["id"], who["code"],
         seal_text("teamup_requests", "note_encrypted", rid, "I see this at my counter every week and can help."),
         state, ago(days)),
    )  # fmt: skip
    return rid


def link(conn: Conn, mine: dict[str, Any], other: dict[str, Any], *, strength: str = "close", reason: str = "", rank: int = 1) -> None:
    conn.execute(
        "INSERT INTO similar_links (idea_uuid, other_idea_uuid, strength, reason, rank) VALUES (%s, %s, %s, %s, %s)",
        (mine["id"], other["id"], strength, reason, rank),
    )


def message(conn: Conn, idea_row: dict[str, Any], text: str, seq: int = 1) -> str:
    """One of the sharer's own messages, stored as the masked copy (the cut-over's `idea_messages`)."""
    mid = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO idea_messages (id, idea_uuid, seq, via, text_encrypted, char_count) VALUES (%s, %s, %s, 'typed', %s, %s)",
        (mid, idea_row["id"], seq, seal_text("idea_messages", "text_encrypted", mid, text), len(text)),
    )
    return mid


def decision(conn: Conn, idea_row: dict[str, Any], reviewer: dict[str, Any], choice: str, reason: str) -> str:
    did = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO idea_decisions (id, idea_uuid, choice, reason_encrypted, by_user_id, at, return_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (did, idea_row["id"], choice, seal_text("idea_decisions", "reason_encrypted", did, reason), reviewer["id"],
         ago(1), ago(-90) if choice == "not_now" else None),
    )  # fmt: skip
    return did
