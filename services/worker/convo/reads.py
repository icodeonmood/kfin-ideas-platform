"""`GET /ideas/:id/conversation` → E-ENTITIES `Conversation`, shaped for the reader (L-CONVO/2–5, /8, /10).

The timeline is the idea's entries in time order: event lines rendered now from their codes (`convo.render`),
people's messages opened for readers allowed to see them (the masked copy, L-CONVO/7), question sets and answers by
reference to the set (L-CONVO/4; lane B's `C-QCARD` fills the card from `GET /ideas/:id/question-set`). The words
the screen shows around it (the line under the header, the box's placeholder, who can see it, the line above the
box while questions are open) are worked out here, so every screen agrees (A-API.conventions/6).

The person at the review desk is named only to the review desk and the Ones Committee (DEC-111). Everyone else (the
sharer, the crew, the build team, a mentioned person) reads "The review desk" in their place, with no id and no
initials, on messages, the questions and answers, "In this conversation", the box's placeholder and the line above it,
and the people a message mentions (`Ctx.shown`, BLD-F082).

The header's status is the one S-06 shows the reader (lane E's `ideapage.shape.display_status`): "Needs you" for the
sharer while a question set is open, "With the review desk" for everyone else (J-TRACK/3, BLD-F085). A line that
names Teams names it only while the `comms.teams` switch is on (DEC-105; `teams_on`, BLD-F086).

Live updates: nothing is sent on an event stream yet (`A-API.events` has no owner); S-08 refetches after each
action (BLD-F050).
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from typing import Any

from convo import render
from convo.access import COMMITTEE_ROLES, DESK_ROLES, Reader, reader
from convo.render import COMMITTEE, DESK, Ctx, plural, when
from convo.store import People, Person, load_idea, now, unseal
from core import killswitch
from core.db import Conn
from desk.when import deadline as answer_by
from ideapage import read as page_read
from ideapage.shape import display_status
from onepc.enums import labels
from onepc.words import REVIEW_DESK

REMOVE_WITHIN = dt.timedelta(minutes=5)  # L-CONVO/10 (NOT DRAWN default)
OPEN_SET_STATES = ("sent", "seen", "partly_answered")
CLEAN_FILE_STATES = ("checked", "hidden_checked")
REMOVED = "Message removed"
TEAMS_SWITCH = "comms.teams"  # DEC-105: Teams is built and off until IT approves it
EMPTY_TITLE = "No messages yet"
# Messages.md "No messages yet"; without its Teams clause while Teams is off (BLD-F086, for HR's sign-off)
EMPTY_BODY = "If the review desk has a question, it shows here and in your Inbox, and we tell you on Teams."
EMPTY_BODY_NO_TEAMS = "If the review desk has a question, it shows here and in your Inbox."


def teams_on(conn: Conn) -> bool:
    """Whether Teams messages go out (DEC-105), read as `notify.post` reads it: an unknown switch counts as off."""
    return killswitch.is_on(TEAMS_SWITCH, conn)


def empty_state(teams: bool) -> dict[str, str]:
    """S-08 "No messages yet" for the sharer: Teams is named only while it is on (BLD-F086)."""
    return {"title": EMPTY_TITLE, "body": EMPTY_BODY if teams else EMPTY_BODY_NO_TEAMS}


def conversation(conn: Conn, ref: str, user_id: str, *, at: dt.datetime | None = None) -> dict[str, Any]:
    idea = load_idea(conn, ref)
    r = reader(conn, idea, user_id)
    t = at or now()
    ctx = Ctx(conn, People(conn), r, idea)
    crew = _crew(conn, idea)
    team = conn.execute("SELECT * FROM build_teams WHERE idea_uuid = %s", (idea["id"],)).fetchone()
    has_crew = any(c["role"] == "crew" for c in crew)
    audience = "build_team" if team else ("crew_and_desk" if has_crew else "you_and_desk")

    rows = [
        dict(x)
        for x in conn.execute(
            "SELECT * FROM conversation_entries WHERE idea_uuid = %s ORDER BY at, id", (idea["id"],)
        ).fetchall()
    ]
    # Mentioned only: the messages that mention them (not removed), and their own replies (BLD-F052).
    if not r.full:
        rows = [
            x
            for x in rows
            if x["type"] == "message"
            and ((user_id in _mentions(x) and x["deleted_at"] is None) or _mine(x, r))
        ]
    files = _files(conn, ctx, [str(x["id"]) for x in rows if x["type"] == "message" and not x["deleted_at"]])

    timeline: list[tuple[dt.datetime, int, dict[str, Any]]] = []
    if r.full and idea.get("shared_at"):
        timeline.append((idea["shared_at"], 0, {"type": "event", "id": f"shared:{idea['idea_id']}",
                                                 "code": "idea.shared", "sentence": render.shared_line(ctx)}))  # fmt: skip
        done = render.checked(ctx)
        if done:
            timeline.append((done[1], 0, {"type": "event", "id": f"checked:{idea['idea_id']}",
                                          "code": "idea.checked", "sentence": done[0]}))  # fmt: skip
    staff_as = _Speaking(conn, idea)
    for x in rows:
        entry = _entry(ctx, x, files, staff_as, t)
        if entry is not None:
            timeline.append((x["at"], 1, entry))
    timeline.sort(key=lambda e: (e[0], e[1]))

    entries, previous = [], None
    for at_, _, e in timeline:
        if e["type"] == "event":
            e["text"] = f"{e.pop('sentence')} {when(at_, t, time_only=render.same_day(previous, at_))}"
        else:
            e["at_label"] = when(at_, t)
        e["at"] = at_
        entries.append(e)
        previous = at_

    sharer = ctx.people.by_code(idea["contributor_code"])
    teams = teams_on(conn)
    out: dict[str, Any] = {
        "idea": _idea_ref(idea, _shown_status(conn, idea, r)),
        "header": _header(ctx, sharer, team, t),
        "audience": audience,
        "participants": _participants(ctx, idea, crew, team, rows, staff_as, sharer, t),
        "entries": entries,
        "composer": _composer(ctx, idea, audience, has_crew, sharer, rows, staff_as),
        # S-08's side note names Teams only while it is on; the screen reads a missing value as off (BLD-F086)
        "teams_on": teams,
    }
    if r.sharer and not any(e["type"] in ("message", "questions", "answers") for e in entries):
        out["empty"] = empty_state(teams)
    return out


# ---------------------------------------------------------------------------------------------------------------
# Entries
# ---------------------------------------------------------------------------------------------------------------
def _mentions(x: dict[str, Any]) -> list[str]:
    return [str(u) for u in (x.get("mentions") or [])]


def _mine(x: dict[str, Any], r: Reader) -> bool:
    if x.get("author_user_id"):
        return str(x["author_user_id"]) == r.user_id
    return r.code is not None and x.get("author_code") == r.code


class _Speaking:
    """How a staff author is named on a message: "from the review desk" or "from the Ones Committee", unless they
    are on the idea themselves (its build team, or the sharer or crew writing by user id)."""

    def __init__(self, conn: Conn, idea: dict[str, Any]) -> None:
        self.conn, self.idea, self.cache = conn, idea, {}  # type: ignore[var-annotated]

    def role(self, user_id: str) -> str | None:
        if user_id not in self.cache:
            from convo.access import is_build_member

            roles = {
                str(g["role"])
                for g in self.conn.execute(
                    "SELECT role FROM role_grants WHERE user_id = %s AND valid_from <= now() "
                    "AND (valid_to IS NULL OR valid_to > now())",
                    (user_id,),
                ).fetchall()
            }
            label = None
            if not is_build_member(self.conn, self.idea, user_id):
                label = (
                    DESK if roles & set(DESK_ROLES) else COMMITTEE if roles & set(COMMITTEE_ROLES) else None
                )
            self.cache[user_id] = label
        return self.cache[user_id]  # type: ignore[no-any-return]


def speaks_as_desk(conn: Conn, idea: dict[str, Any], r: Reader) -> bool:
    """Whether a message this person writes is spoken as the review desk, as `_sender` reads it (DEC-111): written by
    users.id (the sharer and the crew write by their code) by someone `_Speaking` places at the review desk (the
    reviewer role, and not on the idea's build team)."""
    return not (r.sharer or r.crew) and _Speaking(conn, idea).role(r.user_id) == DESK


def _sender(ctx: Ctx, x: dict[str, Any], staff_as: _Speaking) -> Person:
    """Who wrote it, as this reader may see them: the review desk's people as the desk itself outside the desk and
    the committee (DEC-111)."""
    if x.get("author_user_id"):
        p = ctx.people.by_user(str(x["author_user_id"]))
        role = staff_as.role(str(x["author_user_id"]))
        return ctx.shown(p.as_staff(role)) if role else p
    return ctx.people.by_code(x.get("author_code"))


def _at_desk(ctx: Ctx, staff_as: _Speaking, user_id: str) -> bool:
    """Whether a person named by users.id (a mention) is at the review desk, asked only when this reader may not see
    the desk's names (DEC-111)."""
    return not ctx.sees_desk and staff_as.role(user_id) == DESK


# DEC-111: a mention of someone at the review desk, as anyone outside the desk and the committee reads it. Lower case,
# so "@the review desk" sits inside a sentence and the screen still marks it as a mention.
DESK_MENTION = {"id": "", "name": REVIEW_DESK, "first_name": REVIEW_DESK, "initials": ""}


def _mentioned(
    ctx: Ctx, x: dict[str, Any], staff_as: _Speaking, text: str
) -> tuple[str, list[dict[str, Any]]]:
    """The people a message mentions, and its words, as this reader may see them: "@Meera Iyer" reads "@the review
    desk" outside the desk and the committee (DEC-111). The words the person wrote are not changed otherwise."""
    refs: list[dict[str, Any]] = []
    desk_named: list[str] = []
    for u in _mentions(x):
        p = ctx.people.by_user(u)
        if _at_desk(ctx, staff_as, u) and not ctx.is_me(p):
            desk_named.append(p.name)
            if DESK_MENTION not in refs:
                refs.append(DESK_MENTION)
        else:
            refs.append(p.ref())
    for name in sorted(set(desk_named), key=len, reverse=True):
        text = text.replace(f"@{name}", f"@{REVIEW_DESK}")
    return text, refs


def _entry(
    ctx: Ctx, x: dict[str, Any], files: dict[str, list[dict[str, Any]]], staff_as: _Speaking, t: dt.datetime
) -> dict[str, Any] | None:
    eid = str(x["id"])
    if x["type"] == "event":
        line = render.event_line(ctx, x)
        if line is None:
            return None
        e: dict[str, Any] = {"type": "event", "id": eid, "code": x["event"], "sentence": line[0]}
        if line[1]:
            e["link"] = line[1]
        return e
    if x["type"] == "message":
        who = _sender(ctx, x, staff_as)
        mine = _mine(x, ctx.reader)
        removed = x["deleted_at"] is not None
        text, mentions = (
            (REMOVED, []) if removed else _mentioned(ctx, x, staff_as, unseal(x["text_encrypted"], eid) or "")
        )
        own = [] if removed else files.get(eid, [])
        if who.desk:  # the desk's files are added by the desk, not by a named person (DEC-111)
            own = [{**f, "added_by": who.ref()} for f in own]
        e = {
            "type": "message", "id": eid, "from": who.ref(), "from_label": ctx.name(who), "you": mine,
            "text": text, "files": own, "mentions": mentions,
            "mentions_you": not removed and ctx.reader.user_id in _mentions(x),
            "removed": removed,
        }  # fmt: skip
        until = x["at"] + REMOVE_WITHIN
        if mine and not removed and t < until:
            e["can_remove_until"] = until
        return e
    if x["type"] == "questions":
        return _questions(ctx, x, t)
    if x["type"] == "answers":
        return _answers(ctx, x, staff_as, t)
    return None


def _set(ctx: Ctx, set_id: str) -> dict[str, Any] | None:
    row = ctx.conn.execute(
        "SELECT s.id, s.state, s.by_user_id, s.due_at, s.sent_at, "
        "(SELECT count(*) FROM questions q WHERE q.set_id = s.id) AS count, "
        "(SELECT count(*) FROM questions q JOIN answers a ON a.question_id = q.id "
        " WHERE q.set_id = s.id AND a.sent_at IS NOT NULL) AS answered "
        "FROM question_sets s WHERE s.id = %s",
        (set_id,),
    ).fetchone()
    return dict(row) if row else None


def _questions(ctx: Ctx, x: dict[str, Any], t: dt.datetime) -> dict[str, Any] | None:
    """By reference (L-CONVO/4): the card itself is lane B's `C-QCARD`, filled from `GET /ideas/:id/question-set`.
    Its plain words come with it, for S-08 to show until the card is on main (BLD-F065): the card's title, and for
    the sharer while the set is open the deadline as lane B words it (`desk.when.deadline`) and where to answer."""
    s = _set(ctx, str(x["question_set_id"]))
    if s is None or s["state"] == "queued":
        return None
    by = ctx.shown(ctx.people.by_user(str(s["by_user_id"])).as_staff(DESK))
    n = int(s["count"])
    is_open = s["state"] in OPEN_SET_STATES
    # The sharer reads Messages.md's lines: "Meera has 3 questions about your idea", "Meera’s 3 questions, answered";
    # outside the desk and the committee, "The review desk has 3 questions about your idea" (DEC-111).
    if ctx.reader.sharer and is_open:
        title = f"{by.first_name} has {plural(n, 'question')} about your idea"
    elif ctx.reader.sharer and s["state"] == "answered":
        title = f"{by.first_name}’s {plural(n, 'question')}, answered"
    elif ctx.reader.sharer:
        # Closed before every answer came, e.g. the desk decided (lane F's line, BLD-F065).
        title = f"{by.first_name}’s {plural(n, 'question')}, now closed"
    else:
        title = f"{ctx.name(by)} asked {plural(n, 'question')}."
    out: dict[str, Any] = {
        "type": "questions", "id": str(x["id"]), "set_id": str(s["id"]), "state": s["state"],
        "by": by.ref(), "by_label": ctx.name(by), "count": n, "answered": int(s["answered"]),
        "due_at": s["due_at"], "title": title,
    }  # fmt: skip
    if ctx.reader.sharer and is_open and s["due_at"]:
        out["deadline"] = (
            f"Answer by {answer_by(s['due_at'], t)}. One at a time, typed or spoken, and each answer is added to its "
            "part of your idea."
        )
        out["answer_url"] = f"/ideas/{ctx.idea['idea_id']}/answer"
    return out


def _answers(ctx: Ctx, x: dict[str, Any], staff_as: _Speaking, t: dt.datetime) -> dict[str, Any] | None:
    """One message: "Your answers to Meera’s 3 questions", each answer with the part it was added to."""
    s = _set(ctx, str(x["question_set_id"]))
    if s is None:
        return None
    rows = ctx.conn.execute(
        "SELECT a.id, a.question_id, a.text_encrypted, a.added_to, a.sent_at, q.part, q.seq "
        "FROM questions q JOIN answers a ON a.question_id = q.id "
        "WHERE q.set_id = %s AND a.sent_at IS NOT NULL ORDER BY q.seq",
        (s["id"],),
    ).fetchall()
    # This sending: the answers sent last at or before the entry's time (the entry may sit a microsecond later,
    # BLD-F057); all sent so far if none match.
    sent = [a["sent_at"] for a in rows if a["sent_at"] <= x["at"]]
    batch = [a for a in rows if sent and a["sent_at"] == max(sent)] or list(rows)
    part = labels("part")
    files = _answer_files(ctx, [str(a["id"]) for a in batch])
    answers = [
        {
            "id": str(a["id"]),
            "question_id": str(a["question_id"]),
            "text": render_answer(a),
            "added_to": a["added_to"] or a["part"],
            "added_to_label": part.get(str(a["added_to"] or a["part"]), ""),
            "at": a["sent_at"],
            "files": files.get(str(a["id"]), []),
        }
        for a in batch
    ]
    who = _sender(ctx, x, staff_as)
    reviewer = ctx.shown(ctx.people.by_user(str(s["by_user_id"])).as_staff(DESK))  # DEC-111
    n = int((x.get("payload") or {}).get("count") or len(answers))
    whose = "Your" if ctx.is_me(who) else f"{who.first_name}’s"
    asker = "your" if ctx.is_me(reviewer) else f"{reviewer.mid}’s"
    out: dict[str, Any] = {
        "type": "answers", "id": str(x["id"]), "set_id": str(s["id"]), "from": who.ref(),
        "title": f"{whose} answers to {asker} {plural(n, 'question')}", "answers": answers,
    }  # fmt: skip
    decide_by = ctx.idea.get("decide_by")
    if ctx.reader.sharer and decide_by and ctx.idea["status"] == "with_review_desk":  # S-08 "Answers sent"
        today = t.astimezone(render.IST).date()
        out["footer"] = (
            f"Each answer was added to its part of your idea. {reviewer.first_name} decides by "
            f"{render.day(decide_by, today)}."
        )
    return out


def render_answer(a: dict[str, Any]) -> str:
    from onepc.context import open_text

    return open_text("answers", "text_encrypted", str(a["id"]), a["text_encrypted"]) or ""


# ---------------------------------------------------------------------------------------------------------------
# Files: only checked ones, by ID, never opened here (non-negotiable 8), and only to readers the attachment route
# lets open them (BLD-F062): other readers get the entry without its files
# ---------------------------------------------------------------------------------------------------------------
_FILE_SQL = (
    "SELECT id, kind, name, mime, bytes, pages, item_count, file_state, hidden_note, uploaded_by_code, created_at, "
    "{key} AS owner FROM attachments WHERE {key} = ANY(%s::uuid[]) AND kind = 'file' "
    "AND (file_state = ANY(%s) OR (file_state IS NULL AND state = 'clean')) ORDER BY created_at, id"
)


def _file_item(ctx: Ctx, f: dict[str, Any]) -> dict[str, Any]:
    name = str(f["name"])
    ext = name.rsplit(".", 1)[-1].upper() if "." in name else (str(f["mime"] or "").split("/")[-1].upper())
    item: dict[str, Any] = {
        "id": f["id"], "kind": f["kind"], "name": name, "type": ext, "size": int(f["bytes"]),
        "state": f["file_state"] or "checked", "added_by": ctx.people.by_code(f["uploaded_by_code"]).ref(),
        "added_at": f["created_at"], "view_url": f"/api/attachments/{f['id']}",
    }  # fmt: skip
    if f["pages"] is not None:
        item["pages"] = int(f["pages"])
    if f["hidden_note"]:
        item["hidden_note"] = f["hidden_note"]
    return item


def _files(conn: Conn, ctx: Ctx, entry_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if not entry_ids or not ctx.reader.files:
        return out
    sql = _FILE_SQL.format(key="conversation_entry_id")
    for f in conn.execute(sql, (entry_ids, list(CLEAN_FILE_STATES))).fetchall():
        out[str(f["owner"])].append(_file_item(ctx, dict(f)))
    return out


def _answer_files(ctx: Ctx, answer_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if not answer_ids or not ctx.reader.files:
        return out
    sql = _FILE_SQL.format(key="answer_id")
    for f in ctx.conn.execute(sql, (answer_ids, list(CLEAN_FILE_STATES))).fetchall():
        out[str(f["owner"])].append(_file_item(ctx, dict(f)))
    return out


# ---------------------------------------------------------------------------------------------------------------
# Around the timeline
# ---------------------------------------------------------------------------------------------------------------
def _shown_status(conn: Conn, idea: dict[str, Any], r: Reader) -> str:
    """The status S-06 shows this reader (J-TRACK/3, BLD-F085), as lane E works it out: "needs_you" for the sharer
    while the latest question set the desk sent is open, "with_review_desk" for everyone else, even where the idea
    stores "needs_you"."""
    status = str(idea["status"])
    if status not in ("with_review_desk", "needs_you"):
        return status  # the set is read only where it can change what is shown
    qset = page_read.question_set(conn, str(idea["id"])) if r.sharer else None
    return display_status(idea, qset, for_sharer=r.sharer)


def _idea_ref(idea: dict[str, Any], status: str) -> dict[str, Any]:
    label = labels("idea_status").get(status, "")
    meta = f"{idea['idea_id']}, {label[:1].lower()}{label[1:]}" if label else str(idea["idea_id"])
    return {"id": idea["idea_id"], "title": idea.get("title") or "", "status": status, "meta": meta}


def _header(ctx: Ctx, sharer: Person, team: dict[str, Any] | None, t: dt.datetime) -> dict[str, str]:
    """'Your idea, shared Saturday 14 November' / 'Ravi Nair’s idea, Investor service, Hyderabad' / 'Your idea,
    being built by Arjun Rao’s team' (S-08.layout/1)."""
    mine = ctx.reader.sharer
    whose = "Your idea" if mine else f"{sharer.name}’s idea"
    if team:  # named after its lead, as the board draws it (J-TRACK/9); the team's own name if it has no lead
        lead = ctx.people.by_user(str(team["lead_user_id"])) if team["lead_user_id"] else None
        line = f"{whose}, being built by {f'{lead.name}’s team' if lead and lead.id else team['name']}"
    elif mine and ctx.idea.get("shared_at"):
        line = f"{whose}, shared {render.day(ctx.idea['shared_at'], t.astimezone(render.IST).date())}"
    else:
        line = ", ".join(x for x in (whose, ctx.idea.get("area"), ctx.idea.get("city")) if x)
    return {"whose": "Your idea" if mine else "The idea", "line": line}


def _crew(conn: Conn, idea: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        dict(c)
        for c in conn.execute(
            "SELECT contributor_code, role, joined_at FROM crew_members WHERE idea_uuid = %s AND left_at IS NULL "
            "ORDER BY role = 'lead' DESC, joined_at, id",
            (idea["id"],),
        ).fetchall()
    ]


def _participants(
    ctx: Ctx, idea: dict[str, Any], crew: list[dict[str, Any]], team: dict[str, Any] | None,
    rows: list[dict[str, Any]], staff_as: _Speaking, sharer: Person, t: dt.datetime,
) -> list[dict[str, Any]]:  # fmt: skip
    """'In this conversation' (L-CONVO/8): each person with what they are doing; the reader last, as "You". Outside
    the review desk and the committee, the desk's people are one row, "The review desk" (DEC-111)."""
    seen: dict[str, tuple[Person, str]] = {}

    def add(p: Person, doing: str) -> None:
        key = "desk" if p.desk else p.id
        if key and key not in seen:
            seen[key] = (p, doing)

    if team:
        if team["lead_user_id"]:
            add(ctx.people.by_user(str(team["lead_user_id"])), "Leads the build team")
        for g in ctx.conn.execute(
            "SELECT user_id FROM role_grants WHERE role = 'build_team' AND scope_id = %s AND valid_from <= now() "
            "AND (valid_to IS NULL OR valid_to > now()) ORDER BY id",
            (idea["idea_id"],),
        ).fetchall():
            add(ctx.people.by_user(str(g["user_id"])), "On the build team")
    reviewer_id = idea.get("reviewer_id") or idea.get("opened_by")
    if reviewer_id:
        add(ctx.shown(ctx.people.by_user(str(reviewer_id)).as_staff(DESK)), _reviewer_doing(ctx, idea))
    add(sharer, "Shared the idea")
    today = t.astimezone(render.IST).date()
    for c in crew:
        if c["role"] == "crew":
            joined = c["joined_at"].astimezone(render.IST).date() == today
            add(ctx.people.by_code(c["contributor_code"]), "Joined today" if joined else "On the crew")
    for x in rows:
        if x["type"] == "message" and x["deleted_at"] is None:
            for u in _mentions(x):
                add(ctx.shown(ctx.people.by_user(u), at_desk=_at_desk(ctx, staff_as, u)), "Mentioned")
    for x in rows:
        if x["type"] == "message":
            who = _sender(ctx, x, staff_as)
            add(who, "From the review desk" if who.desk or who.role_label == DESK else
                "From the Ones Committee" if who.role_label == COMMITTEE else "In the conversation")  # fmt: skip
    me = seen.pop(ctx.reader.user_id, None)
    out = [{"person": p.ref(), "label": p.label, "doing": d, "you": False} for p, d in seen.values()]
    if me:
        out.append({"person": me[0].ref(), "label": "You", "doing": me[1], "you": True})
    return out


def _reviewer_doing(ctx: Ctx, idea: dict[str, Any]) -> str:
    row = ctx.conn.execute(
        "SELECT choice FROM idea_decisions WHERE idea_uuid = %s ORDER BY at DESC LIMIT 1", (idea["id"],)
    ).fetchone()
    if row is None:
        return "Reviewing it"
    return {"pick": "Picked it", "not_now": "Chose Not now", "not_picked": "Didn’t pick it"}.get(
        str(row["choice"]), "Reviewing it"
    )


def _composer(
    ctx: Ctx,
    idea: dict[str, Any],
    audience: str,
    has_crew: bool,
    sharer: Person,
    rows: list[dict[str, Any]],
    staff_as: _Speaking,
) -> dict[str, Any]:
    """The box: its placeholder by audience (L-CONVO/5), who can see it (S-08.layout/3) and, for the sharer while
    questions are open, the line above it (L-CONVO/4)."""
    r = ctx.reader
    out: dict[str, Any] = {
        "placeholder": _placeholder(ctx, audience, has_crew, sharer, rows, staff_as),
        "visibility": _visibility(ctx, audience, has_crew, sharer),
        "can_attach": r.may_attach,  # S-08 shows the attach control only then (BLD-F063)
    }
    if r.sharer:
        s = ctx.conn.execute(
            "SELECT s.by_user_id, (SELECT count(*) FROM questions q LEFT JOIN answers a ON a.question_id = q.id "
            "  WHERE q.set_id = s.id AND a.sent_at IS NULL) AS open "
            "FROM question_sets s WHERE s.idea_uuid = %s AND s.state = ANY(%s) ORDER BY s.sent_at DESC LIMIT 1",
            (idea["id"], list(OPEN_SET_STATES)),
        ).fetchone()
        if s is not None and int(s["open"]) > 0:
            first = ctx.shown(ctx.people.by_user(str(s["by_user_id"])).as_staff(DESK)).mid  # DEC-111
            out["questions_line"] = (
                f"Answer {first}’s {plural(int(s['open']), 'question')} with Answer the questions, so each answer "
                "lands on its part of your idea. Write here for anything else."
            )
    if idea["status"] == "merged":
        out["closed"] = closed_message(ctx.conn, idea)
    return out


def closed_message(conn: Conn, idea: dict[str, Any]) -> str:
    row = conn.execute(
        "SELECT l.idea_id FROM merges m JOIN ideas l ON l.id = m.lead_idea_uuid "
        "WHERE m.merged_idea_uuid = %s AND m.reversed_at IS NULL ORDER BY m.at DESC LIMIT 1",
        (idea["id"],),
    ).fetchone()
    where = f"{row['idea_id']}’s conversation" if row else "the idea it joined"
    return f"This idea is now part of another one. Write in {where}."


def _placeholder(
    ctx: Ctx, audience: str, has_crew: bool, sharer: Person, rows: list[dict[str, Any]], staff_as: _Speaking
) -> str:
    r = ctx.reader
    if not r.full:  # "Reply to Sanjay": whoever mentioned them last; "Reply to the review desk" (DEC-111)
        last = next((x for x in reversed(rows) if r.user_id in _mentions(x)), None)
        if last is not None:
            return f"Reply to {_sender(ctx, last, staff_as).mid}"
    if audience == "build_team":
        if r.build:
            return "Message the crew" if has_crew else f"Reply to {sharer.first_name}"
        return "Message the build team"
    if audience == "crew_and_desk":
        return "Message the crew"
    return "Message the review desk" if r.sharer else f"Reply to {sharer.first_name}"


def _visibility(ctx: Ctx, audience: str, has_crew: bool, sharer: Person) -> str:
    r = ctx.reader
    if not r.full:
        if has_crew:
            return "The crew, the review desk and anyone they mention see this conversation."
        return f"{sharer.first_name}, the review desk and anyone they mention see this conversation."
    if audience == "build_team":
        if r.sharer:  # the board's line for the sharer, crew or not (BLD-F060, J-TRACK/9)
            return "You, the build team and the review desk see this conversation."
        if has_crew:
            return "The crew, the build team and the review desk see this conversation."
        return f"{sharer.first_name}, the build team and the review desk see this conversation."
    if audience == "crew_and_desk":
        return "The crew and the review desk see this conversation."
    if r.sharer:
        return "Only you and the review desk see this conversation."
    return f"Only {sharer.first_name} and the review desk see this conversation."


def entry_for(
    conn: Conn, idea: dict[str, Any], user_id: str, entry_id: str, at: dt.datetime | None = None
) -> dict[str, Any]:
    """One message as its reader sees it: what `POST` and `DELETE` return, so the screen can place it at once."""
    t = at or now()
    ctx = Ctx(conn, People(conn), reader(conn, idea, user_id), idea)
    x = conn.execute("SELECT * FROM conversation_entries WHERE id = %s", (entry_id,)).fetchone()
    assert x is not None
    files = _files(conn, ctx, [entry_id] if x["deleted_at"] is None else [])
    e = _entry(ctx, dict(x), files, _Speaking(conn, idea), t)
    assert e is not None
    e["at"], e["at_label"] = x["at"], when(x["at"], t)
    return e
