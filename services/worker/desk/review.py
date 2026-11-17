"""The review desk opening an idea (L-REVIEW.open) and moving its decide-by date (L-REVIEW.clock/2)."""

from __future__ import annotations

import datetime as dt
from typing import Any

from core.db import Conn
from desk import adapters, clock
from desk.store import Refused, actor, audit, audited, is_own, load_idea, now

# An idea on the desk, not yet decided: the sharer sees "With the review desk" or "Needs you".
ON_DESK = frozenset({"with_review_desk", "needs_you"})


def open_idea(conn: Conn, ref: str, user_id: str, at: dt.datetime | None = None) -> dict[str, Any]:
    """The first time any reviewer opens an idea it is "opened": the sharer's edit window closes, the conversation
    records it, and the idea is assigned to that reviewer (L-REVIEW.open/1). Idempotent; a reviewer opening their
    own idea only looks (V-ACC.review/14)."""
    t = at or now()
    with audited(conn), conn.transaction():
        idea = load_idea(conn, ref, lock=True)
        own = is_own(conn, user_id, idea)
        if own or idea["opened_at"] is not None or idea["status"] not in ON_DESK:
            return {"opened_at": idea["opened_at"], "first": False, "own": own}
        conn.execute(
            "UPDATE ideas SET opened_at = %s, opened_by = %s, reviewer_id = coalesce(reviewer_id, %s), "
            "edit_closes_at = least(coalesce(edit_closes_at, %s), %s) WHERE id = %s",
            (t, user_id, user_id, t, t, idea["id"]),
        )
        adapters.say(conn, str(idea["id"]), "desk.opened", author_user_id=user_id, at=t)
        audit(conn, actor(user_id), "desk.open", f"idea:{idea['idea_id']}")
        return {"opened_at": t, "first": True, "own": False}


def move_decide_by(
    conn: Conn, idea: dict[str, Any], user_id: str, to: dt.datetime, cal: clock.Calendar
) -> dt.datetime:
    """L-REVIEW.clock/2: the reviewer moves their own date, for instance past a question's deadline. The sharer is
    told the new date. Call inside the caller's transaction, with the idea locked."""
    new = to.astimezone(cal.tz).replace(minute=0, second=0, microsecond=0)
    if idea["decide_by"] is not None and new <= idea["decide_by"]:
        return idea["decide_by"]  # type: ignore[no-any-return]
    conn.execute("UPDATE ideas SET decide_by = %s WHERE id = %s", (new, idea["id"]))
    adapters.say(conn, str(idea["id"]), "desk.decide_by_moved", author_user_id=user_id)
    audit(conn, actor(user_id), "desk.move_decide_by", f"idea:{idea['idea_id']}",
          before={"decide_by": idea["decide_by"].isoformat() if idea["decide_by"] else None},
          after={"decide_by": new.isoformat()})  # fmt: skip
    return new


def ensure_on_desk(idea: dict[str, Any]) -> None:
    if idea["status"] not in ON_DESK:
        raise Refused(409, "already_decided", "This idea already has a decision.")
