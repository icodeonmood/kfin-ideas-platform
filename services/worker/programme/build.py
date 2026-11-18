"""After picking (L-DECIDE.after; J-ONE step 1): the programme admin chooses a picked idea's build team and lead,
and later marks it shipped.

- **Team chosen**: the idea moves to `being_built`. The team is a `build_teams` row (name, lead) and one
  `build_team` grant per member, scoped to the idea's IDEA- reference, so the conversation opens to them. The
  sharer's track shows "Being built" (S-06).
- **Shipped**: the idea moves to `shipped`, the sharer's track reaches "Shipped" and the Wall's Shipped column shows
  it; the 30- and 90-day measurements are scheduled (L-IMPACT/1).

Both moves tell the sharer and the crew through the existing `stage_moved` kind ("moved your idea to Being built",
"... to Shipped"; L-INBOX.kinds), with the stage in `refs.to`. The build team gets no Inbox item: no kind says "you
are on a build team", and "moved your idea" would not be true for them (BLD-A211). The admin tells them.

Status changes go through `ideas.status`; the cut-over's trigger stamps the time and keeps the history.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from core.db import Conn
from notify import post
from programme import impact
from programme.common import (
    Refused,
    audit,
    credited_users,
    crew_users,
    idea,
    need,
    now_utc,
    text,
    user_by_email,
)

MAX_MEMBERS = 30


def _grant(conn: Conn, user_id: str, ref: str, actor: str) -> None:
    live = conn.execute(
        "SELECT 1 FROM role_grants WHERE user_id = %s AND role = 'build_team' AND scope_id = %s "
        "AND (valid_to IS NULL OR valid_to > now())",
        (user_id, ref),
    ).fetchone()
    if live is None:
        conn.execute(
            "INSERT INTO role_grants (user_id, role, scope_id, granted_by) VALUES (%s, 'build_team', %s, %s)",
            (user_id, ref, actor),
        )


def _tell(conn: Conn, row: dict[str, Any], stage: str) -> None:
    """J-ONE step 1's hand-off to the sharer's Inbox: "1% Club moved your idea to <stage>" (L-INBOX.kinds, the
    system as sender). The sharer (everyone credited, after a merge) and the crew; refs are the stage only."""
    people = sorted(set(credited_users(conn, row["id"])) | set(crew_users(conn, row["id"])))
    if people:
        post(conn, "stage_moved", people, idea_id=str(row["id"]), refs={"to": stage},
             dedupe_key=f"stage_moved:{row['id']}:{stage}")  # fmt: skip


def choose_team(conn: Conn, actor: str, ref: Any, body: dict[str, Any]) -> dict[str, Any]:
    need(conn, actor, {"admin"})
    name = text(body.get("name"), "name", min_chars=2, max_chars=80,
                message="Give the team a name of 2 to 80 characters.")  # fmt: skip
    emails = body.get("member_emails") or []
    if isinstance(emails, str):
        emails = [e for e in emails.replace(";", ",").split(",") if e.strip()]
    if not isinstance(emails, list) or len(emails) > MAX_MEMBERS:
        raise Refused(
            422, "members_not_valid", "List up to 30 work emails, separated by commas.", field="members"
        )
    with conn.transaction():
        lead = user_by_email(conn, body.get("lead_email"), "lead")
        members = sorted({user_by_email(conn, e, "members") for e in emails} | {lead})
        row = idea(conn, ref, lock=True)
        if row["status"] != "picked":
            raise Refused(409, "not_picked", "Only a picked idea gets a build team.", field="idea")
        team = conn.execute(
            "INSERT INTO build_teams (idea_uuid, name, lead_user_id, chosen_by) VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (idea_uuid) DO NOTHING RETURNING id",
            (row["id"], name, lead, actor),
        ).fetchone()
        if team is None:
            raise Refused(409, "team_chosen", "This idea already has a build team.", field="idea")
        for member in members:
            _grant(conn, member, row["idea_id"], actor)
        conn.execute("UPDATE ideas SET status = 'being_built' WHERE id = %s", (row["id"],))
        audit(conn, actor, "idea.build_team_chosen", f"idea:{row['idea_id']}",
              {"build_team_id": str(team["id"]), "lead_user_id": lead, "members": len(members),
               "status": "being_built"}, before={"status": "picked"})  # fmt: skip
        _tell(conn, row, "being_built")
    return {"idea": row["idea_id"], "status": "being_built", "build_team_id": str(team["id"]),
            "members": len(members)}  # fmt: skip


def mark_shipped(conn: Conn, actor: str, ref: Any, now: dt.datetime | None = None) -> dict[str, Any]:
    now = now or now_utc()
    need(conn, actor, {"admin"})
    with conn.transaction():
        row = idea(conn, ref, lock=True)
        if row["status"] != "being_built":
            raise Refused(409, "not_being_built", "Choose the build team first. Only an idea being built ships.",
                          field="idea")  # fmt: skip
        conn.execute("UPDATE ideas SET status = 'shipped' WHERE id = %s", (row["id"],))
        impact.schedule(conn, str(row["id"]), now)
        audit(conn, actor, "idea.shipped", f"idea:{row['idea_id']}", {"status": "shipped"},
              before={"status": "being_built"})  # fmt: skip
        _tell(conn, row, "shipped")
    return {"idea": row["idea_id"], "status": "shipped", "measurements": impact.MARKS}
