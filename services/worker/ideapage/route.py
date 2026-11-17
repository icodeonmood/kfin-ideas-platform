"""What `/ideas/:id` shows to whom (P-ROUTES.screens, S-06, S-09.rules/3):

- the sharer gets their page (S-06); a draft of theirs opens where they left it (S-04B, `/share/:draftId`);
- a reviewer who is not the sharer goes to the reviewer's page (S-R2, `/desk/ideas/:id`, lane B);
- anyone else gets the colleague's view (S-09).

A draft and a never-shared idea exist only for their owner: everyone else gets "not found", the same answer as
for an idea that does not exist, so nothing is confirmed (L-DRAFT.autosave/3). A withdrawn idea is the same, except
for someone who was on its crew or asked to join it: they were told, and get S-09's one line (S-09.rules/2,
L-SUBMIT.withdraw/2 and /4, BLD-E011). A merged idea shows its S-06 or S-09 state with the link to where it went.
Others reach an idea only by its reference, never by its row id.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from core.db import Conn
from ideapage import read
from ideapage.colleague import colleague_view, withdrawn_view
from ideapage.sharer import sharer_view
from ideapage.words import IST


def record_open(conn: Conn, idea: dict[str, Any], me: read.Viewer, at: dt.datetime) -> None:
    """A colleague opened the page: one row per person per day in India time, counts only (L-WALL.justin/4,
    'Opened this week'). The day is the view's own clock, so a page shown for a given moment counts on that day."""
    conn.execute(
        "INSERT INTO idea_opens (idea_uuid, user_id, day) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
        (idea["id"], me.user_id, at.astimezone(IST).date()),
    )


def idea_view(
    conn: Conn,
    key: str,
    user_id: str,
    *,
    came_from: str | None = None,
    back: str | None = None,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    """The view this person gets of `key` (a reference, or a row id for the owner's own drafts). Raises
    `read.NotFound` when it does not exist for them, `colleague.Paused` when the Wall is switched off."""
    t = now or read.now()
    idea = read.find_idea(conn, key)
    if idea is None:
        raise read.NotFound
    me = read.viewer(conn, user_id)
    if me.is_sharer(idea):
        if idea["status"] == "draft":
            return {"view": "draft", "to": f"/share/{idea['id']}"}
        return sharer_view(conn, idea, me, t, came_from=came_from, back=back)
    by_reference = key.startswith(read.IDEA_REF_PREFIX)
    if not by_reference or idea["idea_id"] is None or idea["shared_at"] is None:
        raise read.NotFound
    if idea["status"] == "draft":
        raise read.NotFound
    if idea["status"] == "withdrawn":
        if not read.was_involved(conn, str(idea["id"]), me.code):
            raise read.NotFound
        return withdrawn_view(idea, came_from=came_from, back=back)
    if me.on_desk:
        return {"view": "desk", "to": f"/desk/ideas/{idea['idea_id']}"}
    out = colleague_view(conn, idea, me, t, came_from=came_from, back=back)
    record_open(conn, idea, me, t)
    return out
