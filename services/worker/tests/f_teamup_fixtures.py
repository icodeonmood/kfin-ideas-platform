"""Synthetic people, ideas and drafts for lane F's team-up tests (non-negotiable 11: invented names only).

Every helper writes through the test's own `db` connection (autocommit) and returns plain values. `Inbox` records
what lane A's `notify.post` and `notify.resolve` were asked to do, so the tests can check kinds, refs and keys.
"""

from __future__ import annotations

import datetime as dt
import secrets
import uuid
from dataclasses import dataclass, field
from typing import Any

import pytest

from core.db import Conn

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
_counter = iter(range(1, 10**6))
_made: dict[str, list[str]] = {"users": [], "ideas": []}  # what `clean` deletes after each test


def at(d: int, h: int = 10, m: int = 11) -> dt.datetime:
    return dt.datetime(2026, m, d, h, 0, tzinfo=IST)


def person(
    conn: Conn,
    name: str,
    *,
    city: str = "Hyderabad",
    area: str = "Investor service",
    role_title: str | None = "Senior executive",
    roles: tuple[str, ...] = (),
) -> dict[str, str]:
    user_id = str(uuid.uuid4())
    code = f"CTR-{secrets.token_hex(3)}"
    conn.execute(
        "INSERT INTO users (id, emp_id_hash, name, email, first_name, location, area, role_title) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (user_id, f"hash-{user_id}", name, f"{name.split()[0].lower()}.{next(_counter)}@example.test",
         name.split()[0], city, area, role_title),
    )  # fmt: skip
    _made["users"].append(user_id)
    conn.execute("INSERT INTO contributor_map (contributor_code, user_id) VALUES (%s, %s)", (code, user_id))
    for role in roles:
        conn.execute("INSERT INTO role_grants (user_id, role) VALUES (%s, %s)", (user_id, role))
    return {"id": user_id, "code": code, "name": name, "first_name": name.split()[0]}


def idea(
    conn: Conn,
    sharer: dict[str, str],
    *,
    title: str = "Rejection SMS codes confuse investors",
    status: str = "with_review_desk",
    shared_at: dt.datetime | None = None,
    **columns: Any,
) -> dict[str, Any]:
    """A shared idea with its sharer as crew lead."""
    shared_at = shared_at or at(14)
    ref = f"IDEA-2026-{1400 + next(_counter):06d}"
    cols = {
        "idea_id": ref, "contributor_code": sharer["code"], "status": status, "title": title,
        "summary": "Investors call the branch because the SMS gives a code, not a reason.",
        "city": "Hyderabad", "area": "Investor service", "kind": "problem", "shared_at": shared_at,
        **columns,
    }  # fmt: skip
    sql = f"INSERT INTO ideas ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))}) RETURNING *"  # noqa: S608
    row = conn.execute(sql, tuple(cols.values())).fetchone()
    assert row is not None
    _made["ideas"].append(str(row["id"]))
    conn.execute(
        "INSERT INTO crew_members (idea_uuid, contributor_code, role, via) VALUES (%s, %s, 'lead', 'shared')",
        (row["id"], sharer["code"]),
    )
    return dict(row)


def draft(
    conn: Conn, owner: dict[str, str], *, title: str = "Investors call to ask why a redemption was rejected"
) -> dict[str, Any]:
    """An unsent draft: no reference, status `draft`, masked title and summary."""
    row = conn.execute(
        "INSERT INTO ideas (contributor_code, status, title, summary, kind) VALUES (%s, 'draft', %s, %s, 'problem') "
        "RETURNING *",
        (
            owner["code"],
            title,
            "About 40 investors a day call the branch to ask why a redemption was rejected.",
        ),
    ).fetchone()
    assert row is not None
    _made["ideas"].append(str(row["id"]))
    return dict(row)


def crew(conn: Conn, idea_row: dict[str, Any], member: dict[str, str]) -> None:
    conn.execute(
        "INSERT INTO crew_members (idea_uuid, contributor_code, role, via) VALUES (%s, %s, 'crew', 'teamup')",
        (idea_row["id"], member["code"]),
    )


def similar(conn: Conn, a: dict[str, Any], b: dict[str, Any], strength: str = "close") -> None:
    conn.execute(
        "INSERT INTO similar_links (idea_uuid, other_idea_uuid, strength, reason, outcome) "
        "VALUES (%s, %s, %s, 'Same R07 SMS', 'previewed')",
        (a["id"], b["id"], strength),
    )


def clean(conn: Conn) -> None:
    """Delete the rows these fixtures made, and only those: their ideas and drafts first (crews, requests, merges,
    conversation lines, similar-ideas links and question sets go with them), then their people (contributor codes,
    roles and remembered idempotency keys go with them). `audit_log` keeps its rows: IDs only."""
    ideas, users = list(_made["ideas"]), list(_made["users"])
    _made["ideas"].clear()
    _made["users"].clear()
    if ideas:
        conn.execute("DELETE FROM ideas WHERE id = ANY(%s::uuid[])", (ideas,))
    if users:
        conn.execute("DELETE FROM users WHERE id = ANY(%s::uuid[])", (users,))


def crew_rows(conn: Conn, idea_row: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in conn.execute(
            "SELECT contributor_code, role, via, merge_id, teamup_request_id, left_how, removed_by_code "
            "FROM crew_members WHERE idea_uuid = %s ORDER BY id",
            (idea_row["id"],),
        ).fetchall()
    ]


def live_crew(conn: Conn, idea_row: dict[str, Any]) -> dict[str, str]:
    """code -> role, live members only."""
    return {
        str(r["contributor_code"]): str(r["role"])
        for r in conn.execute(
            "SELECT contributor_code, role FROM crew_members WHERE idea_uuid = %s AND left_at IS NULL",
            (idea_row["id"],),
        ).fetchall()
    }


def events(conn: Conn, idea_row: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return [
        (str(r["event"]), dict(r["payload"]))
        for r in conn.execute(
            "SELECT event, payload FROM conversation_entries WHERE idea_uuid = %s ORDER BY at, id",
            (idea_row["id"],),
        ).fetchall()
    ]


def audit_rows(conn: Conn, action_prefix: str, request_id: str | None = None) -> list[dict[str, Any]]:
    """Audit entries by action prefix, and by request when given (`audit_log` is not emptied between tests)."""
    return [
        dict(r)
        for r in conn.execute(
            "SELECT actor, action, entity, before, after FROM audit_log WHERE action LIKE %s "
            "AND (%s::text IS NULL OR after->>'request_id' = %s) ORDER BY id",
            (f"{action_prefix}%", request_id, request_id),
        ).fetchall()
    ]


def status_of(conn: Conn, idea_row: dict[str, Any]) -> dict[str, Any]:
    row = conn.execute("SELECT status, merged_into FROM ideas WHERE id = %s", (idea_row["id"],)).fetchone()
    assert row is not None
    return dict(row)


@dataclass
class Inbox:
    posts: list[dict[str, Any]] = field(default_factory=list)
    resolved: list[str] = field(default_factory=list)

    def kinds(self) -> list[str]:
        return [p["kind"] for p in self.posts]

    def of(self, kind: str) -> list[dict[str, Any]]:
        return [p for p in self.posts if p["kind"] == kind]


def record_inbox(monkeypatch: pytest.MonkeyPatch) -> Inbox:
    """Record lane A's `notify.post` and `notify.resolve` calls (resolve may not be on `main` yet)."""
    import notify

    box = Inbox()

    def post(conn: Conn, kind: str, recipients: list[str], **kw: Any) -> notify.Posted:
        box.posts.append({"kind": kind, "recipients": list(recipients), **kw})
        return notify.Posted()

    def resolve(conn: Conn, dedupe_key: str, *, recipients: list[str] | None = None) -> int:
        box.resolved.append(dedupe_key)
        return 1

    monkeypatch.setattr(notify, "post", post)
    monkeypatch.setattr(notify, "resolve", resolve, raising=False)
    return box
