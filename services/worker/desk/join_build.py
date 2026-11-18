"""Ask to join the build team (L-DECIDE.rules/6, A-API `POST /ideas/:id/join-build`; DEC-111, BLD-B256).

After a Pick, the sharer or a member of the idea's crew can ask to join the build team, until the programme admin
chooses it (L-DECIDE.after). The ask is kept once per person (`join_build_asks`), written to `audit_log` with IDs only,
and shown to the programme admin when the team is chosen (S-ADMIN, `asks_for_idea`). S-06 reads `join_build_for`
through the decision payload (`committee.decision_for_viewer`).

On an idea a Pick joined (status merged, L-MERGE.desk/5) the page shows the lead's Pick, so the ask goes to the lead:
one team builds one fix. Its sharer is credited on the lead (`store.own_codes`) and its crew moved there.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any, Literal

from core.db import Conn
from desk import clock, promises
from desk.store import Refused, actor, audit, is_own, load_idea, now

State = Literal["open", "not_picked", "team_chosen"]

# NOT DRAWN (wording for HR to sign off with S-06's "ask sent" line): the refusals' messages.
NOT_PICKED = "You can ask to join the build team once the idea is picked."
TEAM_CHOSEN = "The build team for this idea has been chosen."
NOT_YOURS = "Only the sharer and the crew can ask to join the build team."


def _target(conn: Conn, idea: dict[str, Any]) -> dict[str, Any]:
    """The idea whose Pick and build team the ask is for: the lead, when a Pick joined this idea to it."""
    from desk.committee import _joined_into

    return _joined_into(conn, idea) or idea


def _valid_user(user_id: str) -> bool:
    try:
        uuid.UUID(str(user_id))
    except ValueError:
        return False
    return True


def _may_ask(conn: Conn, user_id: str, idea: dict[str, Any]) -> bool:
    """The sharer (and every sharer credited through a merge) or an active member of the crew."""
    from desk.committee import _on_crew

    return _valid_user(user_id) and (is_own(conn, user_id, idea) or _on_crew(conn, user_id, idea))


def _latest(conn: Conn, idea: dict[str, Any]) -> tuple[str | None, dt.datetime | None]:
    """The latest decision as it stands (a committee reversal's choice when there is one) and the date it set for
    choosing the team: a desk Pick's `idea_decisions.team_by` (L-DECIDE.rules/6), or a reversal to Pick's own
    `decision_reversals.team_by` (L-COMMITTEE.rules/5, BLD-B259). A reversal to Pick made before that column has
    none stored; its date is worked out from the reversal time the same way. Any other reversal sets none."""
    r = conn.execute(
        "SELECT d.choice, d.team_by, r.id AS reversal_id, r.to_choice, r.at AS reversed_at, "
        "r.team_by AS reversed_team_by FROM idea_decisions d "
        "LEFT JOIN decision_windows w ON w.decision_id = d.id "
        "LEFT JOIN decision_reversals r ON r.window_id = w.id "
        "WHERE d.idea_uuid = %s ORDER BY d.at DESC LIMIT 1",
        (idea["id"],),
    ).fetchone()
    if r is None:
        return None, None
    if r["reversal_id"] is None:
        return str(r["choice"]), r["team_by"]
    choice = str(r["to_choice"])
    if choice != "pick":
        return choice, None
    return choice, r["reversed_team_by"] or reversal_team_by(r["reversed_at"])


def reversal_team_by(reversed_at: dt.datetime) -> dt.datetime:
    """The team date of a reversal to Pick: a desk Pick's rule from the reversal time (L-DECIDE.rules/6)."""
    return clock.team_by(reversed_at, promises.get(), clock.office_calendar())


def _state(conn: Conn, idea: dict[str, Any], choice: str | None) -> State:
    """Whether an ask can be made now. The latest decision must stand as a Pick: a committee reversal to Not now or
    Not picked ends it, a reversal to Pick takes its consequences (L-COMMITTEE.rules/3). The team is chosen once
    `build_teams` has the idea, or the idea has moved on to being built or shipped."""
    if choice != "pick":
        return "not_picked"
    team = conn.execute("SELECT 1 FROM build_teams WHERE idea_uuid = %s", (idea["id"],)).fetchone()
    if team is not None or idea["status"] in ("being_built", "shipped"):
        return "team_chosen"
    return "open" if idea["status"] == "picked" else "not_picked"


def _asked_at(conn: Conn, idea_uuid: Any, user_id: str) -> dt.datetime | None:
    row = conn.execute(
        "SELECT asked_at FROM join_build_asks WHERE idea_uuid = %s AND user_id = %s", (idea_uuid, user_id)
    ).fetchone()
    return row["asked_at"] if row is not None else None


def ask(conn: Conn, ref: str, user_id: str, at: dt.datetime | None = None) -> dict[str, Any]:
    """POST /ideas/:id/join-build. Returns `{asked_at}`; a repeat while asking is open returns the first ask's time
    and changes nothing. Refusals, checked first: 404 not_found (no such idea), 403 forbidden (not the sharer or
    crew), 409 not_picked (no standing Pick), 409 team_chosen (the build team is chosen)."""
    t = at or now()
    idea = load_idea(conn, ref)
    with conn.transaction():
        target = _target(conn, idea)
        # the programme admin's choose_team locks the idea row: an ask and a team choice do not cross
        locked = conn.execute("SELECT * FROM ideas WHERE id = %s FOR SHARE", (target["id"],)).fetchone()
        if locked is None:
            raise Refused(404, "not_found")
        target = dict(locked)
        if not _may_ask(conn, user_id, target):
            raise Refused(403, "forbidden", NOT_YOURS)
        state = _state(conn, target, _latest(conn, target)[0])
        if state == "not_picked":
            raise Refused(409, "not_picked", NOT_PICKED)
        if state == "team_chosen":
            raise Refused(409, "team_chosen", TEAM_CHOSEN)
        # a repeat keeps the first ask and its time, with no second audit row
        made = conn.execute(
            "INSERT INTO join_build_asks (idea_uuid, user_id, asked_at) VALUES (%s, %s, %s) "
            "ON CONFLICT (idea_uuid, user_id) DO NOTHING RETURNING id",
            (target["id"], user_id, t),
        ).fetchone()
        if made is not None:
            audit(conn, actor(user_id), "idea.join_build_ask", f"idea:{target['idea_id']}",
                  after={"ask_id": str(made["id"])})  # fmt: skip
        asked = _asked_at(conn, target["id"], user_id)
    assert asked is not None
    return {"asked_at": asked.isoformat()}


def asks_for_idea(conn: Conn, idea_uuid: str) -> list[dict[str, Any]]:
    """Who asked to join the build team, oldest first: `{user_id, name, asked_at}` (S-ADMIN, lane A's read)."""
    return [
        {"user_id": str(r["user_id"]), "name": r["name"], "asked_at": r["asked_at"].isoformat()}
        for r in conn.execute(
            "SELECT a.user_id, u.name, a.asked_at FROM join_build_asks a JOIN users u ON u.id = a.user_id "
            "WHERE a.idea_uuid = %s ORDER BY a.asked_at, a.id",
            (idea_uuid,),
        ).fetchall()
    ]


def join_build_for(conn: Conn, idea_uuid: str, user_id: str) -> dict[str, Any] | None:
    """The decision payload's `join_build` (S-06): None for anyone who is not the sharer or crew; else `can_ask`, true
    only when an ask would succeed now and none has been made, `asked_at`, the person's ask or None, and `reply_by`,
    the latest decision's `team_by` (the team is chosen by then; S-06's "Asked. The build lead replies by …") or
    None when it set none."""
    row = conn.execute("SELECT * FROM ideas WHERE id = %s", (idea_uuid,)).fetchone()
    if row is None:
        return None
    idea = dict(row)
    if not _may_ask(conn, user_id, idea):
        return None
    asked = _asked_at(conn, idea["id"], user_id)
    choice, team_by = _latest(conn, idea)
    return {
        "can_ask": asked is None and _state(conn, idea, choice) == "open",
        "asked_at": asked.isoformat() if asked is not None else None,
        "reply_by": team_by.isoformat() if team_by is not None else None,
    }
