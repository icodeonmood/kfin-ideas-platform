"""Shared shapes for the idea pages: the public part of E-ENTITIES `Idea` (what anyone at KFintech may see once an
idea is shared: P-PRODUCT.privacy), the crew, similar-idea tiles, and where the Back link goes (P-ROUTES.state).
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

from core.db import Conn
from ideapage import read
from ideapage.track import Decided, stages
from ideapage.words import STAGE_LABEL, count, nodes_json, pill
from teamup.store import crew_role, is_closed

MY_IDEAS_FILTER_LABEL = {
    "needs_you": "Needs you",
    "drafts": "Drafts",
    "with_review_desk": "With the review desk",
    "picked_and_building": "Picked and building",
    "shipped": "Shipped",
    "closed": "Closed",
}
REF = re.compile(r"^IDEA-[0-9]{4}-[0-9]{6}$")
ON_THE_CREW = "On the crew"  # C-SIMGRID.tile, after approval; S-05 says the same (share/[id]/check/copy.ts)


def display_status(idea: dict[str, Any], qset: dict[str, Any] | None, *, for_sharer: bool) -> str:
    """`needs_you` is the sharer's view of `with_review_desk` while a question set is open (E-ENUMS.idea-status).
    Lane B stores it on the idea when it sends questions (and puts `with_review_desk` back once all are answered);
    an older row may still say `with_review_desk` with a set open, so both read the same. Everyone else sees
    'With the review desk'."""
    status = str(idea["status"])
    if status == "needs_you":
        return "needs_you" if for_sharer else "with_review_desk"
    if for_sharer and status == "with_review_desk" and read.has_open_questions(qset):
        return "needs_you"
    return status


def at_desk(idea: dict[str, Any]) -> bool:
    """Shared and waiting on the review desk, with or without questions open (E-ENUMS.idea-machine)."""
    return str(idea["status"]) in ("checking", "with_review_desk", "needs_you")


def crew_of(conn: Conn, idea: dict[str, Any], *, names_for_all: bool) -> dict[str, Any]:
    """Idea.crew: the lead, the members, how many, how many are Ones. Everyone else does not see the name of a
    person who hides it from the Wall (DEC-104); the sharer sees their whole crew (`names_for_all`)."""
    rows = read.crew(conn, str(idea["id"]))
    lead = None
    members: list[dict[str, Any]] = []
    codes: list[str] = []
    for r in rows:
        p = read.person_by_code(conn, r["contributor_code"])
        codes.append(str(r["contributor_code"]))
        if p is None or not (names_for_all or read.shows_name(p)):
            continue
        if r["role"] == "lead":
            lead = read.public_person(p)
        else:
            members.append(read.public_person(p) or {})
    ones = conn.execute(
        "SELECT count(*) AS n FROM ones o JOIN contributor_map m ON m.user_id = o.user_id "
        "WHERE m.contributor_code = ANY(%s) AND o.status = 'active'",
        (codes,),
    ).fetchone()
    return {
        "lead": lead,
        "members": members,
        "count": len(rows),
        "ones_count": int(ones["n"]) if ones else 0,
        "_codes": codes,
    }


def opened_7d(conn: Conn, idea_uuid: str) -> int:
    row = conn.execute(
        "SELECT count(DISTINCT user_id) AS n FROM idea_opens WHERE idea_uuid = %s "
        "AND day > (now() AT TIME ZONE 'Asia/Kolkata')::date - 7",
        (idea_uuid,),
    ).fetchone()
    return int(row["n"]) if row else 0


def public_idea(
    conn: Conn,
    idea: dict[str, Any],
    now: dt.datetime,
    *,
    for_sharer: bool,
    dec: Decided | None,
    qset: dict[str, Any] | None,
    carried_into: str | None = None,
    reviewer_first: str | None = None,
    sees_reversal: bool | None = None,
) -> dict[str, Any]:
    """E-ENTITIES `Idea`, the fields anyone may see once it is shared: the short summary, never the person's own
    words (non-negotiable 7). The sharer is null to others when they hide their name from the Wall."""
    uid = str(idea["id"])
    sharer = read.person_by_code(conn, idea["contributor_code"])
    crew = crew_of(conn, idea, names_for_all=for_sharer)
    merge = read.live_merge_into(conn, uid) if idea["status"] == "merged" else None
    credited = [
        read.public_person(p)
        for p in (
            read.person_by_code(conn, str(r["contributor_code"]))
            for r in conn.execute(
                "SELECT i.contributor_code FROM merges m JOIN ideas i ON i.id = m.merged_idea_uuid "
                "WHERE m.lead_idea_uuid = %s AND m.reversed_at IS NULL",
                (uid,),
            ).fetchall()
        )
        if p is not None and (for_sharer or read.shows_name(p))
    ]
    nodes = stages(
        conn,
        idea,
        now,
        for_sharer=for_sharer,
        dec=dec,
        qset=qset,
        carried_into=carried_into,
        reviewer_first=reviewer_first,
        sees_reversal=sees_reversal,
    )
    return {
        "id": read.key_of(idea),
        "ref": idea["idea_id"],
        "status": display_status(idea, qset, for_sharer=for_sharer),
        "kind": idea["kind"],
        "title": idea["title"] or "",
        "summary": idea["summary"] or "",
        **({"often": idea["often"]} if idea.get("often") else {}),
        "affects": list(idea["affects"] or []),
        "brings": list(idea["brings"] or []),
        "area": idea["area"] or "",
        "city": idea["city"] or "",
        "sharer": read.public_person(sharer) if sharer and (for_sharer or read.shows_name(sharer)) else None,
        "credited": [c for c in credited if c],
        "shared_at": idea["shared_at"].isoformat() if idea["shared_at"] else None,
        **(
            {"share_seconds": idea["share_seconds"]}
            if for_sharer and idea.get("share_seconds") is not None
            else {}
        ),
        "stages": nodes_json(nodes) if nodes else [],
        "crew": {k: v for k, v in crew.items() if not k.startswith("_")},
        "linked_similar_count": read.similar_count(conn, uid),
        "wall": {
            "shown": idea["status"] not in ("draft", "withdrawn", "merged"),
            "opened_7d": opened_7d(conn, uid),
        },
        **({"merged_into": merge["lead_ref"]} if merge and merge.get("lead_ref") else {}),
    }


def similar_tiles(
    conn: Conn, idea: dict[str, Any], viewer: read.Viewer, *, skip: set[str] | None = None
) -> list[dict[str, Any]]:
    """S-06's 'Colleagues on something similar' (C-SIMGRID): each match as its title, area and city, stage, the
    match line and the crew's faces, with Preview and Team up. Summary only, never raw words (non-negotiable 7).
    On an idea whose crew the viewer is already in, the action row is C-SIMGRID.tile's "On the crew" in place of
    Team up (`done_line`), so nobody is offered a crew they are on (J-SIMILAR/7, J-REVIEW/M3; BLD-E056). Team up shows
    only where lane F would take the ask (`_team_up_refusal`; J-SHARE/12, BLD-E063)."""
    out = []
    for s in read.similar(conn, str(idea["id"])):
        if skip and str(s["id"]) in skip:
            continue
        crew = crew_of(conn, s, names_for_all=False)
        mine = read.my_teamup(conn, str(s["id"]), viewer.code)
        on_crew = viewer.code is not None and viewer.code in crew["_codes"]
        state = "on_crew" if on_crew else "request_sent" if mine and mine["state"] == "sent" else "none"
        lead = read.person_by_code(conn, s["contributor_code"])
        actions = [{"label": "Preview", "op": "preview", "accessible_name": f"Preview {s['title']}"}]
        if _team_up_refusal(conn, s, viewer.code) is None:
            actions.append(
                {"label": "Team up", "op": "team_up", "accessible_name": f"Team up on {s['title']}"}
            )
        out.append(
            {
                "idea": {
                    "id": s["idea_id"],
                    "title": s["title"] or "",
                    "status": s["status"],
                    "area": s["area"] or "",
                    "city": s["city"] or "",
                    "shared_at": s["shared_at"].isoformat() if s["shared_at"] else None,
                    "lead": read.public_person(lead) if lead and read.shows_name(lead) else None,
                    "crew_faces": ([crew["lead"]] if crew["lead"] else []) + crew["members"][:2],
                    "crew_count": crew["count"],
                    "in_their_words": s["summary"] or "",
                },
                "strength": s["strength"],
                "reason": s["reason"],
                "meta": ", ".join(x for x in (s["idea_id"], s["area"], s["city"]) if x),
                "pill": pill(s["status"]),
                "count_line": count(crew["count"], "colleague") + " on it",
                "my_state": state,
                "to": f"/ideas/{s['idea_id']}?from={read.key_of(idea)}",
                "actions": actions,
                **({"done_line": ON_THE_CREW} if on_crew else {}),
            }
        )
    return out


def _team_up_refusal(conn: Conn, idea: dict[str, Any], code: str | None) -> str | None:
    """L-TEAMUP.rules/1: why `POST /ideas/:id/team-up` would refuse this person's ask on `idea`, else None. The checks
    `teamup.requests.send` makes, in its order, from lane F's own pieces: `idea_closed` (`teamup.store.is_closed`:
    not now, not picked, withdrawn or merged away), then `already_on_crew`. A request of theirs already waiting is
    rules/4, not this: the tile keeps Team up, and lane F's sheet opens on "Waiting for …" with Withdraw
    (V-ACC.teamup/4). Same signature and return as lane C's `teamup.store.team_up_refusal` (c/walk-b-1).
    TODO(BLD-E063): swap for the team-up eligibility helper when lane C's walk-b lands (a one-line import)."""
    if is_closed(str(idea["status"])):
        return "idea_closed"
    if code is not None and crew_role(conn, idea["id"], code) is not None:
        return "already_on_crew"
    return None


def safe_back(back: str | None, allowed: tuple[str, ...]) -> str | None:
    """A Back target the page may link to: a path on this site under one of `allowed`, with its query (list
    state) kept. Anything else is dropped, so the parameter can never send someone off the site."""
    if not back or len(back) > 600:
        return None
    parts = urlsplit(back)
    if parts.scheme or parts.netloc or not parts.path.startswith("/") or parts.path.startswith("//"):
        return None
    if not any(parts.path == a or parts.path.startswith(a + "/") for a in allowed):
        return None
    query = urlencode([(k, v) for k, vs in parse_qs(parts.query).items() for v in vs])
    return parts.path + (f"?{query}" if query else "")


def my_ideas_label(back: str | None) -> str:
    """'My ideas', or 'My ideas, Needs you' when the list was filtered (S-06.layout/1)."""
    if not back:
        return "My ideas"
    f = parse_qs(urlsplit(back).query).get("filter", [""])[0]
    label = MY_IDEAS_FILTER_LABEL.get(f)
    return f"My ideas, {label}" if label else "My ideas"


def stage_label(stage: str) -> str:
    return STAGE_LABEL[stage]
