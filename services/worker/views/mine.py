"""My ideas (AT-B7-02): each of the person's ideas with its stage in plain words and the next step, with a date
wherever one is set (a draft's expiry, the review desk's due date, the answer's due date); the ideas they joined,
as everyone else sees them; and whether their name may appear on the wall."""

from __future__ import annotations

import datetime as dt
from typing import Any

from psycopg.types.json import Jsonb

from core.db import Conn
from pii import vault
from pii.restore import restore
from views.common import PUBLIC_WORDS, checked_summary, first_area, is_public, taxonomy_names

# (stage in plain words, next step). The owner sees their own idea's stage more precisely than everyone else.
# Drafts for HR to sign off with the other screen wording (BLD-094).
OWNER_WORDS: dict[str, tuple[str, str]] = {
    "draft": ("Draft, not shared yet", "Finish it and share it. We keep drafts until"),
    "scanning": ("Being checked", "Open it to see the result and choose what happens next"),
    "blocked": ("Needs a change", "Open it to take out the details we flagged, then share it again"),
    "redirected": ("Sent to the right team", "That team picks it up from here"),
    "scanned": ("With the review desk", "The review desk decides by"),
    "merged": ("Teamed up with colleagues", "The review desk looks at the idea you joined"),
    "adoption_requested": ("Asked to use a solution", "The team that runs it gets back to you"),
    "needs_info": ("The review desk has a question", "Please answer by"),
    "withdrawn": ("Set aside", "Answer the question any time to reopen it"),
    "reviewed": ("Reviewed", "It is grouped with similar ideas, then assessed in the next round"),
    "in_cluster": ("Grouped with similar ideas", "Assessed in the next round"),
    "ready_for_scoring": ("Being assessed", "The committee scores it in the next round"),
    "scored": ("Being assessed", "The committee shortlists ideas after scoring"),
    "already_solved": ("In the Garage", "A team already runs a solution for this; you can ask to use it"),
    "already_planned": ("Planned by a team", "We will tell you when it ships"),
    "parked": ("Parked for now", "It can come back when things change; you can disagree with this"),
    "declined": ("Not taken forward this time", "You can disagree with this"),
    "shortlisted": ("Shortlisted", "You are invited to present to the core committee"),
    "presenting": ("Being presented", "The core committee decides after your presentation"),
    "picked": ("Picked for the Garage", "A working group starts on it"),
    "appealed": ("Being looked at again", "The appeal panel decides"),
    "handover": ("In the Garage", "The Garage takes it on"),
    "in_garage": ("In the Garage", "The working group builds it"),
    "in_fix_track": ("Being fixed", "The owning team makes the fix"),
    "shipped": ("Shipped", "We measure what changed"),
    "resolved": ("Fixed", "We measure what changed"),
    "measuring": ("Shipped", "We measure what changed"),
    "closed": ("Closed", "Nothing more to do. Thank you"),
}

BEFORE_DECISION = ("scanning", "scanned", "merged", "adoption_requested", "needs_info")
LINK_WORDS = {"joiner": "You joined", "plus_one": "You added +1", "adoption": "You asked to use it"}


def viewer_codes(conn: Conn, user_id: str) -> list[str]:
    return [
        r["contributor_code"]
        for r in conn.execute(
            "SELECT contributor_code FROM contributor_map WHERE user_id = %s", (user_id,)
        ).fetchall()
    ]


def _timer(conn: Conn, idea: dict[str, Any]) -> dict[str, Any] | None:
    """The open timer behind the next step: running, or breached (overdue) but not yet stopped."""
    if idea["stage"] == "needs_info":
        return conn.execute(
            "SELECT due_at, state FROM sla_timers WHERE entity_type = 'idea' AND entity_id = %s "
            "AND stage = 'needs_info' AND state IN ('running', 'breached') ORDER BY id DESC LIMIT 1",
            (idea["idea_id"],),
        ).fetchone()
    if idea["stage"] == "scanned":
        return conn.execute(
            "SELECT t.due_at, t.state FROM sla_timers t JOIN review_items r ON t.entity_type = 'review_item' "
            "AND t.entity_id = r.id::text WHERE r.ref_id = %s AND r.item_type = 'idea' AND t.stage = 'review' "
            "AND t.state IN ('running', 'breached') ORDER BY t.id DESC LIMIT 1",
            (idea["idea_id"],),
        ).fetchone()
    return None


def owner_status(conn: Conn, idea: dict[str, Any]) -> dict[str, Any]:
    stage, step = OWNER_WORDS.get(idea["stage"], ("With the review desk", "We will let you know"))
    due: dt.datetime | None = idea.get("draft_expires_at") if idea["stage"] == "draft" else None
    timer = _timer(conn, idea)
    if timer is not None and timer["state"] == "breached" and idea["stage"] == "scanned":
        step, due = "The review is taking longer than planned. The review desk has been reminded", None
    elif timer is not None:
        due = timer["due_at"]
    elif step.endswith(" by"):
        step = step.removesuffix(" by")  # no date to finish the sentence with
    return {
        "stage": stage,
        "next_step": step,
        "due": due.isoformat() if due else None,
        "stage_key": idea["stage"],
    }


def my_ideas(conn: Conn, user_id: str) -> dict[str, Any]:
    codes = viewer_codes(conn, user_id)
    areas, _ = taxonomy_names()
    rows = conn.execute(
        "SELECT id, idea_id, stage, canvas, area_ids, created_at, submitted_at, draft_expires_at FROM ideas "
        "WHERE contributor_code = ANY(%s) AND (stage <> 'draft' OR draft_expires_at > now()) "
        "ORDER BY coalesce(submitted_at, created_at) DESC",
        (codes,),
    ).fetchall()
    ideas = []
    for r in rows:
        canvas = r["canvas"] or {}
        one_line = None
        if r["idea_id"] and canvas.get("one_line"):
            one_line = restore(
                canvas["one_line"], vault.mapping(conn, r["idea_id"]), "real"
            )  # their own words
        ideas.append(
            {
                "id": str(r["id"]),
                "idea_id": r["idea_id"],
                "one_line": one_line,
                "area": first_area(r["area_ids"], areas),
                "shared_on": (r["submitted_at"] or r["created_at"]).isoformat(),
                "draft": r["stage"] == "draft",
            }
            | owner_status(conn, dict(r))
        )
    joined = []
    for link in conn.execute(
        "SELECT DISTINCT ON (l.idea_id) l.idea_id, l.link_type, i.stage, i.visibility, i.canvas, i.area_ids "
        "FROM idea_links l JOIN ideas i ON i.idea_id = l.idea_id WHERE l.contributor_code = ANY(%s) "
        "AND l.link_type IN ('joiner', 'plus_one') AND NOT (i.contributor_code = ANY(%s)) "
        "ORDER BY l.idea_id, l.created_at DESC",
        (codes, codes),
    ).fetchall():
        # As everyone else sees it (BLD-094): the summary only once the desk has accepted it and it is open to
        # everyone; before that "with the review desk"; after a decision that took it out, just "closed".
        public = is_public(dict(link))
        joined.append(
            {
                "how": LINK_WORDS.get(link["link_type"], "You joined"),
                "summary": checked_summary(conn, (link["canvas"] or {}).get("neutral_summary"))
                if public
                else None,
                "with_desk": not public and link["stage"] in BEFORE_DECISION,
                "area": first_area(link["area_ids"], areas) if public else None,
                "stage": PUBLIC_WORDS[link["stage"]]
                if public
                else "With the review desk"
                if link["stage"] in BEFORE_DECISION
                else "Closed",
                "idea_id": link["idea_id"] if public else None,
            }
        )
    pref = conn.execute(
        "SELECT public_name_consent FROM comms_prefs WHERE user_id = %s", (user_id,)
    ).fetchone()
    return {"ideas": ideas, "joined": joined, "name_on_wall": bool(pref and pref["public_name_consent"])}


def set_name_on_wall(conn: Conn, user_id: str, on: bool) -> dict[str, Any]:
    conn.execute(
        "INSERT INTO comms_prefs (user_id, public_name_consent) VALUES (%s, %s) "
        "ON CONFLICT (user_id) DO UPDATE SET public_name_consent = EXCLUDED.public_name_consent",
        (user_id, on),
    )
    conn.execute(
        "INSERT INTO audit_log (actor, action, entity, after) VALUES (%s, 'prefs.name_on_wall', %s, %s)",
        (f"user:{user_id}", f"user:{user_id}", Jsonb({"on": on})),
    )
    return {"name_on_wall": on}
