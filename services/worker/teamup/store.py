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

# Every 404 says the same, whatever is missing or hidden, so it never tells anyone that something exists (BLD-F025).
NOT_FOUND = "We couldn’t find that."


class Refused(Exception):
    """An action the rules do not allow, answered as `{error: {code, message, field?}}` (A-API.conventions/2).
    `audit` is written after the rollback, so a refused attempt that must leave a trace survives it. A 404
    `not_found` carries the one message ready to show (`NOT_FOUND`)."""

    def __init__(
        self,
        status: int,
        code: str,
        message: str | None = None,
        field: str | None = None,
        audit: tuple[str, str, str, dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(code)
        if message is None and code == "not_found":
            message = NOT_FOUND
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


def hidden_from(conn: Conn, idea: dict[str, Any], code: str | None) -> bool:
    """BLD-E011, BLD-F023, L-SUBMIT.withdraw/2: a withdrawn idea is hidden from everyone but its sharer, the people who were
    on its crew (whether or not they have left) and the people who asked to join it (a team-up request or a draft
    merge request, in any state)."""
    if idea["status"] != "withdrawn":
        return False
    if code is None:
        return True
    if idea["contributor_code"] == code:
        return False
    row = conn.execute(
        "SELECT 1 FROM crew_members WHERE idea_uuid = %s AND contributor_code = %s "
        "UNION ALL SELECT 1 FROM teamup_requests WHERE idea_uuid = %s AND from_code = %s "
        "UNION ALL SELECT 1 FROM merge_requests WHERE other_idea_uuid = %s AND from_code = %s LIMIT 1",
        (idea["id"], code, idea["id"], code, idea["id"], code),
    ).fetchone()
    return row is None


def load_idea_for(conn: Conn, ref: str, code: str | None, *, lock: bool = False) -> dict[str, Any]:
    """`load_idea` for this person: a withdrawn idea they may not see is not found, exactly like a missing one."""
    idea = load_idea(conn, ref, lock=lock)
    if hidden_from(conn, idea, code):
        raise Refused(404, "not_found")
    return idea


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


TEAM_UP_REFUSED: dict[str, str] = {
    "idea_closed": "This idea is no longer open to team up.",
    "already_on_crew": "You’re on the crew.",
}


def team_up_refusal(conn: Conn, idea: dict[str, Any], code: str | None) -> str | None:
    """L-TEAMUP.rules/1: why this person may not ask to team up on this shared idea, else None. `idea_closed` for a
    closed, withdrawn or merged-away idea (`is_closed`), then `already_on_crew` when `code` is on its live crew. The
    one rule `POST /ideas/:id/team-up` refuses by, and the similar read's `can_team_up` (BLD-C187), so a tile never
    offers "Team up" that the send would refuse. A waiting request of theirs is rules/4, read on its own."""
    if is_closed(str(idea["status"])):
        return "idea_closed"
    if code is not None and crew_role(conn, idea["id"], code) is not None:
        return "already_on_crew"
    return None


@dataclass(frozen=True)
class SeenLead:
    """The idea's lead as one viewer may see them (BLD-F029, DEC-104). `ref` is an E-ENTITIES PersonRef, or lane C's
    hidden person ("A colleague", no initials, an opaque id, never a users.id); `first` is the first name to put in a
    sentence, or None when the lead is not named to this viewer, so the words say "the lead"."""

    ref: dict[str, Any]
    first: str | None


def lead_seen_by(conn: Conn, idea: dict[str, Any], user_id: str | None, code: str | None) -> SeenLead:
    """BLD-F029: team-up names the idea's lead by DEC-104, through lane C's helpers (`similar.preview`), as the
    crew cards do (BLD-F042). A lead who hid their name from the Wall in Profile (`person_settings
    .show_name_on_wall`), or is no longer active, is not named to someone asking to join, and their users.id never
    leaves the server. The idea's live crew (the lead included) and the review desk and the Ones Committee always
    see the name; so once a request is approved the requester, now on the crew, does too."""
    from similar.preview import Viewer, hidden_person, person_refs

    lc = lead_code(conn, idea)
    hidden_id = hidden_person(lc)["id"]
    ref = person_refs(conn, [lc], names_always=False)[lc]
    if ref["id"] == hidden_id:
        on_crew = code is not None and crew_role(conn, idea["id"], code) is not None
        if on_crew or Viewer.of(conn, user_id).desk:
            ref = person_refs(conn, [lc], names_always=True)[lc]
    named = ref["id"] != hidden_id
    return SeenLead(ref, str(ref["first_name"]) if named else None)


@dataclass(frozen=True)
class Person:
    """E-ENTITIES PersonRef from the users row, with no Wall check. Team-up uses it only for the requester as the lead
    reads them and for the person's own details (BLD-F075); the lead goes through `lead_seen_by` (BLD-F029)."""

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


def _digest(body: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


def remembered(conn: Conn, user_id: str, key: str | None, route: str, body: dict[str, Any]) -> str | None:
    """The row id a create with this key already made, if it is still remembered (24 hours). The same key sent with
    another request (another idea, another draft, other words, or another route) is refused, never answered with
    the first result (BLD-F026). Callers check before and again after taking their lock."""
    k = _usable_key(key)
    if k is None:
        return None
    row = conn.execute(
        "SELECT route, request_hash, response_json FROM idempotency_keys WHERE user_id = %s AND key = %s "
        "AND expires_at > now()",
        (user_id, k),
    ).fetchone()
    if row is None:
        return None
    if row["route"] != route or row["request_hash"] != _digest(body):
        raise Refused(
            409, "key_reused", "Something changed since you last sent this. Refresh the page and try again."
        )
    made = row["response_json"].get("id") if isinstance(row["response_json"], dict) else None
    return str(made) if made else None


def remember(
    conn: Conn, user_id: str, key: str | None, route: str, body: dict[str, Any], made_id: str
) -> None:
    """Keep the created row's id (IDs only; the table's rule) against the key and a hash of the request."""
    k = _usable_key(key)
    if k is None:
        return
    digest = _digest(body)
    conn.execute(
        "INSERT INTO idempotency_keys (key, user_id, route, request_hash, status, response_json) "
        "VALUES (%s, %s, %s, %s, 201, %s) ON CONFLICT (user_id, key) DO NOTHING",
        (k, user_id, route, digest, Jsonb({"id": made_id})),
    )
