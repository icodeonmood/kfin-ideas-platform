"""Shared reads for the idea pages: the idea, who is looking, people as PersonRef, and read-only views of the tables
other lanes write (decisions and windows: lane B; questions and answers: lane B; hidden details and files: lane C;
crew, team-up and similar ideas: lanes C and F). Nothing here writes.

Private text is stored as the masked copy, sealed with the context "<table>.<column>:<row id>" (onepc/context.py);
it is opened here only for a viewer the page's rules allow, and never logged (non-negotiable 3).
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass, field
from typing import Any

from core.config import get_settings
from core.db import Conn
from onepc.context import open_text
from rules import load_rule

IDEA_REF_PREFIX = "IDEA-"
# Roles that land on the reviewer's page (P-ROUTES.screens: "A reviewer following a link to an idea lands on S-R2").
DESK_ROLES = frozenset({"reviewer"})
# The Ones Committee (E-ENUMS.roles; the seed and the old grants still say "committee").
COMMITTEE_ROLES = frozenset({"committee", "core_committee", "core_chair"})
PARTLY_ANSWERED = "partly_answered"  # some answers sent, the rest open until the deadline
OPEN_SET_STATES = ("sent", "seen", PARTLY_ANSWERED)
ANSWERED_SET_STATES = ("answered",)


class NotFound(Exception):
    """The idea does not exist, or this person may not know that it does (the web app answers 404 either way)."""


def promises() -> dict[str, Any]:
    """P-PRODUCT.promises from the company repo's rules/promises.md (BLD-A181). Read on each call: no release."""
    return dict(load_rule(get_settings().company_repo_path, "promises").data)


def now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


# --- The idea ------------------------------------------------------------------------------------------------------


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


def find_idea(conn: Conn, key: str) -> dict[str, Any] | None:
    """An idea by its IDEA- reference, or by its row id (drafts and never-shared ideas have no reference)."""
    if key.startswith(IDEA_REF_PREFIX):
        row = conn.execute("SELECT * FROM ideas WHERE idea_id = %s", (key,)).fetchone()
    elif _is_uuid(key):
        row = conn.execute("SELECT * FROM ideas WHERE id = %s", (key,)).fetchone()
    else:
        return None
    return dict(row) if row else None


def key_of(idea: dict[str, Any]) -> str:
    """The id a route uses: the reference once shared, else the row id."""
    return str(idea["idea_id"] or idea["id"])


def status_of(idea: dict[str, Any]) -> str:
    return str(idea["status"])


# --- Who is looking ------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Viewer:
    user_id: str
    code: str | None
    roles: frozenset[str] = field(default_factory=frozenset)

    def is_sharer(self, idea: dict[str, Any]) -> bool:
        return self.code is not None and self.code == idea["contributor_code"]

    @property
    def on_desk(self) -> bool:
        return bool(self.roles & DESK_ROLES)

    @property
    def on_committee(self) -> bool:
        return bool(self.roles & COMMITTEE_ROLES)

    @property
    def sees_desk_names(self) -> bool:
        """DEC-111: only the review desk and the Ones Committee see who at the desk asked, revised or decided.
        Everyone else, the sharer and the crew included, reads "the review desk", with no name, avatar or initials
        (`onepc.words.REVIEW_DESK`). Read from the live role grants, never from the caller (BLD-E053)."""
        return self.on_desk or self.on_committee


def viewer(conn: Conn, user_id: str) -> Viewer:
    """The signed-in person, from the database: their contributor code and live role grants. The web app has
    checked the session; the roles are read again here so a page never trusts a role the caller passes."""
    if not _is_uuid(user_id):
        return Viewer(user_id=user_id, code=None)
    row = conn.execute(
        "SELECT contributor_code FROM contributor_map WHERE user_id = %s", (user_id,)
    ).fetchone()
    roles = {
        str(r["role"])
        for r in conn.execute(
            "SELECT role FROM role_grants WHERE user_id = %s AND valid_from <= now() "
            "AND (valid_to IS NULL OR valid_to > now())",
            (user_id,),
        ).fetchall()
    }
    return Viewer(user_id=user_id, code=str(row["contributor_code"]) if row else None, roles=frozenset(roles))


# --- People --------------------------------------------------------------------------------------------------------


def _initials(name: str) -> str:
    parts = [p for p in name.split() if p]
    if not parts:
        return ""
    return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()


_PERSON_SQL = (
    "SELECT u.id, u.name, u.first_name, u.area, u.location AS city, u.active, "
    "coalesce(s.show_name_on_wall, true) AS show_name, m.contributor_code "
    "FROM users u LEFT JOIN person_settings s ON s.user_id = u.id "
    "LEFT JOIN contributor_map m ON m.user_id = u.id "
)


def _person(row: dict[str, Any] | None, role_label: str | None = None) -> dict[str, Any] | None:
    if row is None:
        return None
    name = str(row["name"])
    out: dict[str, Any] = {
        "id": str(row["id"]),
        "name": name,
        "first_name": str(row["first_name"] or name.split()[0]),
        "initials": _initials(name),
        **({"area": row["area"]} if row.get("area") else {}),
        **({"city": row["city"]} if row.get("city") else {}),
        **({"role_label": role_label} if role_label else {}),
        "_show_name": bool(row["show_name"]),
        "_active": bool(row["active"]),
    }
    return out


def person_by_code(conn: Conn, code: str | None, role_label: str | None = None) -> dict[str, Any] | None:
    if not code:
        return None
    row = conn.execute(_PERSON_SQL + "WHERE m.contributor_code = %s", (code,)).fetchone()
    return _person(dict(row) if row else None, role_label)


def person_by_user(conn: Conn, user_id: Any, role_label: str | None = None) -> dict[str, Any] | None:
    if user_id is None:
        return None
    row = conn.execute(_PERSON_SQL + "WHERE u.id = %s", (str(user_id),)).fetchone()
    return _person(dict(row) if row else None, role_label)


def public_person(p: dict[str, Any] | None) -> dict[str, Any] | None:
    """A PersonRef as the API sends it: the private `_show_name` and `_active` flags removed."""
    if p is None:
        return None
    return {k: v for k, v in p.items() if not k.startswith("_")}


def shows_name(p: dict[str, Any] | None) -> bool:
    """Whether this person may be named to someone outside their crew, the review desk and the Ones Committee:
    they show their name on the Wall (Profile's switch, no row means shown) and they are still here
    (`users.active`). A person who hid their name, or has left, is "the lead", "A colleague" or left out
    (DEC-104, P-PRODUCT.privacy; the same rule as lane C's `similar.preview.person_refs` and lane F's team-up,
    BLD-C090, BLD-F029; BLD-E048)."""
    return bool(p and p.get("_show_name") and p.get("_active"))


# --- Lane B's tables, read only: the decision, its window and reversal; questions and answers ----------------------


def decision(conn: Conn, idea_uuid: str, *, with_text: bool = False) -> dict[str, Any] | None:
    """The latest decision on an idea with its committee window and any reversal (L-DECIDE, L-COMMITTEE), for the
    track's dates and the list's rows. The decision itself, its reason and the window are lane B's to show on the
    idea page (`GET /ideas/:id/decision`); the reason and the committee's note are opened only with `with_text`,
    which only My ideas asks for (S-07.rows: "the reason in one line", the sharer's own idea)."""
    r = conn.execute(
        "SELECT d.*, w.id AS window_id, w.state AS window_state, w.opens_at, w.closes_at, w.max_closes_at, "
        "w.extended_times, v.id AS reversal_id, v.to_choice, v.note_encrypted, v.by_user_id AS reversed_by, "
        "v.at AS reversed_at, v.return_at AS reversed_return_at, v.team_by AS reversed_team_by "
        "FROM idea_decisions d LEFT JOIN decision_windows w ON w.decision_id = d.id "
        "LEFT JOIN decision_reversals v ON v.window_id = w.id "
        "WHERE d.idea_uuid = %s ORDER BY d.at DESC LIMIT 1",
        (idea_uuid,),
    ).fetchone()
    if r is None:
        return None
    d = dict(r)
    reason = d.pop("reason_encrypted")
    note = d.pop("note_encrypted")
    d["reason"] = open_text("idea_decisions", "reason_encrypted", str(d["id"]), reason) if with_text else None
    d["note"] = (
        open_text("decision_reversals", "note_encrypted", str(d["reversal_id"]), note)
        if with_text and note
        else None
    )
    return d


def decision_reason(conn: Conn, decision_id: str) -> str | None:
    """The desk's reason for one decision, as lane B stored it: already masked (`adapters.hide` in desk/decide.py), so
    the same words S-06's reason block reads from lane B's `/decision`. Only the sharer's own page opens it, for the
    desk's message in "You and the review desk" (S-06.layout/8, BLD-E058). Never logged."""
    row = conn.execute("SELECT reason_encrypted FROM idea_decisions WHERE id = %s", (decision_id,)).fetchone()
    if row is None:
        return None
    return open_text("idea_decisions", "reason_encrypted", decision_id, row["reason_encrypted"])


def reversal_note(conn: Conn, reversal_id: str) -> str | None:
    """The Ones Committee's note to the sharer when it reversed a decision, as lane B stored it: masked when the
    committee sent it (`adapters.hide` in desk/committee.py), so the same words as the reversal card's note from lane
    B's `/decision`. Only the sharer's own page opens it, for the committee's message in "You and the review desk"
    (S-06.layout/8, BLD-E058). Never logged."""
    row = conn.execute(
        "SELECT note_encrypted FROM decision_reversals WHERE id = %s", (reversal_id,)
    ).fetchone()
    if row is None:
        return None
    return open_text("decision_reversals", "note_encrypted", reversal_id, row["note_encrypted"])


def question_set(conn: Conn, idea_uuid: str) -> dict[str, Any] | None:
    """The latest set the desk sent (never a queued one, which only the reviewer sees): its state, who asked, when,
    how many questions and which have a sent answer. Counts and dates only: the questions card and the answers are
    lane B's (`GET /ideas/:id/question-set`, C-QCARD). Reading it does not mark it seen (that is S-R3's read)."""
    row = conn.execute(
        "SELECT * FROM question_sets WHERE idea_uuid = %s AND state <> 'queued' "
        "ORDER BY sent_at DESC NULLS LAST, created_at DESC LIMIT 1",
        (idea_uuid,),
    ).fetchone()
    if row is None:
        return None
    s = dict(row)
    s["questions"] = [
        {
            "id": str(q["id"]),
            "n": int(q["seq"]),
            "part": str(q["part"]),
            "answered": q["answered_at"] is not None,
        }
        for q in conn.execute(
            "SELECT q.id, q.seq, q.part, a.sent_at AS answered_at FROM questions q "
            "LEFT JOIN answers a ON a.question_id = q.id WHERE q.set_id = %s ORDER BY q.seq",
            (s["id"],),
        ).fetchall()
    ]
    return s


def has_open_questions(qset: dict[str, Any] | None) -> bool:
    return bool(qset and qset["state"] in OPEN_SET_STATES)


# --- Lane F's tables, read only: the crew and team-up requests ------------------------------------------------------


def crew(conn: Conn, idea_uuid: str) -> list[dict[str, Any]]:
    """Active crew members, lead first, then in the order they joined."""
    return [
        dict(r)
        for r in conn.execute(
            "SELECT contributor_code, role, joined_at FROM crew_members WHERE idea_uuid = %s AND left_at IS NULL "
            "ORDER BY (role = 'lead') DESC, joined_at",
            (idea_uuid,),
        ).fetchall()
    ]


def my_teamup(conn: Conn, idea_uuid: str, code: str | None) -> dict[str, Any] | None:
    """This person's latest team-up request on the idea, if any."""
    if not code:
        return None
    row = conn.execute(
        "SELECT id, state, sent_at FROM teamup_requests WHERE idea_uuid = %s AND from_code = %s "
        "ORDER BY sent_at DESC LIMIT 1",
        (idea_uuid, code),
    ).fetchone()
    return dict(row) if row else None


def was_involved(conn: Conn, idea_uuid: str, code: str | None) -> bool:
    """Whether this person was ever on the idea's crew or asked to join it: the people a withdrawal is told to
    (L-SUBMIT.withdraw/4), who may still follow an old link to it (BLD-E011)."""
    if not code:
        return False
    row = conn.execute(
        "SELECT EXISTS (SELECT 1 FROM crew_members WHERE idea_uuid = %s AND contributor_code = %s) "
        "OR EXISTS (SELECT 1 FROM teamup_requests WHERE idea_uuid = %s AND from_code = %s) AS yes",
        (idea_uuid, code, idea_uuid, code),
    ).fetchone()
    return bool(row and row["yes"])


def live_merge_into(conn: Conn, idea_uuid: str) -> dict[str, Any] | None:
    """The merge that took this idea into another (not reversed), with the surviving idea's reference."""
    row = conn.execute(
        "SELECT m.*, i.idea_id AS lead_ref, i.title AS lead_title, i.contributor_code AS lead_code "
        "FROM merges m JOIN ideas i ON i.id = m.lead_idea_uuid "
        "WHERE m.merged_idea_uuid = %s AND m.reversed_at IS NULL ORDER BY m.at DESC LIMIT 1",
        (idea_uuid,),
    ).fetchone()
    if row is None:
        return None
    m = dict(row)
    note = m.pop("note_encrypted", None)
    m["note"] = open_text("merges", "note_encrypted", str(m["id"]), note) if note else None
    return m


# --- Lane C's tables, read only: hidden details, files, similar ideas ------------------------------------------------


def hidden(conn: Conn, idea_uuid: str) -> list[dict[str, Any]]:
    """Hidden details as their masked form only ("Folio ••••89"); the value stays in the vault (DEC-103)."""
    return [
        dict(r)
        for r in conn.execute(
            "SELECT h.id, h.kind, h.masked, h.state, h.reason, h.shown_at, h.source, a.name AS file_name "
            "FROM hidden_details h LEFT JOIN attachments a ON h.source = 'file' AND a.id = h.source_id "
            "WHERE h.idea_uuid = %s ORDER BY h.created_at",
            (idea_uuid,),
        ).fetchall()
    ]


def files(conn: Conn, idea_uuid: str) -> list[dict[str, Any]]:
    """The idea's own files and links (not those on an answer or a conversation message), top level only."""
    return [
        dict(r)
        for r in conn.execute(
            "SELECT id, kind, name, mime, bytes, pages, item_count, file_state, state, link_scope, hidden_note, "
            "uploaded_by_code, created_at FROM attachments WHERE idea_uuid = %s AND parent_id IS NULL "
            "AND answer_id IS NULL AND purpose = 'idea' AND conversation_entry_id IS NULL ORDER BY created_at",
            (idea_uuid,),
        ).fetchall()
    ]


def similar(conn: Conn, idea_uuid: str) -> list[dict[str, Any]]:
    """Similar ideas linked to this one that others may see (shared, not withdrawn or merged away)."""
    return [
        dict(r)
        for r in conn.execute(
            "SELECT s.strength, s.reason, s.rank, o.id, o.idea_id, o.title, o.summary, o.status, o.area, o.city, "
            "o.shared_at, o.contributor_code FROM similar_links s JOIN ideas o ON o.id = s.other_idea_uuid "
            "WHERE s.idea_uuid = %s AND o.idea_id IS NOT NULL AND o.status NOT IN ('draft', 'withdrawn', 'merged') "
            "ORDER BY (s.strength = 'close') DESC, s.rank, o.shared_at DESC",
            (idea_uuid,),
        ).fetchall()
    ]


def similar_count(conn: Conn, idea_uuid: str) -> int:
    row = conn.execute(
        "SELECT count(*) AS n FROM similar_links s JOIN ideas o ON o.id = s.other_idea_uuid "
        "WHERE s.idea_uuid = %s AND o.idea_id IS NOT NULL AND o.status NOT IN ('draft', 'withdrawn')",
        (idea_uuid,),
    ).fetchone()
    return int(row["n"]) if row else 0


def worth(conn: Conn, idea_uuid: str) -> dict[str, Any]:
    """The sharer's figures and the latest reviewer revision, kept side by side (L-WORTH/3)."""
    out: dict[str, Any] = {}
    for side in ("sharer", "reviewer"):
        row = conn.execute(
            "SELECT * FROM idea_worth WHERE idea_uuid = %s AND by_side = %s ORDER BY at DESC LIMIT 1",
            (idea_uuid, side),
        ).fetchone()
        if row is not None:
            w = dict(row)
            note = w.pop("note_encrypted", None)
            w["note"] = open_text("idea_worth", "note_encrypted", str(w["id"]), note) if note else None
            out[side] = w
    return out


def fix(conn: Conn, idea_uuid: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM idea_fix WHERE idea_uuid = %s AND included", (idea_uuid,)).fetchone()
    return dict(row) if row else None


def status_at(conn: Conn, idea_uuid: str, status: str) -> dt.datetime | None:
    """When the idea last moved to `status` (idea_status_history, kept by the cut-over's trigger)."""
    row = conn.execute(
        "SELECT max(at) AS at FROM idea_status_history WHERE idea_uuid = %s AND to_status = %s",
        (idea_uuid, status),
    ).fetchone()
    return row["at"] if row and row["at"] else None


def build_team(conn: Conn, idea_uuid: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT name, chosen_at FROM build_teams WHERE idea_uuid = %s", (idea_uuid,)
    ).fetchone()
    return dict(row) if row else None


def entry_count(conn: Conn, idea_uuid: str) -> int:
    row = conn.execute(
        "SELECT count(*) AS n FROM conversation_entries WHERE idea_uuid = %s AND type <> 'event' "
        "AND deleted_at IS NULL",
        (idea_uuid,),
    ).fetchone()
    return int(row["n"]) if row else 0


# The merge lines lane F's S-08 shows on both ideas (`convo.render.event_line`, L-MERGE.effects/6): lane B's desk
# merge, lane F's lead-accepted merge (into, on the merged idea; from, on the lead), the Ones Committee undoing a
# merge, and the seed's own code for a desk merge (BLD-F061).
MERGE_EVENTS = ("desk.merged", "merge.into", "merge.from", "committee.merge_reversed", "desk_merged")


def merge_line_count(conn: Conn, idea_uuid: str) -> int:
    """How many merge lines this idea's conversation shows (BLD-E065): `entry_count` leaves events out."""
    row = conn.execute(
        "SELECT count(*) AS n FROM conversation_entries WHERE idea_uuid = %s AND type = 'event' "
        "AND event = ANY(%s) AND deleted_at IS NULL",
        (idea_uuid, list(MERGE_EVENTS)),
    ).fetchone()
    return int(row["n"]) if row else 0
