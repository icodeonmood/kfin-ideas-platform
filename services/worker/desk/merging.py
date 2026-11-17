"""The review desk merges two ideas, and the committee undoes it (L-MERGE.desk, L-MERGE.effects, L-MERGE.states).

The rules that need no database (which idea leads, when a merge is allowed, the note, the sheet's words) are in
`desk.merge`. This module writes a desk merge and its effects in one transaction, and undoes them when the Ones
Committee reverses the merge inside its window (L-COMMITTEE, same window rules as a decision).
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from core.db import Conn
from desk import adapters, merge, promises
from desk.merge import Lead, Side
from desk.store import (
    Refused,
    actor,
    audit,
    audited,
    load_idea,
    own_codes,
    person_by_code,
    person_by_user,
    refuse_own,
    seal,
    user_of,
)
from desk.store import now as clock_now
from desk.window import open_window

LEADS: tuple[Lead, ...] = ("this", "other")
BUTTON = "Merge and tell both"
# 409s from merge.refusal, with words ready to show (A-API.conventions/2).
_REFUSALS: dict[str, str] = {
    "same_idea": "Choose a different idea to merge with.",
    "already_decided": "This idea already has a decision.",
    "other_not_open": "That idea is no longer open to merge.",
}


def _crew_codes(conn: Conn, idea_uuid: Any) -> list[str]:
    """The live crew, lead first, then in the order they joined."""
    return [
        str(r["contributor_code"])
        for r in conn.execute(
            "SELECT contributor_code FROM crew_members WHERE idea_uuid = %s AND left_at IS NULL "
            "ORDER BY role = 'lead' DESC, joined_at, id",
            (idea_uuid,),
        ).fetchall()
    ]


def _side(conn: Conn, idea: dict[str, Any]) -> Side:
    return Side(
        idea_id=str(idea["idea_id"]),
        status=str(idea["status"]),
        shared_at=idea["shared_at"] or idea["created_at"],
        sharer_first_name=person_by_code(conn, idea["contributor_code"]).first_name,
        crew_count=len(_crew_codes(conn, idea["id"])),
    )


def sheet_for(
    conn: Conn, ref: str, other_ref: str, user_id: str, now: dt.datetime | None = None
) -> dict[str, Any]:
    """C-SHEET-MERGE.anatomy for the reviewer's page: the words, the default lead (L-MERGE.desk/2), and the line
    and team-up words for either choice, so the sheet follows the choice without asking again."""
    t = now or clock_now()
    p = promises.get()
    with audited(conn):
        this, other = load_idea(conn, ref), load_idea(conn, other_ref)
        refuse_own(conn, user_id, this, "merge")
        refuse_own(conn, user_id, other, "merge")
    this_side, other_side = _side(conn, this), _side(conn, other)
    lead = merge.default_lead(this_side, other_side)
    words = {k: merge.sheet(this_side, other_side, k, t) for k in LEADS}
    shown = words[lead]
    return {
        "idea_id": this_side.idea_id, "other_idea_id": other_side.idea_id,
        "title": shown.title, "line": shown.line, "default_lead": lead,
        "options": [
            {"lead": "this", "label": shown.this_option[0], "meta": shown.this_option[1], "selected": lead == "this"},
            {"lead": "other", "label": shown.other_option[0], "meta": shown.other_option[1], "selected": lead == "other"},
        ],
        "by_lead": {k: {"line": w.line, "team_up": w.team_up} for k, w in words.items()},
        "refusal": {k: merge.refusal(this_side, other_side, k) for k in LEADS},
        "team_up": {"label": "Team them up", "line": shown.team_up, "default": True},
        "note": {"label": "Note to both sharers", "prefill": shown.note_prefill, "min": p.merge_note_min,
                 "max": p.merge_note_max},
        "small_print": shown.small_print, "button": BUTTON,
    }  # fmt: skip


def _window_json(w: Any, state: str = "open") -> dict[str, Any]:
    return {"state": state, "opens_at": w.opens_at.isoformat(), "closes_at": w.closes_at.isoformat(),
            "max_closes_at": w.max_closes_at.isoformat(), "extended_times": w.extended_times}  # fmt: skip


def desk_merge(
    conn: Conn, ref: str, user_id: str, body: dict[str, Any], at: dt.datetime | None = None
) -> dict[str, Any]:
    """L-MERGE.desk: the reviewer merges the idea under review with a similar one. No consent is needed; both
    sharers are told at once with the note, and the committee's window opens (L-MERGE.desk/3–4). Returns the
    Merge (E-ENTITIES.crew) and the banner (C-SHEET-MERGE.after).
    Errors: own_idea (403), same_idea / already_decided / other_not_open (409), lead_invalid and
    note_too_short / note_too_long (422)."""
    t = at or clock_now()
    p = promises.get()
    note = str(body.get("note") or "")
    team_up = body.get("team_up", True) is not False
    with audited(conn), conn.transaction():
        first, second = load_idea(conn, ref), load_idea(conn, str(body.get("other_idea_id") or ""))
        # both locked in one stable order, so two reviewers merging the same pair cannot deadlock
        locked = {
            str(i["id"]): load_idea(conn, str(i["id"]), lock=True)
            for i in sorted((first, second), key=lambda i: str(i["id"]))
        }
        this, other = locked[str(first["id"])], locked[str(second["id"])]
        refuse_own(conn, user_id, this, "merge")
        refuse_own(conn, user_id, other, "merge")
        this_side, other_side = _side(conn, this), _side(conn, other)
        lead = body.get("lead") or merge.default_lead(this_side, other_side)
        if lead not in LEADS:
            raise Refused(422, "lead_invalid", "Choose which idea leads.", "lead")
        code = merge.refusal(this_side, other_side, lead)
        if code:
            raise Refused(409, code, _REFUSALS.get(code))
        errors = merge.check_note(note, p)
        if errors:
            e = errors[0]
            raise Refused(422, e.code, e.message, e.field)
        leader, joiner = (this, other) if lead == "this" else (other, this)
        credited = own_codes(conn, leader) | own_codes(conn, joiner)
        masked, _ = adapters.hide(conn, str(leader["id"]), note.strip())
        merge_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO merges (id, lead_idea_uuid, merged_idea_uuid, via, by_user_id, team_up, note_encrypted, "
            "prior_status, at) VALUES (%s, %s, %s, 'review_desk', %s, %s, %s, %s, %s)",
            (merge_id, leader["id"], joiner["id"], user_id, team_up,
             seal(masked, "merges", "note_encrypted", merge_id), joiner["status"], t),
        )  # fmt: skip
        # L-MERGE.effects/1, /5: the joining idea points to the lead; its open sets close, queued ones are dropped
        conn.execute(
            "UPDATE ideas SET status = 'merged', merged_into = %s WHERE id = %s", (leader["id"], joiner["id"])
        )
        conn.execute("DELETE FROM question_sets WHERE idea_uuid = %s AND state = 'queued'", (joiner["id"],))
        closed = conn.execute(
            "UPDATE question_sets SET state = 'closed', closed_at = %s WHERE idea_uuid = %s AND state <> 'closed' "
            "RETURNING id",
            (t, joiner["id"]),
        ).fetchall()
        # L-INBOX.rules/3: the joining idea's questions leave Needs you with their reminders
        for done in closed:
            adapters.resolve(conn, adapters.questions_key(str(done["id"])))
        # L-MERGE.effects/4: the joining sharer and their live crew join the lead's crew, never as a second lead
        added: list[str] = []
        if team_up:
            on_lead = set(_crew_codes(conn, leader["id"]))
            for c in dict.fromkeys([str(joiner["contributor_code"]), *_crew_codes(conn, joiner["id"])]):
                if c in on_lead:
                    continue
                conn.execute(
                    "INSERT INTO crew_members (idea_uuid, contributor_code, role, via, merge_id, joined_at) "
                    "VALUES (%s, %s, 'crew', 'desk_merge', %s, %s)",
                    (leader["id"], c, merge_id, t),
                )
                added.append(c)
        w = open_window(t, p)
        conn.execute(
            "INSERT INTO decision_windows (merge_id, opens_at, closes_at, max_closes_at) VALUES (%s, %s, %s, %s)",
            (merge_id, w.opens_at, w.closes_at, w.max_closes_at),
        )
        for idea in (leader, joiner):  # L-MERGE.effects/6: both conversations stay, each gets a line
            adapters.say(conn, str(idea["id"]), "desk.merged", author_user_id=user_id,
                         payload={"merge_id": merge_id}, at=t)  # fmt: skip
        adapters.tell(
            conn, "desk_merge", sorted({u for c in credited if (u := user_of(conn, c))}),
            idea_uuid=str(leader["id"]), sender=user_id,
            actions=[("Open the idea", f"/ideas/{leader['idea_id']}", "primary")], refs={"merge_id": merge_id},
        )  # fmt: skip
        adapters.schedule(conn, "committee.window_close", f"merge:{merge_id}", w.closes_at)
        audit(conn, actor(user_id), "desk.merge", f"idea:{joiner['idea_id']}",
              before={"status": joiner["status"]},
              after={"merge_id": merge_id, "lead_idea_id": leader["idea_id"], "team_up": team_up,
                     "crew_added": len(added)})  # fmt: skip
        return {
            "id": merge_id, "lead_idea_id": leader["idea_id"], "merged_idea_id": joiner["idea_id"],
            "by": person_by_user(conn, user_id).as_json(), "via": "review_desk", "team_up": team_up,
            "note": masked, "at": t.isoformat(), "window": _window_json(w),
            "banner": merge.banner(this_side, other_side, lead, team_up),
        }  # fmt: skip


def reverse_merge(conn: Conn, merge_id: str, user_id: str, note_masked: str, at: dt.datetime) -> None:
    """L-MERGE.effects/7: the committee reverses a desk merge. Called inside the committee's transaction, after it
    has checked the window and written the reversal (which holds the note, sealed); the committee also audits.

    The merged idea goes back to its status before the merge with its own crew; crew joins the merge made are
    undone; both sharers and the reviewer who merged are told (L-INBOX.kinds: Decision reversed)."""
    _ = note_masked  # the reversal row holds it; the Inbox item carries IDs only
    m = conn.execute("SELECT * FROM merges WHERE id = %s FOR UPDATE", (merge_id,)).fetchone()
    if m is None or m["reversed_at"] is not None:
        raise Refused(409, "already_reversed")
    conn.execute(
        "UPDATE ideas SET status = %s, merged_into = NULL WHERE id = %s",
        # its question sets were closed by the merge, so a joiner that was waiting on its sharer comes back to the
        # desk rather than to a "Needs you" with nothing to answer
        (
            "with_review_desk" if m["prior_status"] in (None, "needs_you") else m["prior_status"],
            m["merged_idea_uuid"],
        ),
    )
    conn.execute(
        "UPDATE crew_members SET left_at = %s, left_how = 'merge_reversed' WHERE merge_id = %s AND left_at IS NULL",
        (at, merge_id),
    )
    conn.execute("UPDATE merges SET reversed_at = %s WHERE id = %s", (at, merge_id))
    ideas = conn.execute(
        "SELECT id, idea_id, contributor_code FROM ideas WHERE id IN (%s, %s) ORDER BY id = %s DESC",
        (m["lead_idea_uuid"], m["merged_idea_uuid"], m["merged_idea_uuid"]),
    ).fetchall()
    for idea in ideas:
        adapters.say(conn, str(idea["id"]), "committee.merge_reversed", author_user_id=user_id,
                     payload={"merge_id": merge_id}, at=at)  # fmt: skip
    recipients = {u for i in ideas if (u := user_of(conn, i["contributor_code"]))}
    if m["by_user_id"]:
        recipients.add(str(m["by_user_id"]))
    adapters.tell(
        conn, "decision_reversed", sorted(recipients), idea_uuid=str(m["merged_idea_uuid"]), sender=user_id,
        actions=[("Read the note", f"/ideas/{ideas[0]['idea_id']}", "primary")], refs={"merge_id": merge_id},
    )  # fmt: skip
