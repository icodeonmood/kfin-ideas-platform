"""Event lines, rendered when the conversation is read (L-CONVO/3): a code and IDs in, the words of
`1pc-handoff/reference/copy/Messages.md` out, with names resolved now and "You" for the reader.

Lines Messages.md draws are used as drawn. Every other line is ours, in the same style, and listed for HR in
`docs/hr-wording/lane-f.md`. No gendered pronoun for a person (BLD-E008). An unknown code renders nothing and is
logged by its code alone, so a lane that posts a new code before lane F renders it breaks no screen.

Codes and payloads (IDs, enums and numbers only):

| Code | Posted by | Author | Payload |
|---|---|---|---|
| `desk.opened`, `desk.worth_revised`, `desk.decide_by_moved` | lane B | reviewer (user) | `worth_id` |
| `desk.decided` | lane B | reviewer | `decision_id`, `choice` |
| `desk.back_from_not_now` | lane B | none | |
| `desk.merged` | lane B, on both ideas | reviewer | `merge_id` |
| `committee.reversed` | lane B | committee member | `window_id`, `to` |
| `committee.merge_reversed` | lane B, on both ideas | committee member | `merge_id` |
| `desk.asked` (type questions), `sharer.answered` (type answers) | lane B | | `set_id`, `count` |
| `teamup.approved_merged`, `teamup.approved_team_only` | F1 | the lead (code) | `request_id` |
| `crew.joined`, `crew.left` | F1 | the member (code) | |
| `crew.removed` | F1 | the lead (code) | `member_code` |
| `merge.into` (on the merged idea), `merge.from` (on the lead idea) | F1 | the lead (code) | `idea_id` (the other idea), `merge_id` |
| `build.team_chosen` | whoever chooses the build team (no lane at launch) | the chooser (user) | |

"You shared it" and "Checked and matched" are not posted: they are read from the idea itself (BLD-F051).

Lane E's synthetic seed (`bootstrap/club_seed.py`, BLD-E006) writes its lines under codes of its own, with an ID in
the payload and no author: `opened_by_desk` {reviewer_id}, `decided` {decision_id}, `decision_reversed`
{reversal_id}, `desk_merged` {merge_id}, `crew_joined` {request_id}, `team_chosen`. Each reads as the code it stands
for, with its author (and choice) taken from the row the ID names; `shared`, `checked_matched` and `shipped` read as
nothing, since the first two come from the idea and the board draws no line for the third (BLD-F061).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any

from convo.access import Reader
from convo.store import People, Person
from core.db import Conn
from core.logging import get_logger

log = get_logger("convo")

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
DESK = "from the review desk"
COMMITTEE = "from the Ones Committee"
_DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
           "November", "December")  # fmt: skip
CHOICE_DONE = {"pick": "picked it", "not_now": "chose Not now", "not_picked": "didn’t pick it"}
CHOICE_NAME = {"pick": "Picked", "not_now": "Not now", "not_picked": "Not picked"}
HIDDEN_WORD = {
    "folio": ("folio number", "folio numbers"),
    "pan": ("PAN", "PANs"),
    "phone": ("phone number", "phone numbers"),
    "email": ("email address", "email addresses"),
    "account": ("account number", "account numbers"),
    "aadhaar": ("Aadhaar number", "Aadhaar numbers"),
    "name": ("name", "names"),
}


# ---------------------------------------------------------------------------------------------------------------
# Dates as the timeline says them (A-API.conventions/6: worked out on the server so every screen agrees)
# ---------------------------------------------------------------------------------------------------------------
def clock(t: dt.datetime) -> str:
    """'10:05 am', '6:40 pm', '12:00 pm'."""
    local = t.astimezone(IST)
    h = local.hour % 12 or 12
    return f"{h}:{local.minute:02d} {'am' if local.hour < 12 else 'pm'}"


def day(t: dt.datetime, today: dt.date) -> str:
    """'Saturday 14 November', with the year only when it is not this year."""
    local = t.astimezone(IST)
    out = f"{_DAYS[local.weekday()]} {local.day} {_MONTHS[local.month - 1]}"
    return out if local.year == today.year else f"{out} {local.year}"


def when(t: dt.datetime, now: dt.datetime, *, time_only: bool = False) -> str:
    """'Today, 10:05 am'; 'Monday 16 November, 9:50 am' within the last 6 days; 'Monday 2 November' before that
    (Messages.md draws both); just '10:06 am' for a line on the same day as the one above it (BLD-F053)."""
    today = now.astimezone(IST).date()
    local = t.astimezone(IST)
    if local.date() == today:
        return clock(t) if time_only else f"Today, {clock(t)}"
    if time_only:
        return clock(t)
    if (today - local.date()).days > 6:
        return day(t, today)
    return f"{day(t, today)}, {clock(t)}"


def same_day(a: dt.datetime | None, b: dt.datetime) -> bool:
    return a is not None and a.astimezone(IST).date() == b.astimezone(IST).date()


def plural(n: int, one: str, many: str | None = None) -> str:
    return f"{n} {one if n == 1 else (many or one + 's')}"


# ---------------------------------------------------------------------------------------------------------------
# Lines
# ---------------------------------------------------------------------------------------------------------------
@dataclass
class Ctx:
    conn: Conn
    people: People
    reader: Reader
    idea: dict[str, Any]

    def is_me(self, p: Person) -> bool:
        return p.id is not None and p.id == self.reader.user_id

    def name(self, p: Person) -> str:
        return "You" if self.is_me(p) else p.label

    def obj(self, p: Person) -> str:
        """The person as the object of a sentence: 'you' for the reader."""
        return "you" if self.is_me(p) else p.label

    def owner(self, p: Person) -> str:
        """'your' for the reader, 'Kavya Menon’s' for anyone else."""
        return "your" if self.is_me(p) else f"{p.label}’s"

    def idea_ref(self, ref: Any) -> str | None:
        """The IDEA- reference of an idea given by reference or uuid."""
        row = _idea_by(self.conn, ref)
        return str(row["idea_id"]) if row and row["idea_id"] else None


def _idea_by(conn: Conn, ref: Any) -> dict[str, Any] | None:
    if not ref:
        return None
    row = conn.execute(
        "SELECT idea_id, contributor_code FROM ideas WHERE idea_id = %s OR id::text = %s",
        (str(ref), str(ref)),
    ).fetchone()
    return dict(row) if row else None


Line = tuple[str, dict[str, str] | None]  # the sentence, and a link {label, to} when the line carries one


def author(ctx: Ctx, row: dict[str, Any]) -> Person:
    """Who did it, with their role when they acted as staff: desk codes speak for the review desk, committee codes
    for the Ones Committee."""
    if row.get("author_user_id"):
        p = ctx.people.by_user(str(row["author_user_id"]))
        code = str(row.get("event") or "")
        if code.startswith("desk."):
            return p.as_staff(DESK)
        if code.startswith("committee."):
            return p.as_staff(COMMITTEE)
        return p
    return ctx.people.by_code(row.get("author_code"))


def _merge(ctx: Ctx, merge_id: Any) -> dict[str, Any] | None:
    if not merge_id:
        return None
    row = ctx.conn.execute(
        "SELECT m.lead_idea_uuid, m.merged_idea_uuid, l.idea_id AS lead_ref, d.idea_id AS merged_ref "
        "FROM merges m JOIN ideas l ON l.id = m.lead_idea_uuid JOIN ideas d ON d.id = m.merged_idea_uuid "
        "WHERE m.id::text = %s",
        (str(merge_id),),
    ).fetchone()
    return dict(row) if row else None


def _carries_on(ref: str) -> Line:
    return f"It’s now part of {ref}. The conversation carries on there.", {
        "label": ref,
        "to": f"/ideas/{ref}/conversation",
    }


SEED_SILENT = frozenset({"shared", "checked_matched", "shipped"})
SEED_CODES = frozenset(
    {"opened_by_desk", "decided", "decision_reversed", "desk_merged", "crew_joined", "team_chosen"}
)


def _seeded(ctx: Ctx, row: dict[str, Any]) -> dict[str, Any]:
    """A line of lane E's seed as the posted code it stands for, its author and choice read from the row its ID
    names (BLD-F061)."""
    code, p = str(row.get("event") or ""), dict(row.get("payload") or {})

    def named(sql: str, key: str) -> dict[str, Any]:
        found = ctx.conn.execute(sql, (str(p[key]),)).fetchone() if p.get(key) else None
        return dict(found) if found else {}

    out = dict(row)
    if code == "opened_by_desk":
        out.update(event="desk.opened", author_user_id=p.get("reviewer_id"))
    elif code == "decided":
        d = named("SELECT choice, by_user_id FROM idea_decisions WHERE id::text = %s", "decision_id")
        out.update(
            event="desk.decided", author_user_id=d.get("by_user_id"), payload={**p, "choice": d.get("choice")}
        )
    elif code == "decision_reversed":
        r = named("SELECT to_choice, by_user_id FROM decision_reversals WHERE id::text = %s", "reversal_id")
        out.update(
            event="committee.reversed",
            author_user_id=r.get("by_user_id"),
            payload={**p, "to": r.get("to_choice")},
        )
    elif code == "desk_merged":
        m = named("SELECT by_user_id FROM merges WHERE id::text = %s", "merge_id")
        out.update(event="desk.merged", author_user_id=m.get("by_user_id"))
    elif code == "crew_joined":
        q = named("SELECT from_code FROM teamup_requests WHERE id::text = %s", "request_id")
        out.update(event="crew.joined", author_code=q.get("from_code"))
    elif code == "team_chosen":
        out.update(event="build.team_chosen")
    return out


def event_line(ctx: Ctx, row: dict[str, Any]) -> Line | None:
    """The sentence for one event entry, or None for a code lane F does not know (logged by code only)."""
    code = str(row.get("event") or "")
    if code in SEED_SILENT:
        return None
    if code in SEED_CODES:
        row = _seeded(ctx, row)
        code = str(row["event"])
    p = dict(row.get("payload") or {})
    who = author(ctx, row)
    me = ctx.name(who)

    if code == "desk.opened":
        return f"{me} opened it.", None  # "Meera from the review desk opened it."
    if code == "desk.decided":
        done = CHOICE_DONE.get(str(p.get("choice")))
        return (f"{me} {done}.", None) if done else (f"{me} decided.", None)
    if code == "desk.worth_revised":
        return f"{me} revised what it’s worth.", None
    if code == "desk.decide_by_moved":
        return f"{me} moved the date to decide.", None
    if code == "desk.back_from_not_now":
        return "It’s back with the review desk.", None
    if code == "desk.merged":
        m = _merge(ctx, p.get("merge_id"))
        if m is None:
            return f"{me} joined it with another idea.", None
        if str(m["merged_idea_uuid"]) == str(
            ctx.idea["id"]
        ):  # L-MERGE.effects/6: the closing line, with a link
            ref = str(m["lead_ref"])
            return f"{me} joined it with {ref}. The conversation carries on there.", _carries_on(ref)[1]
        return f"{me} joined it with {m['merged_ref']}.", None
    if code == "committee.reversed":
        to = CHOICE_NAME.get(str(p.get("to")))
        return (
            (f"{me} reversed the decision. It’s now {to}.", None)
            if to
            else (f"{me} reversed the decision.", None)
        )
    if code == "committee.merge_reversed":
        return f"{me} undid the merge. Each idea is on its own again.", None
    if code in ("teamup.approved_merged", "teamup.approved_team_only"):
        requester = _requester(ctx, p.get("request_id"))
        if requester is None:
            return f"{me} approved a team-up request.", None
        if ctx.is_me(requester):
            return f"{me} approved your team-up request.", None  # "Ravi Nair approved your team-up request."
        return f"{me} approved {requester.label}’s team-up request.", None
    if code == "crew.joined":
        return f"{me} joined the crew.", None
    if code == "crew.left":
        return f"{me} left the crew.", None
    if code == "crew.removed":
        member = ctx.people.by_code(str(p.get("member_code") or "") or None)
        return f"{me} took {ctx.obj(member)} off the crew.", None
    if code == "merge.into":
        into = ctx.idea_ref(p.get("idea_id") or p.get("lead_idea_id"))
        return _carries_on(into) if into else ("It’s now part of another idea.", None)
    if code == "merge.from":
        came_from = p.get("idea_id") or p.get("merged_idea_id")
        if not came_from and p.get("merge_id"):  # a draft merged in has no reference (J-SIMILAR/6a)
            m = _merge(ctx, p.get("merge_id"))
            came_from = str(m["merged_idea_uuid"]) if m else None
        came, sharer = ctx.idea_ref(came_from), _sharer_of(ctx, came_from)
        if sharer is None:
            return "Another idea is now part of it.", None
        if came is None:  # "Kavya Menon’s idea is now part of it, with credit to them." (BLD-E008)
            if ctx.is_me(sharer):
                return "Your idea is now part of it, with credit to you.", None
            return f"{sharer.label}’s idea is now part of it, with credit to them.", None
        return f"{came} is now part of it, with credit to {ctx.obj(sharer)}.", None
    if code == "build.team_chosen":  # "Arjun Rao’s team started building it." (Messages.md)
        team = ctx.conn.execute(
            "SELECT lead_user_id FROM build_teams WHERE idea_uuid = %s", (ctx.idea["id"],)
        ).fetchone()
        if team is None or not team["lead_user_id"]:
            return "The build team started building it.", None
        whose = ctx.owner(ctx.people.by_user(str(team["lead_user_id"])))
        return f"{whose[:1].upper()}{whose[1:]} team started building it.", None
    log.info("convo.render.unknown_code", code=code, entry_id=str(row.get("id")))
    return None


def _requester(ctx: Ctx, request_id: Any) -> Person | None:
    """Who asked: a team-up request, or a draft's merge request (F1 answers both by one id, BLD-F010)."""
    if not request_id:
        return None
    row = ctx.conn.execute(
        "SELECT from_code FROM teamup_requests WHERE id::text = %s UNION ALL "
        "SELECT from_code FROM merge_requests WHERE id::text = %s LIMIT 1",
        (str(request_id), str(request_id)),
    ).fetchone()
    return ctx.people.by_code(str(row["from_code"])) if row else None


def _sharer_of(ctx: Ctx, ref: Any) -> Person | None:
    row = _idea_by(ctx.conn, ref)
    return ctx.people.by_code(str(row["contributor_code"])) if row else None


def shared_line(ctx: Ctx) -> str:
    """'You shared it.' / 'Ravi Nair shared it.' (Messages.md)."""
    return f"{ctx.name(ctx.people.by_code(ctx.idea['contributor_code']))} shared it."


def checked(ctx: Ctx) -> tuple[str, dt.datetime] | None:
    """'Checked and matched. 1 folio number hidden, 2 similar ideas found.' (Messages.md), when the idea left the
    check: the details hidden in what was shared (not in later messages) and the similar ideas found."""
    row = ctx.conn.execute(
        "SELECT min(at) AS at FROM idea_status_history WHERE idea_uuid = %s AND from_status = 'checking'",
        (ctx.idea["id"],),
    ).fetchone()
    if row is None or row["at"] is None:
        return None
    kinds = ctx.conn.execute(
        "SELECT kind, count(*) AS n FROM hidden_details WHERE idea_uuid = %s AND source IN ('message', 'file') "
        "AND state = 'hidden' GROUP BY kind ORDER BY count(*) DESC, kind",
        (ctx.idea["id"],),
    ).fetchall()
    similar = ctx.conn.execute(
        "SELECT count(*) AS n FROM similar_links WHERE idea_uuid = %s", (ctx.idea["id"],)
    ).fetchone()
    parts = [plural(int(k["n"]), *HIDDEN_WORD.get(str(k["kind"]), ("detail", "details"))) for k in kinds]
    hidden = (
        (", ".join(parts[:-1]) + " and " + parts[-1] if len(parts) > 1 else parts[0]) + " hidden"
        if parts
        else ""
    )
    n = int(similar["n"]) if similar else 0
    found = f"{plural(n, 'similar idea')} found" if n else "no similar ideas found"
    if not hidden:
        return f"Checked and matched. Nothing to hide, {found}.", row["at"]
    return f"Checked and matched. {hidden}, {found}.", row["at"]
