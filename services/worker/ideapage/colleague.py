"""S-09, a colleague's idea: what everyone at KFintech sees of someone else's idea once it is shared. The short
summary, where it is, and one action, Team up (lane F's sheet).

Nothing private (S-09.rules/1, DEC-104): no raw words, no answers, no files, no reason for a decision beyond the
stage. The sharer's name is left out when they hide it from the Wall (S-09.layout/2, NOT DRAWN default). The Back
link names where the person came from (P-ROUTES.state).
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from core import killswitch
from core.db import Conn
from ideapage import read
from ideapage.shape import REF, crew_of, public_idea, safe_back
from ideapage.track import decided
from ideapage.words import brings_words, count, day, join_words, pill

CLOSED_FOR_TEAM_UP = (
    "not_picked",
    "withdrawn",
    "merged",
)  # L-TEAMUP/1: "not closed, withdrawn or merged away"


class Paused(Exception):
    """The Wall is switched off (kill switch `wall.public`): nobody sees anyone else's ideas (§7.6)."""


def back_link(came_from: str | None, back: str | None) -> dict[str, str]:
    """'Back to the Wall' / 'Back to My ideas' / 'Back to IDEA-2026-001481' (S-09.layout/1). `back` may carry the
    list state to return to (the Wall's or My ideas' query); anything off-site is dropped."""
    if came_from and REF.match(came_from):
        return {"from": came_from, "label": f"Back to {came_from}", "to": f"/ideas/{came_from}"}
    if came_from == "my-ideas":
        return {
            "from": "my-ideas",
            "label": "Back to My ideas",
            "to": safe_back(back, ("/my-ideas",)) or "/my-ideas",
        }
    return {"from": "wall", "label": "Back to the Wall", "to": safe_back(back, ("/wall",)) or "/wall"}


def _team_up(
    conn: Conn, idea: dict[str, Any], me: read.Viewer, crew: dict[str, Any], lead: dict[str, Any] | None
) -> dict[str, Any]:
    """The Team up card (S-09.layout/6, S-09.states). Read only: requests and crews are lane F's (L-TEAMUP);
    `op` names the action their sheet and endpoints carry out."""
    status = str(idea["status"])
    key = read.key_of(idea)
    first = lead["first_name"] if lead else None
    who = first or "The person who shared it"
    n = int(crew["count"])
    count_line = (
        f"{count(n, 'colleague')} on it. {who} leads it and decides who joins. The crew helps the review desk with "
        "detail and, if it’s picked, helps build it."
    )
    faces = ([crew["lead"]] if crew["lead"] else []) + list(crew["members"])
    out: dict[str, Any] = {"count": n, "count_line": count_line, "faces": faces[:4]}
    if status in CLOSED_FOR_TEAM_UP:
        merged = read.live_merge_into(conn, str(idea["id"])) if status == "merged" else None
        if merged and merged.get("lead_ref"):
            out.update(
                {
                    "state": "merged",
                    "line": f"This idea is now part of {merged['lead_ref']}. Team up there.",
                    "link": {
                        "label": f"Open {merged['lead_ref']}",
                        "to": f"/ideas/{merged['lead_ref']}?from={key}",
                    },
                }
            )  # NOT DRAWN wording; S-09.rules/2
        else:
            out.update({"state": "closed", "line": "This idea isn’t going ahead, so it isn’t taking a crew."})
        out["can_team_up"] = False
        return out
    on_crew = me.code is not None and me.code in crew["_codes"]
    mine = read.my_teamup(conn, str(idea["id"]), me.code)
    if on_crew:
        out.update(
            {
                "state": "on_crew",
                "line": "You’re on the crew. You’ll get its updates.",
                "action": {"label": "Say hello", "to": f"/ideas/{key}/conversation"},
                "can_team_up": False,
            }
        )
    elif mine and mine["state"] == "sent":
        out.update(
            {
                "state": "request_sent",
                "heading": f"Waiting for {first}" if first else "Waiting for the lead",
                "line": f"{first or 'The lead'} reads your note and decides. You’ll hear in your Inbox.",
                "action": {"label": "Withdraw", "op": "teamup.withdraw", "request_id": str(mine["id"])},
                "can_team_up": False,
            }
        )
    else:
        out.update(
            {
                "state": "not_asked",
                "line": (
                    f"Send {first or 'the lead'} a note about what you bring. Raised the same thing? Bring your idea "
                    f"along, and if {first or 'the lead'} approves, it joins this one with credit to you."
                ),
                "action": {"label": "Team up", "op": "teamup.open", "sheet": "C-SHEET-TEAMUP"},
                "can_team_up": True,
            }
        )
    return out


def colleague_view(
    conn: Conn,
    idea: dict[str, Any],
    me: read.Viewer,
    now: dt.datetime,
    *,
    came_from: str | None = None,
    back: str | None = None,
) -> dict[str, Any]:
    """Everything S-09 shows. The caller has checked that the idea is shared and not withdrawn."""
    if not killswitch.is_on("wall.public", conn):
        raise Paused
    uid = str(idea["id"])
    dec = decided(read.decision(conn, uid))
    carried = read.live_merge_into(conn, uid) if idea["status"] == "not_picked" else None
    base = public_idea(
        conn,
        idea,
        now,
        for_sharer=False,
        dec=dec,
        qset=None,
        carried_into=carried["lead_ref"] if carried else None,
    )
    sharer = read.person_by_code(conn, idea["contributor_code"])
    named = sharer if read.shows_name(sharer) else None
    crew = crew_of(conn, idea, names_for_all=False)
    shared_on = day(idea["shared_at"], now) if idea["shared_at"] else None
    place = ", ".join(x for x in (idea["area"], idea["city"]) if x)
    if named:
        shared_line = (
            f"Shared {shared_on} by {named['name']}, {place}"
            if place
            else f"Shared {shared_on} by {named['name']}"
        )
        words_note = f"This is the short summary everyone at KFintech sees. {named['first_name']}’s own words stay with them and the review desk."
    else:
        shared_line = f"Shared {shared_on}, {place}" if place else f"Shared {shared_on}"
        words_note = "This is the short summary everyone at KFintech sees. The sharer’s own words stay with them and the review desk."
    n_similar = int(base["linked_similar_count"])
    return {
        "view": "colleague",
        "screen": "S-09",
        "idea": {**base, "next_step": {"sentence": pill(base["status"])["label"]}},
        "page": {
            "back": back_link(came_from, back),
            "pill": pill(base["status"]),
            "shared_line": shared_line,
            "summary_heading": "The problem",
            "summary_note": words_note,
            "about": [
                {"label": "Who it affects", "value": join_words(list(idea["affects"] or []))},
                {"label": "What it’s worth", "value": brings_words(list(idea["brings"] or []))},
                {"label": "Area", "value": idea["area"] or ""},
                {"label": "Linked", "value": count(n_similar, "similar idea") + " linked"},
                {"label": "Who can see it", "value": "Everyone at KFintech, as this short summary"},
            ],
            "team_up": _team_up(conn, idea, me, crew, named),
        },
    }
