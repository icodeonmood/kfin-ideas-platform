"""Turn a stored inbox item (IDs only) into what one person reads: the Inbox row and reader (E-ENTITIES `InboxItem`)
and the email (L-NOTIFY/3). Words come from `comms/templates/inbox/<kind>.md` (HR signs them off); facts come
from the rows the IDs point to, read at the moment the item is shown or sent.

Nothing here reads anyone's words: not a decision's reason, a request's note, a question or an answer. The idea's
title is its masked title (L-HIDE), the one line every message may carry.
"""

from __future__ import annotations

import datetime as dt
from typing import Any
from zoneinfo import ZoneInfo

from comms import email_html
from comms.templates import Template, load, render_text
from core.config import get_settings
from core.db import Conn
from notify import AS_THE_COMMITTEE, AS_THE_DESK, as_the_committee, as_the_desk, sees_names
from onepc import countdown as clock
from onepc.words import ONES_COMMITTEE_START, REVIEW_DESK_START
from similar.preview import HIDDEN_NAME, hidden_person

IST = ZoneInfo("Asia/Kolkata")

# Who the sender is (L-INBOX.kinds "Sender display", as DEC-111 changes it): the review desk's kinds come from the
# review desk as a whole, the Ones Committee by full name, everyone else by full name, the system as "1% Club".
# DEC-111 (BLD-A221): a sharer, a crew member or anyone outside the desk and the committee never sees the name of the
# person at the review desk, so a desk kind reads "The review desk" with the mark, whoever reads it, and the reviewer
# is never read: no users.id, name, first name or initials reach the item, its variables or its email. L-HIDE/7's
# kind (`notify.AS_THE_DESK`, BLD-A205) is one of them, and its reviewer is not even stored. Any other item whose refs
# say `as_desk: true` (lane F's comment and mention when a reviewer writes as the desk) reads the same way, and its
# reviewer is not stored either (`notify.as_the_desk`). DEC-113 (BLD-A231): the Ones Committee likewise. A committee
# kind names its member only to a reader who holds a desk or committee role now (live role grants, as
# `ideapage.read.Viewer.sees_desk_names`); everyone else reads "The Ones Committee", with no avatar or initials, and
# the member is never read for them. An item whose refs say `as_committee: true` (lane F's comment and mention when a
# member writes in the conversation) reads the same way to whoever reads it (`notify.as_the_committee`).
DESK_KINDS = frozenset({"questions", "decision", "worth_revised", "desk_merge"}) | AS_THE_DESK
# Kinds the 1% Club sends whoever set them off (DEC-111, BLD-A221): an idea sent to the review desk. It never names a
# person, and the sender is never read. The reminder to answer the desk's questions is the desk's own
# (`notify.AS_THE_DESK`, BLD-B257), so it reads "The review desk" through DESK_KINDS.
SYSTEM_KINDS = frozenset({"sent_to_desk"})
COMMITTEE_KINDS = AS_THE_COMMITTEE
COUNTDOWN_KINDS = frozenset({"questions", "answer_reminder"})  # "3 days left"; the rest read "By Thu, 19 Nov"
STAGE_WORDS = {"picked": "Picked", "being_built": "Being built", "shipped": "Shipped"}
SYSTEM = {"display": "1% Club", "name": "1% Club", "first_name": "1% Club", "initials": "1%", "system": True}
# The review desk as a whole, shown with the mark (L-HIDE/7, BLD-A205; DEC-111). The words are the shared label
# (`onepc.words`), so every lane names the desk the same way.
DESK_SENDER = {
    **SYSTEM,
    "display": REVIEW_DESK_START,
    "name": REVIEW_DESK_START,
    "first_name": REVIEW_DESK_START,
}
# The Ones Committee as one (DEC-113): a speaker with no person behind it. No users.id, no initials and no mark, so the
# reader draws no avatar at all; not `system`, so the reader does not draw the 1% mark either.
COMMITTEE_SENDER: dict[str, Any] = {
    "id": "",
    "name": ONES_COMMITTEE_START,
    "first_name": ONES_COMMITTEE_START,
    "initials": "",
    "display": ONES_COMMITTEE_START,
    "system": False,
}
# Kinds whose one action is the whole of it: no "Open the conversation" is added (L-HIDE/7: "Open your idea" only).
ONE_ACTION_KINDS = frozenset({"detail_hidden_by_desk"})
# A decision read from the idea when the item names none (`choice`, `decision_id`): its status says which.
STATUS_CHOICE = {
    "picked": "pick",
    "being_built": "pick",
    "shipped": "pick",
    "not_now": "not_now",
    "not_picked": "not_picked",
}

# The kind's own buttons when the caller gives none (L-INBOX.kinds "Reader action"). `to` keys are resolved for the
# item's idea by `route`.
DEFAULT_ACTIONS: dict[str, list[dict[str, str]]] = {
    "questions": [{"label": "Answer the questions", "to": "answer", "style": "primary"}],
    "answer_reminder": [{"label": "Answer the questions", "to": "answer", "style": "primary"}],
    "teamup_request": [{"label": "Open the request", "to": "inbox", "style": "primary"}],
    "teamup_answer": [{"label": "Open the idea", "to": "idea", "style": "primary"}],
    "decision": [{"label": "Read the decision", "to": "idea", "style": "primary"}],
    "decision_reversed": [{"label": "Read the note", "to": "idea", "style": "primary"}],
    "desk_merge": [{"label": "Open the idea", "to": "idea", "style": "primary"}],
    "worth_revised": [{"label": "Open the idea", "to": "idea", "style": "primary"}],
    "stage_moved": [{"label": "Open the idea", "to": "idea", "style": "primary"}],
    "build_ask": [{"label": "Open the conversation", "to": "conversation", "style": "primary"}],
    "mention": [{"label": "Open the conversation", "to": "conversation", "style": "primary"}],
    "crew_joined": [{"label": "Open the idea", "to": "idea", "style": "primary"}],
    "comment": [{"label": "Open the conversation", "to": "conversation", "style": "primary"}],
    "draft_kept": [{"label": "Carry on", "to": "draft", "style": "primary"}],  # by `via`: `default_actions`
    "sent_to_desk": [{"label": "Open the idea", "to": "idea", "style": "primary"}],
    "detail_hidden_by_desk": [{"label": "Open your idea", "to": "idea", "style": "primary"}],
}
_STYLE_ORDER = {"text": 0, "line": 1, "primary": 2}
# Where a kept draft came from (BLD-A188): lane C posts `via`. A draft sent in by email or Teams is checked and sent
# (J-RESUME/6); one from the phone, or from nowhere the refs say, is carried on (J-RESUME/3).
VIA = ("phone", "email", "teams")
SENT_IN = frozenset({"email", "teams"})
CHECK_AND_SEND: list[dict[str, str]] = [{"label": "Check and send", "to": "draft", "style": "primary"}]
# `item_id` when an "inbox" link opens the row itself (the in-app item being read); None opens the Inbox.
OWN_ROW: Any = object()


def _via(refs: dict[str, Any]) -> str | None:
    via = refs.get("via")
    return via if isinstance(via, str) and via in VIA else None


def default_actions(kind: str, refs: dict[str, Any]) -> list[dict[str, str]]:
    """The kind's own buttons when the caller gives none (L-INBOX.kinds "Reader action"); a kept draft's by `via`."""
    if kind == "draft_kept" and _via(refs) in SENT_IN:
        return CHECK_AND_SEND
    return DEFAULT_ACTIONS.get(kind, [])


def initials(name: str) -> str:
    parts = [p for p in name.split() if p]
    if not parts:
        return "?"
    letters = parts[0][:2] if len(parts) == 1 else parts[0][0] + parts[-1][0]
    return letters.upper()


def person(conn: Conn, user_id: Any) -> dict[str, Any] | None:
    if not user_id:
        return None
    row = conn.execute("SELECT id, name, first_name FROM users WHERE id = %s", (str(user_id),)).fetchone()
    if row is None or not row["name"]:
        return None
    name = str(row["name"])
    first = str(row["first_name"] or name.split()[0])
    return {"id": str(row["id"]), "name": name, "first_name": first, "initials": initials(name)}


def lead_seen_by_requester(
    conn: Conn, user_id: Any, idea: dict[str, Any] | None, viewer: str
) -> dict[str, Any] | None:
    """The lead as the requester they declined may see them (DEC-104, BLD-A196), decided by lane F's own rule,
    `teamup.store.lead_seen_by` (BLD-F029, lane C's `person_refs` with `names_always=False`), so the Inbox and every
    team-up read agree: a lead who hid their name from the Wall, or has left, is lane C's `hidden_person` ("A
    colleague", no initials, an opaque `p…` id, never their users.id) with `hidden` set, unless the reader is on the
    idea's live crew or is the review desk or the Ones Committee. An item with no idea names no one (fail closed).
    An approved requester is on the crew and reads `person`."""
    if not user_id:
        return None
    if idea is None or not idea.get("contributor_code"):
        return {**hidden_person(f"user:{user_id}"), "hidden": True}
    from teamup.store import crew_role, lead_seen_by  # lane F's package; imported here, as it imports notify

    on_crew = next((c for c in sorted(_codes(conn, viewer)) if crew_role(conn, idea["uuid"], c)), None)
    seen = lead_seen_by(
        conn, {"id": idea["uuid"], "contributor_code": idea["contributor_code"]}, viewer, on_crew
    )
    ref = {k: seen.ref[k] for k in ("id", "name", "first_name", "initials")}
    return ref if seen.first is not None else {**ref, "hidden": True}


def sender(kind: str, who: dict[str, Any] | None, refs: dict[str, Any] | None = None) -> dict[str, Any]:
    """The sender as the item shows them. A desk kind, or an item whose refs say `as_desk`, is the review desk as a
    whole, and a system kind the 1% Club, whoever `who` is (DEC-111): neither carries a person. An item whose refs say
    `as_committee`, or a committee kind with no member to name (`who` None: the reader may not see them, or none is
    stored), is the Ones Committee as one (DEC-113)."""
    if kind in DESK_KINDS or as_the_desk(kind, refs):
        return dict(DESK_SENDER)
    if as_the_committee(kind, refs) or (who is None and kind in COMMITTEE_KINDS):
        return dict(COMMITTEE_SENDER)
    if who is None or kind in SYSTEM_KINDS:
        return dict(SYSTEM)
    if kind in COMMITTEE_KINDS:
        role, display = "from the Ones Committee", f"{who['name']} from the Ones Committee"
    else:
        role, display = "", who["name"]
    return {**who, "role_label": role, "display": display, "system": False}


def names_no_one(kind: str, refs: dict[str, Any] | None = None) -> bool:
    """An item whose sender is never read (DEC-111, DEC-113): the review desk's kinds and the 1% Club's own, and any
    item whose refs say `as_desk` or `as_committee`. A committee kind is read only for a reader who may see its member
    (`names_member`)."""
    return (
        kind in DESK_KINDS or kind in SYSTEM_KINDS or as_the_desk(kind, refs) or as_the_committee(kind, refs)
    )


def names_member(conn: Conn, kind: str, viewer: str) -> bool:
    """Whether this reader may read the committee member behind a committee kind (DEC-113): only the review desk and
    the Ones Committee, by their role grants at the moment the item is read or sent (`notify.sees_names`)."""
    return kind not in COMMITTEE_KINDS or viewer in sees_names(conn, [viewer])


def _possessive(first_name: str | None) -> str:
    """ "Meera’s", "Dhanus’", "a colleague’s": the typographic apostrophe of every inbox line (BLD-A195)."""
    if not first_name:
        return "a colleague’s"
    return f"{first_name}’" if first_name.endswith("s") else f"{first_name}’s"


def _clock(t: dt.datetime) -> str:
    hour = t.hour % 12 or 12
    suffix = "am" if t.hour < 12 else "pm"
    return f"{hour} {suffix}" if t.minute == 0 else f"{hour}:{t.minute:02d} {suffix}"


def long_date(at: dt.datetime) -> str:
    """ "Thursday 19 November, 6 pm" (S-H5 reader, C-QCARD)."""
    t = at.astimezone(IST)
    return f"{t:%A} {t.day} {t:%B}, {_clock(t)}"


def short_date(at: dt.datetime) -> str:
    """ "Thu, 19 Nov"."""
    t = at.astimezone(IST)
    return f"{t:%a}, {t.day} {t:%b}"


def countdown(at: dt.datetime, now: dt.datetime) -> str:
    """ "2 days left", "07:38 left", "Overdue by 5 hours" (A-API.conventions/6: the server says it). The one rule every
    place counts by (F-COPY.plurals/3, `onepc.countdown`, BLD-A225), with the Inbox's own word after the count."""
    return clock.label(at, now, "left")


def due(kind: str, at: dt.datetime | None, now: dt.datetime) -> dict[str, Any] | None:
    if at is None:
        return None
    out: dict[str, Any] = {"at": at.isoformat(), "long": long_date(at), "short": short_date(at), "any": True}
    if kind in COUNTDOWN_KINDS:
        c = clock.countdown(at, now)
        out["label"], out["variant"] = c.label("left"), c.variant  # the pill: warn under a day, bad once late
    else:
        out["label"] = f"By {short_date(at)}"
    return out


def _idea(conn: Conn, idea_uuid: Any) -> dict[str, Any] | None:
    if not idea_uuid:
        return None
    row = conn.execute(
        "SELECT id, idea_id, title, status, decide_by, contributor_code FROM ideas WHERE id = %s",
        (str(idea_uuid),),
    ).fetchone()
    if row is None:
        return None
    status = str(row["status"])
    title = (row["title"] or "").strip() or ("Untitled draft" if status == "draft" else "Your idea")
    return {
        "uuid": str(row["id"]),
        "ref": row["idea_id"],
        "title": title,
        "status": status,
        "decide_by": long_date(row["decide_by"]).split(",")[0] if row["decide_by"] else "",
        "contributor_code": row["contributor_code"],
    }


def route(to: str | None, idea: dict[str, Any] | None, item_id: Any) -> str | None:
    """An action's `to`: an app path as given, or a key resolved for the item's idea."""
    if not to:
        return None
    if to.startswith("/"):
        return to
    ref = (idea or {}).get("ref")
    if to == "inbox":
        return f"/inbox/{item_id}" if item_id is not None else "/inbox"
    if to == "draft":
        return f"/share/{idea['uuid']}" if idea else None
    if not ref:
        return None
    return {
        "answer": f"/ideas/{ref}/answer",
        "idea": f"/ideas/{ref}",
        "conversation": f"/ideas/{ref}/conversation",
    }.get(to)


def _codes(conn: Conn, user_id: str) -> set[str]:
    rows = conn.execute(
        "SELECT contributor_code FROM contributor_map WHERE user_id = %s", (user_id,)
    ).fetchall()
    return {str(r["contributor_code"]) for r in rows}


def _first_name_for_code(conn: Conn, code: str | None) -> str | None:
    if not code:
        return None
    row = conn.execute(
        "SELECT u.name, u.first_name FROM contributor_map m JOIN users u ON u.id = m.user_id "
        "WHERE m.contributor_code = %s LIMIT 1",
        (code,),
    ).fetchone()
    if row is None or not row["name"]:
        return None
    return str(row["first_name"] or str(row["name"]).split()[0])


def _left(row: dict[str, Any], now: dt.datetime) -> str:
    """How long is left on a reminder, as it is read: "2 days", "07:38" (the countdown's count, F-COPY.plurals/3).
    Once the time has passed, what was left when it was sent: "1 day" for the day-before reminder, else the whole
    hours as "02:00" (L-QUESTIONS.clock/2)."""
    at = row.get("due_at")
    if at is not None and at > now:
        return clock.countdown(at, now).count
    hours = 24.0
    if at is not None and row.get("created_at"):
        hours = (at - row["created_at"]).total_seconds() / 3600
    return "1 day" if hours >= 20 else f"{max(1, round(hours)):02d}:00"


def teamup_request_vars(refs: dict[str, Any], offered: list[str]) -> dict[str, Any]:
    """Which request the lead reads (S-H2B.reader/1, L-INBOX.kinds): a "Merge request" when it brings an idea, so a
    draft merge request (`request` "merge") and a sheet request with any idea brought (lane F's `tell_lead` posts
    `request` "teamup" with `brought`, the number of ideas brought); a "Team-up request" when nothing comes along.
    An item that names neither (the seed, BLD-A206) is a merge when it offers one. Lane F's reader words agree
    (`teamup.rules.reader_words`): "idea" for one, "ideas" for more (BLD-A195)."""
    raw = refs.get("brought")
    brought = int(raw) if isinstance(raw, int) else 0  # True counts as one
    merge = (
        refs.get("request") == "merge"
        or brought > 0
        or ("request" not in refs and any(op.rsplit(".", 1)[-1] == "merge" for op in offered))
    )
    return {
        "request": {"merge": merge, "team_only": not merge},
        "brought": {"any": brought > 0, "count": brought, "many": brought > 1, "single": brought <= 1},
    }


def _kind_vars(
    conn: Conn,
    kind: str,
    refs: dict[str, Any],
    row: dict[str, Any],
    viewer: str,
    idea: dict[str, Any] | None,
    now: dt.datetime,
) -> dict[str, Any]:
    """The kind's facts, from the rows its IDs point to. Booleans drive the template's sections."""
    out: dict[str, Any] = {}
    if kind in ("questions", "answer_reminder"):
        # The set and its count only: who asked is never read, as the desk asks as a whole (DEC-111, BLD-A221)
        n, qs = 0, None
        count_sql = "SELECT s.id, (SELECT count(*) FROM questions q WHERE q.set_id = s.id) AS n "
        if refs.get("set_id"):
            qs = conn.execute(
                count_sql + "FROM question_sets s WHERE s.id::text = %s", (str(refs["set_id"]),)
            ).fetchone()
        elif idea is not None:  # an item that names no set: the idea's latest one sent
            qs = conn.execute(
                count_sql + "FROM question_sets s WHERE s.idea_uuid = %s AND s.sent_at IS NOT NULL "
                "ORDER BY s.sent_at DESC LIMIT 1",
                (idea["uuid"],),
            ).fetchone()
        if qs is not None:
            n = int(qs["n"])
            out["set_id"] = str(qs["id"])
        if not n and isinstance(refs.get("count"), int):
            n = int(refs["count"])
        out["count"] = n
        out["count_words"] = "1 question" if n == 1 else (f"{n} questions" if n else "some questions")
        if kind == "answer_reminder":
            out["left"] = _left(row, now)
    elif kind == "decision":
        choice = refs.get("choice")
        if not choice and refs.get("decision_id"):
            d = conn.execute(
                "SELECT choice FROM idea_decisions WHERE id::text = %s", (str(refs["decision_id"]),)
            ).fetchone()
            choice = d["choice"] if d else None
        if not choice and idea is not None:  # the idea's latest decision, else what its status says
            d = conn.execute(
                "SELECT choice FROM idea_decisions WHERE idea_uuid = %s ORDER BY at DESC LIMIT 1",
                (idea["uuid"],),
            ).fetchone()
            choice = d["choice"] if d else STATUS_CHOICE.get(idea["status"])
        out["choice"] = {c: choice == c for c in ("pick", "not_now", "not_picked")}
    elif kind == "decision_reversed":
        decided = False
        if idea is not None:
            r = conn.execute(
                "SELECT 1 FROM ideas i WHERE i.id = %s AND i.reviewer_id = %s UNION ALL SELECT 1 FROM idea_decisions d "
                "WHERE d.idea_uuid = %s AND d.by_user_id = %s LIMIT 1",
                (idea["uuid"], viewer, idea["uuid"], viewer),
            ).fetchone()
            decided = r is not None and idea.get("contributor_code") not in _codes(conn, viewer)
        out["viewer"] = {"decided": decided, "sharer": not decided}
        out["merge"] = bool(refs.get("merge_id"))
    elif kind == "desk_merge":
        other = None
        if refs.get("merge_id"):
            m = conn.execute(
                "SELECT a.contributor_code AS lead_code, b.contributor_code AS merged_code FROM merges g "
                "JOIN ideas a ON a.id = g.lead_idea_uuid JOIN ideas b ON b.id = g.merged_idea_uuid WHERE g.id::text = %s",
                (str(refs["merge_id"]),),
            ).fetchone()
            if m is not None:
                mine = _codes(conn, viewer)
                code = m["merged_code"] if m["lead_code"] in mine else m["lead_code"]
                other = _first_name_for_code(conn, code)
        out["other"] = {"possessive": _possessive(other)}
    elif kind == "teamup_request":
        offered = [str(a.get("op") or "") for a in (row.get("actions") or []) if isinstance(a, dict)]
        out.update(teamup_request_vars(refs, offered))
    elif kind == "teamup_answer":
        answer = refs.get("answer")
        declined = answer == "decline"
        # Lane F's `has_reason` (never the reason): only a decline that says it has one reads "with a reason"
        reason = declined and refs.get("has_reason") is True
        out["answer"] = {"declined": declined, "approved": not declined, "with_reason": reason,
                         "no_reason": declined and not reason}  # fmt: skip
    elif kind == "stage_moved":
        to = refs.get("to") or refs.get("stage") or (idea or {}).get("status")
        out["stage"] = {"words": STAGE_WORDS.get(str(to), "its next stage")}
    elif kind == "draft_kept":
        # A missing or unknown `via` says nothing about where: the plain "kept your draft" with "Carry on" (BLD-A188).
        via = _via(refs)
        out["via"] = {**{v: via == v for v in VIA}, "sent_in": via in SENT_IN, "kept": via not in SENT_IN}
    return out


def variables(
    conn: Conn,
    row: dict[str, Any],
    viewer: str,
    now: dt.datetime,
    *,
    absolute: bool = False,
    item_id: Any = OWN_ROW,
) -> tuple[Template, dict[str, Any]]:
    """The template and its variables for one item and one reader. Links are app paths, or full addresses for an
    email (`absolute`). `item_id` is the in-app item an "inbox" link opens (`OWN_ROW`: this row; None: the Inbox)."""
    kind = str(row["kind"])
    tpl = load(f"inbox/{kind}")
    refs = dict(row.get("payload") or {})
    idea = _idea(conn, row.get("idea_uuid"))
    me = person(conn, viewer) or {"first_name": "there"}
    if names_no_one(kind, refs) or not names_member(conn, kind, viewer):
        # DEC-111, DEC-113: the reviewer, or the committee member, is not read at all, so no template can name them
        who = sender(kind, None, refs)
    elif kind == "teamup_answer" and refs.get("answer") == "decline":
        who = sender(kind, lead_seen_by_requester(conn, row.get("from_user_id"), idea, viewer))
    else:
        who = sender(kind, person(conn, row.get("from_user_id")))
    if who.get("hidden"):  # the template's word for a sender who is not named ("The lead", BLD-A196)
        who["display"] = tpl.inbox.get("hidden_sender") or HIDDEN_NAME
    base = get_settings().app_base_url.rstrip("/") if absolute else ""
    actions = resolved_actions(row, idea, item_id=item_id)
    forward = next((a for a in reversed(actions) if a.get("to")), None)

    def link(path: str | None) -> str:
        return f"{base}{path}" if path else f"{base}/inbox"

    data: dict[str, Any] = {
        "recipient": {"first_name": me["first_name"]},
        "from": who,
        "idea": idea or {"title": "", "ref": ""},
        "due": due(kind, row.get("due_at"), now) or {"any": False},
        "decide_by": {"long": (idea or {}).get("decide_by", ""), "any": bool((idea or {}).get("decide_by"))},
        "links": {
            "action": link(forward["to"] if forward else route("idea", idea, None)),
            "idea": link(route("idea", idea, None)),
            "inbox": link("/inbox"),
        },
        **_kind_vars(conn, kind, refs, row, viewer, idea, now),
    }
    data["line"] = render_text(tpl.inbox.get("line", ""), data).strip()
    return tpl, data


def _path_of(to: str) -> str:
    """An action's path without its `#…` or `?…`: "Say hello" goes to a place on the conversation
    (`/ideas/{ref}/conversation#say-hello`) and is that conversation's link all the same (L-INBOX.rules/6, BLD-A220)."""
    return to.split("#", 1)[0].split("?", 1)[0]


def resolved_actions(
    row: dict[str, Any], idea: dict[str, Any] | None, *, item_id: Any = OWN_ROW
) -> list[dict[str, Any]]:
    """The item's buttons, in footer order: the forward one last, as the primary (S-H5.rules/3), with "Open the
    conversation" as a line button before it when the item is about a shared idea (L-INBOX.rules/6)."""
    kind = str(row["kind"])
    given = [dict(a) for a in (row.get("actions") or [])] or [
        dict(a) for a in default_actions(kind, dict(row.get("payload") or {}))
    ]
    out: list[dict[str, Any]] = []
    for a in given:
        entry: dict[str, Any] = {"label": str(a.get("label") or ""), "style": a.get("style") or "line"}
        if a.get("op"):
            entry["op"] = str(a["op"])
        path = route(a.get("to"), idea, row.get("id") if item_id is OWN_ROW else item_id)
        if path:
            entry["to"] = path
        if entry.get("to") or entry.get("op"):
            out.append(entry)
    if out and not any(a["style"] == "primary" for a in out):
        out[-1]["style"] = "primary"
    ref = idea.get("ref") if idea is not None and idea["status"] != "draft" else None
    if (
        ref
        and kind not in ONE_ACTION_KINDS
        and not any(_path_of(a.get("to", "")).endswith("/conversation") for a in out)
    ):
        out.append({"label": "Open the conversation", "to": f"/ideas/{ref}/conversation", "style": "line"})
    return sorted(out, key=lambda a: _STYLE_ORDER.get(str(a["style"]), 1))


def item(conn: Conn, row: dict[str, Any], viewer: str, now: dt.datetime) -> dict[str, Any]:
    """E-ENTITIES `InboxItem` for the reader. `body.sender` is the sender as the row shows them."""
    tpl, data = variables(conn, row, viewer, now)
    kind = str(row["kind"])
    idea = data["idea"] if data["idea"].get("ref") or data["idea"].get("uuid") else None
    who = data["from"]
    needs = bool(row.get("needs_you")) and row.get("resolved_at") is None
    body: dict[str, Any] = {
        "heading": render_text(tpl.inbox.get("heading", ""), data).strip(),
        "note": render_text(tpl.inbox.get("note", ""), data).strip(),
        "sender": who["display"],
    }
    refs = dict(row.get("payload") or {})
    for key in ("set_id", "decision_id", "request_id", "merge_id", "window_id", "entry_id", "worth_id"):
        if refs.get(key):
            body[key] = str(refs[key])
    if data.get("set_id") and "set_id" not in body:
        body["set_id"] = data["set_id"]
    if "count" in data:
        body["count"] = data["count"]
    out: dict[str, Any] = {
        "id": str(row["id"]),
        "kind": kind,
        "from": "system"
        if who.get("system")
        else {
            k: who[k]
            for k in ("id", "name", "first_name", "initials", "role_label")
            if who.get(k) is not None
        },
        "line": data["line"],
        "at": row["created_at"].isoformat(),
        "unread": row.get("read_at") is None,
        "needs_you": needs,
        "archived": row.get("archived_at") is not None,
        "body": body,
        "actions": resolved_actions(row, idea),
    }
    if idea is not None:
        out["idea"] = {
            "id": idea.get("ref") or idea["uuid"],
            "title": idea["title"],
            "status": idea["status"],
        }
    d = data["due"]
    if d.get("any") and (needs or kind == "build_ask"):
        out["due"] = {"at": d["at"], "label": d["label"]}
        if "variant" in d:  # a countdown's pill, so the Inbox tones it as the card beside it does (BLD-A225)
            out["due"]["variant"] = d["variant"]
    return out


def in_app_item(conn: Conn, row: dict[str, Any]) -> int | None:
    """The person's in-app item an email (or Teams) row stands for, so its "Open the request" opens that item: the
    one with the same key, else the latest of its kind on the same idea posted with it or before it. None: there is
    none, and the link is the Inbox itself. The row's own id is never an item (an email row is not in the Inbox)."""
    user, kind, idea = row.get("user_id"), row.get("kind"), row.get("idea_uuid")
    if not user or not kind:
        return None
    if row.get("dedupe_key"):
        found = conn.execute(
            "SELECT id FROM notifications WHERE user_id = %s AND channel = 'in_app' AND dedupe_key = %s",
            (str(user), str(row["dedupe_key"])),
        ).fetchone()
        if found is not None:
            return int(found["id"])
    if idea:
        found = conn.execute(
            "SELECT id FROM notifications WHERE user_id = %s AND channel = 'in_app' AND kind = %s AND idea_uuid = %s "
            "AND (%s::bigint IS NULL OR id < %s::bigint) ORDER BY id DESC LIMIT 1",
            (str(user), str(kind), str(idea), row.get("id"), row.get("id")),
        ).fetchone()
        if found is not None:
            return int(found["id"])
    return None


def email(conn: Conn, row: dict[str, Any], now: dt.datetime | None = None) -> email_html.Email:
    """The email for one queued inbox item: the idea's title, what happened, any date and a link (L-NOTIFY/3). An
    "inbox" link opens the person's in-app item, never the email row's own id."""
    tpl, data = variables(
        conn,
        row,
        str(row["user_id"]),
        now or dt.datetime.now(dt.UTC),
        absolute=True,
        item_id=in_app_item(conn, row),
    )
    return email_html.compose(tpl, data, get_settings().app_base_url)
