"""Synthetic people and ideas for lane F's conversation tests (non-negotiable 11: invented names only).

Every helper writes through the test's own `db` connection (autocommit) and returns plain values, and records the
people and ideas it makes so `clean` can delete them when the test ends: no user is left behind in the shared test
database (the seed's HR import refuses while active users are there).
"""

from __future__ import annotations

import datetime as dt
import secrets
import uuid
from typing import Any

from core.db import Conn

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
_counter = iter(range(1, 10**6))
_made: dict[str, list[str]] = {"users": [], "ideas": []}  # what `clean` deletes after each test


# A grant starts a minute back: `role_grants` is read with `valid_from <= now()`, and a Docker VM's clock can step back
# by a fraction of a second between the grant and the read, which made a just-granted role briefly not count.
GRANT = "INSERT INTO role_grants (user_id, role, scope_id, valid_from) VALUES (%s, %s, %s, now() - interval '1 minute')"


def at(d: int, h: int = 0, mi: int = 0, m: int = 11, y: int = 2026) -> dt.datetime:
    return dt.datetime(y, m, d, h, mi, tzinfo=IST)


def person(conn: Conn, name: str, *, city: str = "Hyderabad", area: str = "Investor service",
           roles: tuple[tuple[str, str | None], ...] = ()) -> dict[str, str]:  # fmt: skip
    """A user with a contributor code and any (role, scope) grants."""
    user_id = str(uuid.uuid4())
    code = f"CTR-{secrets.token_hex(3)}"
    conn.execute(
        "INSERT INTO users (id, emp_id_hash, name, email, first_name, location, area) VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (user_id, f"hash-{user_id}", name, f"{name.split()[0].lower()}.{next(_counter)}@example.test",
         name.split()[0], city, area),
    )  # fmt: skip
    _made["users"].append(user_id)
    conn.execute("INSERT INTO contributor_map (contributor_code, user_id) VALUES (%s, %s)", (code, user_id))
    for role, scope in roles:
        conn.execute(GRANT, (user_id, role, scope))
    return {"id": user_id, "code": code, "name": name, "first_name": name.split()[0]}


def idea(conn: Conn, sharer: dict[str, str], *, title: str = "Investors call to ask why a redemption was rejected",
         status: str = "with_review_desk", shared_at: dt.datetime | None = None, **columns: Any) -> dict[str, Any]:  # fmt: skip
    """A shared idea with its sharer as crew lead. Returns the row."""
    shared_at = shared_at or at(14, 10, 5)
    n = next(_counter)
    cols = {
        "idea_id": f"IDEA-2026-{3400 + n:06d}", "contributor_code": sharer["code"], "status": status,
        "title": title, "summary": "Investors call the branch because the SMS gives a code, not a reason.",
        "city": "Hyderabad", "area": "Investor service", "kind": "problem", "shared_at": shared_at,
        "edit_closes_at": shared_at + dt.timedelta(days=3), **columns,
    }  # fmt: skip
    sql = f"INSERT INTO ideas ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))}) RETURNING *"  # noqa: S608
    row = conn.execute(sql, tuple(cols.values())).fetchone()
    assert row is not None
    _made["ideas"].append(str(row["id"]))
    conn.execute(
        "INSERT INTO crew_members (idea_uuid, contributor_code, role, via, joined_at) "
        "VALUES (%s, %s, 'lead', 'shared', %s)",
        (row["id"], sharer["code"], shared_at),
    )
    return dict(row)


def join_crew(
    conn: Conn, idea_row: dict[str, Any], member: dict[str, str], when: dt.datetime | None = None
) -> None:
    conn.execute(
        "INSERT INTO crew_members (idea_uuid, contributor_code, role, via, joined_at) "
        "VALUES (%s, %s, 'crew', 'teamup', coalesce(%s, now()))",
        (idea_row["id"], member["code"], when),
    )


def leave_crew(conn: Conn, idea_row: dict[str, Any], member: dict[str, str]) -> None:
    conn.execute(
        "UPDATE crew_members SET left_at = now(), left_how = 'left' WHERE idea_uuid = %s AND contributor_code = %s",
        (idea_row["id"], member["code"]),
    )


def build_team(conn: Conn, idea_row: dict[str, Any], lead: dict[str, str], *members: dict[str, str]) -> None:
    conn.execute(
        "INSERT INTO build_teams (idea_uuid, name, lead_user_id) VALUES (%s, %s, %s)",
        (idea_row["id"], f"{lead['name']}’s team", lead["id"]),
    )
    for m in (lead, *members):
        conn.execute(GRANT, (m["id"], "build_team", idea_row["idea_id"]))


def clean(conn: Conn) -> None:
    """Delete the rows these fixtures made, and only those: their ideas first (crews, conversation lines, requests,
    merges, question sets, files and links go with them), then their people (contributor codes, roles, inbox items
    and remembered idempotency keys go with them). `audit_log` keeps its rows: IDs only."""
    ideas, users = list(_made["ideas"]), list(_made["users"])
    _made["ideas"].clear()
    _made["users"].clear()
    if ideas:
        conn.execute("DELETE FROM ideas WHERE id = ANY(%s::uuid[])", (ideas,))
    if users:
        conn.execute("DELETE FROM users WHERE id = ANY(%s::uuid[])", (users,))


def entries(conn: Conn, idea_uuid: Any) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM conversation_entries WHERE idea_uuid = %s ORDER BY at, id", (idea_uuid,)
        ).fetchall()
    ]


def question_set(
    conn: Conn, idea_row: dict[str, Any], reviewer: dict[str, str], parts: tuple[str, ...], at_: dt.datetime
) -> str:
    """A sent question set (lane B writes these; here for the conversation's reading only)."""
    from onepc.context import seal_text

    set_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO question_sets (id, idea_uuid, by_user_id, state, time_to_answer, sent_at, due_at) "
        "VALUES (%s, %s, %s, 'sent', '3d', %s, %s)",
        (set_id, idea_row["id"], reviewer["id"], at_, at_ + dt.timedelta(days=3)),
    )
    for seq, part in enumerate(parts, start=1):
        qid = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO questions (id, set_id, seq, part, text_encrypted) VALUES (%s, %s, %s, %s, %s)",
            (
                qid,
                set_id,
                seq,
                part,
                seal_text("questions", "text_encrypted", qid, f"Synthetic question {seq}?"),
            ),
        )
    return set_id


def answer_all(conn: Conn, set_id: str, sharer: dict[str, str], at_: dt.datetime) -> None:
    from onepc.context import seal_text

    for q in conn.execute(
        "SELECT id, seq, part FROM questions WHERE set_id = %s ORDER BY seq", (set_id,)
    ).fetchall():
        aid = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO answers (id, question_id, by_code, text_encrypted, added_to, saved_at, sent_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (aid, q["id"], sharer["code"], seal_text("answers", "text_encrypted", aid, f"Synthetic answer {q['seq']}."),
             q["part"], at_, at_),
        )  # fmt: skip
    conn.execute("UPDATE question_sets SET state = 'answered', answered_at = %s WHERE id = %s", (at_, set_id))


def attachment(
    conn: Conn, idea_row: dict[str, Any], owner: dict[str, str], file_state: str = "checked",
    name: str = "plain-rejection-reasons.xlsx",
) -> str:  # fmt: skip
    att_id = f"ATT-2026-{next(_counter) + 500000:06d}"
    conn.execute(
        "INSERT INTO attachments (id, idea_uuid, uploaded_by_code, name, mime, bytes, store_key, state, kind, "
        "file_state) VALUES (%s, %s, %s, %s, %s, 2048, %s, 'clean', 'file', %s)",
        (
            att_id,
            idea_row["id"],
            owner["code"],
            name,
            "application/vnd.ms-excel",
            f"clean/{att_id}",
            file_state,
        ),
    )
    return att_id
