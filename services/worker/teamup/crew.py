"""Leaving a crew, and the lead removing a member (L-TEAMUP.rules/11, NOT DRAWN default): a member can leave from
the idea's page; the lead can remove a member; both are logged and announced in the conversation. The lead stays:
a crew has one lead, the sharer (L-TEAMUP.rules/10).
"""

from __future__ import annotations

from typing import Any

from core.db import Conn
from teamup import adapters
from teamup.store import (
    Refused,
    actor,
    audit,
    audited,
    code_of,
    crew_codes,
    crew_role,
    entity_of,
    lead_code,
    load_idea,
    require_code,
)
from teamup.store import now as clock_now


def _off(conn: Conn, idea_uuid: Any, code: str, how: str, by: str | None) -> None:
    conn.execute(
        "UPDATE crew_members SET left_at = %s, left_how = %s, removed_by_code = %s "
        "WHERE idea_uuid = %s AND contributor_code = %s AND left_at IS NULL",
        (clock_now(), how, by, idea_uuid, code),
    )


def leave(conn: Conn, ref: str, user_id: str) -> dict[str, Any]:
    """`POST /ideas/:id/crew/leave` (BLD-F018). Errors: not_on_crew, lead_stays."""
    with audited(conn), conn.transaction():
        idea = load_idea(conn, ref, lock=True)
        code = require_code(conn, user_id)
        role = crew_role(conn, idea["id"], code)
        if role is None:
            raise Refused(409, "not_on_crew", "You’re not on this crew.")
        if role == "lead":
            raise Refused(409, "lead_stays", "You lead this idea, so you stay on its crew.")
        _off(conn, idea["id"], code, "left", None)
        adapters.say(conn, str(idea["id"]), "crew.left", author_code=code)
        audit(conn, actor(user_id), "crew.leave", entity_of(idea), after={"member_code": code})
        return {"idea_id": idea["idea_id"], "me": None, "crew_count": len(crew_codes(conn, idea["id"]))}


def remove(conn: Conn, ref: str, member: str, user_id: str) -> dict[str, Any]:
    """`DELETE /ideas/:id/crew/:member` by the lead (BLD-F018). `member` is the person's id (PersonRef.id, what
    screens hold) or their contributor code. Errors: not_lead (403, audited), not_on_crew, lead_stays."""
    with audited(conn), conn.transaction():
        idea = load_idea(conn, ref, lock=True)
        code = require_code(conn, user_id)
        if lead_code(conn, idea) != code:
            raise Refused(
                403, "not_lead", "Only the lead of this idea can remove someone.",
                audit=(actor(user_id), "crew.remove_refused", entity_of(idea), {}),
            )  # fmt: skip
        member_code = member if member.startswith("CTR-") else code_of(conn, member)
        role = crew_role(conn, idea["id"], member_code) if member_code else None
        if member_code is None or role is None:
            raise Refused(404, "not_on_crew", "That person is not on this crew.")
        if role == "lead":
            raise Refused(409, "lead_stays", "You lead this idea, so you stay on its crew.")
        _off(conn, idea["id"], member_code, "removed", code)
        adapters.say(
            conn, str(idea["id"]), "crew.removed", author_code=code, payload={"member_code": member_code}
        )
        audit(conn, actor(user_id), "crew.remove", entity_of(idea), after={"member_code": member_code})
        return {"idea_id": idea["idea_id"], "removed": True, "crew_count": len(crew_codes(conn, idea["id"]))}
