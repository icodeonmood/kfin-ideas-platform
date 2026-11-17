"""Synthetic people and ideas for the review side's database tests (non-negotiable 11: invented names only).

Every helper writes through the same `db` connection the test uses (autocommit) and returns plain values. What
they make is removed when the test ends (`clean_up_desk_rows`, autouse in every lane B database test module that
imports it), so no synthetic person or idea is left in the shared test database for another lane's tests: on 17 Nov
leftover users broke the seed test.
"""

from __future__ import annotations

import datetime as dt
import secrets
import sys
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import pytest

from core.db import Conn

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
_counter = iter(range(1, 10**6))
_made: dict[str, list[str]] = {
    "users": [],
    "ideas": [],
}  # what this test's helpers created, removed at its end


@pytest.fixture(autouse=True)
def clean_up_desk_rows(test_database: str) -> Iterator[None]:
    """Remove every idea and person the helpers made in this test, with what hangs off them: ideas first (their
    decisions, windows, merges, question sets, answers, files and crew go with them), then the people (contributor
    codes and role grants go with them). Rows the services wrote about them by ID only, such as `audit_log`, stay."""
    _made["users"].clear()
    _made["ideas"].clear()
    yield
    if not (_made["users"] or _made["ideas"]):
        return
    from core.db import connect
    from tests import helpers

    with connect(helpers.db_url(test_database), autocommit=True) as conn:
        remove_made(conn, _made["users"], _made["ideas"])
    _made["users"].clear()
    _made["ideas"].clear()


def remove_made(conn: Conn, users: list[str], ideas: list[str]) -> None:
    """Delete these people and ideas, everything that hangs off them, and the `jobs` rows keyed to the ideas, their
    decision windows, merges and question sets (lane A's timers, through `adapters.schedule`), so another lane's
    job runner never picks one up. Audit rows stay."""
    with conn.transaction():
        codes = [
            str(r["contributor_code"])
            for r in conn.execute(
                "SELECT contributor_code FROM contributor_map WHERE user_id = ANY(%s::uuid[])", (users,)
            ).fetchall()
        ]
        made = conn.execute(
            "SELECT id::text AS id FROM ideas WHERE id = ANY(%s::uuid[]) OR contributor_code = ANY(%s)",
            (ideas, codes),
        ).fetchall()
        idea_ids = [str(r["id"]) for r in made]
        keys = idea_ids + [
            str(r["id"])
            for r in conn.execute(
                "SELECT w.id::text AS id FROM decision_windows w LEFT JOIN idea_decisions d ON d.id = w.decision_id "
                "LEFT JOIN merges m ON m.id = w.merge_id "
                "WHERE d.idea_uuid = ANY(%(i)s::uuid[]) OR m.lead_idea_uuid = ANY(%(i)s::uuid[]) "
                "OR m.merged_idea_uuid = ANY(%(i)s::uuid[]) "
                "UNION SELECT id::text FROM idea_decisions WHERE idea_uuid = ANY(%(i)s::uuid[]) "
                "UNION SELECT id::text FROM merges WHERE lead_idea_uuid = ANY(%(i)s::uuid[]) "
                "OR merged_idea_uuid = ANY(%(i)s::uuid[]) "
                "UNION SELECT id::text FROM question_sets WHERE idea_uuid = ANY(%(i)s::uuid[])",
                {"i": idea_ids},
            ).fetchall()
        ]
        if keys:
            conn.execute(
                "DELETE FROM jobs j WHERE EXISTS (SELECT 1 FROM unnest(%s::text[]) AS k(id) "
                "WHERE strpos(j.payload::text, k.id) > 0 OR strpos(coalesce(j.dedupe_key, ''), k.id) > 0)",
                (keys,),
            )
        conn.execute("DELETE FROM ideas WHERE id = ANY(%s::uuid[])", (idea_ids,))
        conn.execute("DELETE FROM users WHERE id = ANY(%s::uuid[])", (users,))


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
    _made["users"].append(user_id)
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
    _made["ideas"].append(str(row["id"]))
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


@dataclass(frozen=True)
class Post:
    """One `notify.post` call, as lane B made it."""

    kind: str
    recipients: list[str]
    needs_you: bool
    due_at: dt.datetime | None
    sender: str
    dedupe_key: str | None
    actions: list[str]  # the buttons' labels


class FakeNotify:
    """A stand-in for lane A's `notify` (BLD-A180) that records every `post` and `resolve`, so a test can check who is
    told what (L-INBOX.kinds) without lane A's inbox tables. Installed by the `fake_notify` fixture."""

    def __init__(self) -> None:
        self.posts: list[Post] = []
        self.resolved: list[str] = []

    @dataclass(frozen=True)
    class Action:
        label: str
        style: str = "line"
        to: str | None = None
        op: str | None = None

    def post(self, conn: Conn, kind: str, recipients: list[str], **kw: Any) -> None:
        _ = conn
        self.posts.append(Post(kind, list(recipients), bool(kw.get("needs_you")), kw.get("due_at"),
                               str(kw.get("sender")), kw.get("dedupe_key"),
                               [a.label for a in kw.get("actions") or ()]))  # fmt: skip

    def resolve(self, conn: Conn, dedupe_key: str) -> int:
        _ = conn
        self.resolved.append(dedupe_key)
        return 1

    def of(self, kind: str) -> list[Post]:
        return [p for p in self.posts if p.kind == kind]


def install_fake_notify(monkeypatch: pytest.MonkeyPatch) -> FakeNotify:
    """`notify` in sys.modules for this test only; `monkeypatch` puts the real one back when the test ends."""
    fake = FakeNotify()
    monkeypatch.setitem(sys.modules, "notify", fake)
    return fake
