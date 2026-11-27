"""A merge the lead accepted (L-MERGE.effects/1–6 for `via = 'lead_accepted'`).

Modelled on lane B's `desk.merging.desk_merge` so the two can converge after launch: one transaction, both ideas
locked in a stable order, a `merges` row, the merged idea pointing to the lead, its open question sets closed, its
crew joining the lead's. What differs, by the pack: no committee window (that is desk merges only, L-MERGE.desk/4),
the crew always joins (L-MERGE.effects/4, "always for a lead-accepted merge"), and a draft can be the merged idea
(L-MERGE.request/5: "The draft is closed as merged").
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass, field
from typing import Any

from core.db import Conn
from teamup import adapters
from teamup.store import (
    Refused,
    actor,
    audit,
    crew_codes,
    entity_of,
    is_closed,
    lead_code,
    lock_ideas,
    seal,
    user_of,
)
from teamup.store import now as clock_now


@dataclass
class Merged:
    merge_id: str
    lead_idea_id: str
    merged_idea_id: str | None  # None for a draft, which has no reference
    joined: list[str] = field(default_factory=list)  # contributor codes added to the lead's crew


def _join_crew(
    conn: Conn,
    lead_uuid: Any,
    codes: list[str],
    *,
    via: str,
    at: dt.datetime,
    merge_id: str | None = None,
    teamup_request_id: str | None = None,
) -> list[str]:
    """Add people to an idea's crew as `crew`, never as a second lead; anyone already on it is skipped."""
    on = set(crew_codes(conn, lead_uuid))
    added: list[str] = []
    for c in dict.fromkeys(codes):
        if c in on:
            continue
        conn.execute(
            "INSERT INTO crew_members (idea_uuid, contributor_code, role, via, merge_id, teamup_request_id, "
            "joined_at) VALUES (%s, %s, 'crew', %s, %s, %s, %s)",
            (lead_uuid, c, via, merge_id, teamup_request_id, at),
        )
        added.append(c)
        on.add(c)
    return added


def announce_joins(
    conn: Conn,
    lead_idea: dict[str, Any],
    joined: list[str],
    *,
    via: str,
    at: dt.datetime,
    before: list[str],
    payload: dict[str, str | None],
) -> None:
    """A `crew.joined` line per person who joined (L-CONVO), and `crew_joined` to the crew that was already there,
    not the person who joined and not the lead who said yes (the coordinator's refs: {via})."""
    lead = lead_code(conn, lead_idea)
    existing = [user_of(conn, c) for c in before if c != lead and c not in joined]
    for c in joined:
        adapters.say(conn, str(lead_idea["id"]), "crew.joined", author_code=c, payload={"via": via, **payload},
                     at=at)  # fmt: skip
        sender = user_of(conn, c)
        adapters.tell(
            conn, "crew_joined", [u for u in existing if u], idea_uuid=str(lead_idea["id"]),
            sender=sender or "system", refs={"via": via},
        )  # fmt: skip


def join_crew(
    conn: Conn,
    lead_idea: dict[str, Any],
    codes: list[str],
    *,
    via: str,
    at: dt.datetime,
    merge_id: str | None = None,
    teamup_request_id: str | None = None,
    payload: dict[str, str | None] | None = None,
) -> list[str]:
    """Join and announce, in the caller's transaction."""
    before = crew_codes(conn, lead_idea["id"])
    added = _join_crew(conn, lead_idea["id"], codes, via=via, at=at, merge_id=merge_id,
                       teamup_request_id=teamup_request_id)  # fmt: skip
    announce_joins(conn, lead_idea, added, via=via, at=at, before=before, payload=payload or {})
    return added


def apply_lead_merge(
    conn: Conn,
    *,
    lead_uuid: Any,
    merged_uuid: Any,
    by_code: str,
    requester_code: str,
    note_masked: str,
    teamup_request_id: str | None = None,
    merge_request_id: str | None = None,
    at: dt.datetime | None = None,
) -> Merged:
    """L-MERGE.effects/1–6 for a merge the lead (`by_code`) accepted. Runs in one transaction (a savepoint when
    the caller already holds one). `requester_code` and the merged idea's live crew join the lead's crew via
    'merge'. A shared idea becomes `merged`; a draft closes as `merged` (L-MERGE.request/5).

    Refuses (409) when either idea is no longer open to merge, so no route can merge without this check."""
    t = at or clock_now()
    with conn.transaction():
        # lane C's lock on both ideas first, in uuid order, then their rows in the same order (BLD-B247, BLD-F096):
        # the merged idea's queued questions are forgotten below. Re-entrant: `requests.answer` already holds them.
        adapters.lock_hide(conn, lead_uuid, merged_uuid)
        locked = lock_ideas(conn, lead_uuid, merged_uuid)
        leader, joiner = locked.get(str(lead_uuid)), locked.get(str(merged_uuid))
        if leader is None or joiner is None or leader["id"] == joiner["id"]:
            raise Refused(404, "not_found")
        if leader["status"] == "draft" or is_closed(str(leader["status"])):
            raise Refused(409, "idea_closed", "This idea is no longer open to team up.")
        if lead_code(conn, leader) != by_code:
            raise Refused(403, "not_lead", "Only the lead of this idea can answer.")
        is_draft = joiner["status"] == "draft"
        if (is_draft and joiner["archived_at"] is not None) or is_closed(str(joiner["status"])):
            raise Refused(409, "brought_not_open", "That idea is no longer open to merge.")

        merge_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO merges (id, lead_idea_uuid, merged_idea_uuid, via, by_code, team_up, note_encrypted, "
            "prior_status, at, teamup_request_id, merge_request_id) "
            "VALUES (%s, %s, %s, 'lead_accepted', %s, true, %s, %s, %s, %s, %s)",
            (merge_id, leader["id"], joiner["id"], by_code, seal(note_masked, "merges", "note_encrypted", merge_id),
             joiner["status"], t, teamup_request_id, merge_request_id),
        )  # fmt: skip
        # L-MERGE.effects/1, /5: the merged idea points to the lead; its open question sets close, and its queued
        # ones (every reviewer's) are dropped with what lane C's hide kept for their questions (lane B's
        # `drop_queued`, BLD-B272, BLD-F096; lane C's lock on the idea is held, above)
        conn.execute(
            "UPDATE ideas SET status = 'merged', merged_into = %s WHERE id = %s", (leader["id"], joiner["id"])
        )
        adapters.drop_queued(conn, str(joiner["id"]))
        closed = conn.execute(
            "UPDATE question_sets SET state = 'closed', closed_at = %s WHERE idea_uuid = %s AND state <> 'closed' "
            "RETURNING id",
            (t, joiner["id"]),
        ).fetchall()
        # L-INBOX.rules/3 (BLD-F108): the merged idea's questions leave the sharer's Needs you with their reminders,
        # as they do when the review desk merges (lane B's `desk.merging`)
        for done in closed:
            adapters.resolve_questions(conn, str(done["id"]))
        # Requests waiting on the merged idea close with it (L-TEAMUP.states: "closed … if merged away first")
        from teamup.requests import close_requests_for

        close_requests_for(conn, joiner["id"], t)

        # L-MERGE.effects/4: the requester and the merged idea's crew join the lead's crew, never as a second lead
        joiners = [requester_code, *([] if is_draft else crew_codes(conn, joiner["id"]))]
        added = join_crew(conn, leader, joiners, via="merge", at=t, merge_id=merge_id,
                          teamup_request_id=teamup_request_id, payload={"merge_id": merge_id})  # fmt: skip

        # L-MERGE.effects/6: both conversations stay; the merged one gets a closing line with a link. A draft has
        # no conversation, so only the lead idea gets its line.
        adapters.say(conn, str(leader["id"]), "merge.from", author_code=by_code,
                     payload={"merge_id": merge_id, "idea_id": joiner["idea_id"]}, at=t)  # fmt: skip
        if not is_draft:
            adapters.say(conn, str(joiner["id"]), "merge.into", author_code=by_code,
                         payload={"merge_id": merge_id, "idea_id": leader["idea_id"]}, at=t)  # fmt: skip
        who = user_of(conn, by_code)
        audit(conn, actor(who) if who else f"code:{by_code}", "merge.lead_accepted", entity_of(joiner),
              before={"status": joiner["status"]},
              after={"merge_id": merge_id, "lead_idea_id": leader["idea_id"], "crew_added": len(added),
                     "teamup_request_id": teamup_request_id, "merge_request_id": merge_request_id})  # fmt: skip
        return Merged(merge_id, str(leader["idea_id"]), joiner["idea_id"], added)
