"""Who may read and write an idea's conversation (L-CONVO/2, /6; L-AUDIT.permissions "Read … conversation").

The sharer and the review desk from the start; the crew once there is one; the build team once chosen; the Ones
Committee always (L-AUDIT.permissions). A person mentioned in a message who is none of these may read the messages
that mention them, and their own replies, and nothing else (BLD-F052); a removed message grants nothing. Anyone
else gets 404, never 403, so the answer never says that the conversation exists.

Files on messages and answers go only to readers the attachment route lets open them (BLD-F062, DEC-107): the
sharer, and the roles `view_review_queue` names in `policy/rbac.yaml` (`apps/web/src/server/attachments.ts`,
`accessible()`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from convo.store import Refused, code_of, not_found
from core.db import Conn

DESK_ROLES = ("reviewer",)
COMMITTEE_ROLES = ("committee", "core_committee", "core_chair")
# `view_review_queue` in policy/rbac.yaml (core_chair is an alias of core_committee): who opens a file besides the
# sharer. Keep in step with `accessible()` in apps/web/src/server/attachments.ts (BLD-F062).
FILE_ROLES = ("reviewer", "core_committee", "core_chair", "admin")


@dataclass(frozen=True)
class Reader:
    user_id: str
    code: str | None
    sharer: bool = False
    crew: bool = False  # on the crew now, the lead included
    desk: bool = False
    committee: bool = False
    build: bool = False
    mentioned: bool = False  # mentioned in at least one message that is not removed
    files: bool = False  # may open the files on messages and answers (BLD-F062)

    @property
    def full(self) -> bool:
        """Reads every entry. A mention-only reader reads only their messages (BLD-F052)."""
        return self.sharer or self.crew or self.desk or self.committee or self.build

    @property
    def may_attach(self) -> bool:
        """Adds files to a message: the sharer, the review desk and the core committee, the readers who can open
        them (BLD-F063). The crew, the build team and a mentioned person write without files."""
        return self.files and self.full

    @property
    def staff(self) -> bool:
        """Speaks as the review desk or the committee: staff, and not on the idea themselves."""
        return (self.desk or self.committee) and not (self.sharer or self.crew or self.build)


def _roles(conn: Conn, user_id: str) -> set[str]:
    rows = conn.execute(
        "SELECT role FROM role_grants WHERE user_id = %s AND valid_from <= now() "
        "AND (valid_to IS NULL OR valid_to > now())",
        (user_id,),
    ).fetchall()
    return {str(r["role"]) for r in rows}


def is_build_member(conn: Conn, idea: dict[str, Any], user_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM build_teams b WHERE b.idea_uuid = %s AND (b.lead_user_id = %s OR EXISTS ("
        "  SELECT 1 FROM role_grants g WHERE g.user_id = %s AND g.role = 'build_team' AND g.scope_id = %s"
        "  AND g.valid_from <= now() AND (g.valid_to IS NULL OR g.valid_to > now())))",
        (idea["id"], user_id, user_id, idea["idea_id"]),
    ).fetchone()
    return row is not None


def reader(conn: Conn, idea: dict[str, Any], user_id: str) -> Reader:
    """The reader's standing on this idea, or 404 when they may not read its conversation."""
    code = code_of(conn, user_id)
    roles = _roles(conn, user_id)
    crew = (
        code is not None
        and conn.execute(
            "SELECT 1 FROM crew_members WHERE idea_uuid = %s AND contributor_code = %s AND left_at IS NULL",
            (idea["id"], code),
        ).fetchone()
        is not None
    )
    mentioned = (
        conn.execute(
            "SELECT 1 FROM conversation_entries WHERE idea_uuid = %s AND type = 'message' AND deleted_at IS NULL "
            "AND mentions @> ARRAY[%s]::uuid[]",
            (idea["id"], user_id),
        ).fetchone()
        is not None
    )
    sharer = code is not None and code == idea["contributor_code"]
    r = Reader(
        user_id=user_id,
        code=code,
        sharer=sharer,
        crew=crew,
        desk=bool(roles & set(DESK_ROLES)),
        committee=bool(roles & set(COMMITTEE_ROLES)),
        build=is_build_member(conn, idea, user_id),
        mentioned=mentioned,
        files=sharer or bool(roles & set(FILE_ROLES)),
    )
    if not (r.full or r.mentioned):
        raise not_found()
    return r


def sees_desk_names(conn: Conn, user_id: str) -> bool:
    """DEC-111: only the review desk and the Ones Committee read the names of the people at the review desk. The same
    test as `Ctx.sees_desk` (a `Reader`'s `desk` or `committee`), for a person who is not the one reading."""
    return bool(_roles(conn, user_id) & {*DESK_ROLES, *COMMITTEE_ROLES})


def may_read_full(conn: Conn, idea: dict[str, Any], user_id: str) -> bool:
    """For mentions: is this person already in the conversation (so a mention adds no access)?"""
    try:
        return reader(conn, idea, user_id).full
    except Refused:
        return False
