"""S-06, the sharer's own idea page: where it is, what happens next and by when, and what they can do now.

States are named as S-06.states names them ("Just shared", "Questions from the review desk", "Answers sent",
"Picked", "Not now", "Not picked, with the reason", "Reversed by the Ones Committee", "Withdrawn"); the statuses
the board does not draw on this page (being built, shipped, merged) follow the same pattern and are marked
NOT DRAWN in the words. Copy is the board's (reference/copy/Status.md), with a first name where the board has a
pronoun for a real person (BLD-E008).

The sharer's own words: the page returns the masked copy of each message. The unmasked copy is in the worker-only
`idea_words_sealed` (DEC-103); its reader belongs to lane C (L-HIDE), and `SEALED_WORDS_HOOK` is where it plugs in.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from typing import Any

from core.db import Conn
from ideapage import read
from ideapage.shape import my_ideas_label, public_idea, safe_back, similar_tiles
from ideapage.track import STATUS_OF_CHOICE, Decided, decided
from ideapage.words import (
    DECISION_LABEL,
    MONTHS,
    PART_LABEL,
    brings_words,
    count,
    countdown,
    day,
    day_time,
    hours_range,
    join_words,
    local,
    money_range,
    pill,
    short_date,
)
from onepc.context import open_text

STATE_LABEL = {
    "just_shared": "Just shared",
    "questions": "Questions from the review desk",
    "answers_sent": "Answers sent",
    "picked": "Picked",
    "not_now": "Not now",
    "not_picked": "Not picked, with the reason",
    "reversed": "Reversed by the Ones Committee",
    "withdrawn": "Withdrawn",
    # NOT DRAWN on the Status board; named for the status they show.
    "being_built": "Being built",
    "shipped": "Shipped",
    "merged": "Merged",
}


def _masked_own_words(conn: Conn, idea_uuid: str) -> list[dict[str, Any]]:
    """The sharer's messages as the masked copy (what the desk and committee read)."""
    out = []
    for m in conn.execute(
        "SELECT id, seq, via, device, lang, text_encrypted, spans, created_at FROM idea_messages "
        "WHERE idea_uuid = %s ORDER BY seq",
        (idea_uuid,),
    ).fetchall():
        out.append(
            {
                "id": str(m["id"]),
                "text": open_text("idea_messages", "text_encrypted", str(m["id"]), m["text_encrypted"]) or "",
                "at": m["created_at"].isoformat(),
                "device": m["device"],
                "via": m["via"],
                **({"lang": m["lang"]} if m["lang"] else {}),
                "files": [],
                "spans": list(m["spans"] or []),
            }
        )
    return out


# Lane C (L-HIDE.rules/4): replace with the worker-only reader of `idea_words_sealed`, which returns the sharer's
# unmasked words for their own messages and nobody else's. Until then the sharer sees the masked copy, and the page
# says so with `own_words_unmasked: false`. Signature: (conn, idea_uuid, owner_user_id, masked messages) -> messages.
SEALED_WORDS_HOOK: Callable[[Conn, str, str, list[dict[str, Any]]], list[dict[str, Any]]] | None = None


def own_words(conn: Conn, idea_uuid: str, owner_user_id: str) -> tuple[list[dict[str, Any]], bool]:
    masked = _masked_own_words(conn, idea_uuid)
    if SEALED_WORDS_HOOK is None:
        return masked, False
    return SEALED_WORDS_HOOK(conn, idea_uuid, owner_user_id, masked), True


def _size(n: int | None) -> str | None:
    if n is None:
        return None
    if n >= 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB"
    return f"{max(1, round(n / 1024))} KB"


FILE_STATE_LABEL = {
    "uploading": "Uploading",
    "checking": "Checking",
    "checked": "Checked",
    "hidden_checked": "Checked, details hidden",
    "personal_data_found": "Personal details found",
    "upload_failed": "Couldn’t upload",
    "too_big": "Too big",
    "locked": "Locked",
    "infected": "Couldn’t be checked",
    "ok": "Checked",
    "unreachable": "Checked",
}
VIEWABLE = ("checked", "hidden_checked", "ok")


def _file(f: dict[str, Any]) -> dict[str, Any]:
    """C-FILE: a tile with its type badge, name, meta line and checked state. `view_url` only once checked
    (non-negotiable 8); it is the masked copy (A-API.files `GET /files/:id/view`, lane C)."""
    state = f["file_state"] or ("checked" if f["state"] == "clean" else "checking")
    name = str(f["name"])
    ext = name.rsplit(".", 1)[-1].upper() if "." in name else (f["kind"] or "").upper()
    mime = str(f["mime"] or "")
    if f["kind"] == "link":
        meta = "Link, inside KFintech" if f["link_scope"] == "internal" else "Link"
    elif f["kind"] == "folder":
        meta = f"Folder, {count(int(f['item_count'] or 0), 'file')}"
    elif mime == "application/pdf" or ext == "PDF":
        meta = ", ".join(
            x for x in ("PDF", count(int(f["pages"]), "page") if f["pages"] else None, _size(f["bytes"])) if x
        )
    elif mime.startswith("image/"):
        meta = ", ".join(x for x in ("Image", _size(f["bytes"])) if x)
    else:
        meta = ", ".join(x for x in (ext, _size(f["bytes"])) if x)
    return {
        "id": str(f["id"]),
        "kind": f["kind"] or "file",
        "name": name,
        "type": ext,
        "size": int(f["bytes"]) if f["bytes"] is not None else None,
        **({"pages": int(f["pages"])} if f["pages"] else {}),
        "state": state,
        "state_label": FILE_STATE_LABEL.get(state, "Checking"),
        "meta": meta,
        **({"hidden_note": f["hidden_note"]} if f["hidden_note"] else {}),
        **({"link_scope": f["link_scope"]} if f["link_scope"] else {}),
        "added_at": f["created_at"].isoformat(),
        **({"view_url": f"/api/files/{f['id']}/view"} if state in VIEWABLE else {}),
    }


def _state(idea: dict[str, Any], qset: dict[str, Any] | None, dec: Decided | None) -> str:
    status = str(idea["status"])
    if status in ("checking", "with_review_desk"):
        if qset and qset["state"] in read.OPEN_SET_STATES:
            return "questions"
        if qset and qset["state"] in read.ANSWERED_SET_STATES:
            return "answers_sent"
        return "just_shared"
    if status in ("picked", "not_now", "not_picked"):
        if dec and dec.reversed and STATUS_OF_CHOICE.get(dec.choice) == status:
            return "reversed"
        return status
    return status if status in STATE_LABEL else "just_shared"


def edit_window(idea: dict[str, Any], qset: dict[str, Any] | None, now: dt.datetime) -> dict[str, Any] | None:
    """L-SUBMIT.edit/1: until the desk opens it, at the latest `edit_closes_at` (3 days after sharing); an open
    question set closes it too (L-SUBMIT.edit/5 via J-TRACK step 3). None once it is past review."""
    if idea["status"] not in ("checking", "with_review_desk"):
        return None
    closes = idea.get("edit_closes_at")
    opened = idea.get("opened_at")
    asked = bool(qset and qset["state"] != "queued")
    is_open = opened is None and not asked and closes is not None and now < closes
    out: dict[str, Any] = {"open": is_open}
    if closes is not None:
        out["closes_at"] = closes.isoformat()
    if opened is not None:
        out["opened_by_desk_at"] = opened.isoformat()
    return out


def may_withdraw(idea: dict[str, Any], qset: dict[str, Any] | None, now: dt.datetime) -> bool:
    w = edit_window(idea, qset, now)
    return bool(w and w["open"])


def _window_words(idea: dict[str, Any], w: dict[str, Any] | None, now: dt.datetime) -> dict[str, Any] | None:
    if w is None:
        return None
    closes = idea.get("edit_closes_at")
    opened = idea.get("opened_at")
    if w["open"] and closes is not None:
        return {
            "open": True,
            "line": (
                f"Open to changes until {day(closes, now)}. Edit or withdraw it any time before the review desk "
                "opens it. We tell you on Teams and by email when anything moves."
            ),
            "countdown": countdown(closes, now),
        }
    if opened is not None:
        line = (
            f"The review desk opened it on {day(opened, now)}, so the idea itself can’t be changed now. "
            "Write to them in the conversation."
        )
    else:  # NOT DRAWN: the three days ran out before the desk opened it
        line = (
            f"The time for changes ended on {day(closes, now) if closes else 'its third day'}, so the idea itself "
            "can’t be changed now. Write to the review desk in the conversation."
        )
    return {"open": False, "line": line}


def _committee(dec: Decided, now: dt.datetime) -> dict[str, str] | None:
    """The committee line under a decision (L-DECIDE.rules/5, L-COMMITTEE.rules/2, /6)."""
    if dec.reversed:
        return None
    if dec.window_state in ("open", "extended") and dec.closes_at is not None:
        return {
            "head": f"The Ones Committee can review this decision until {day(dec.closes_at, now)}.",
            "line": "If they change it, their note comes to your Inbox. After that, it stands.",
            "closes_at": dec.closes_at.isoformat(),
        }
    if dec.window_state == "expired" and dec.closes_at is not None:  # NOT DRAWN on the Status board
        return {
            "head": f"The Ones Committee’s window closed on {day(dec.closes_at, now)}.",
            "line": "The decision stands.",
        }
    return None


def _decision_json(conn: Conn, dec: Decided, idea: dict[str, Any], now: dt.datetime) -> dict[str, Any]:
    """E-ENTITIES `Decision`, with the reason exactly as the reviewer wrote it (L-DECIDE.rules/3)."""
    d = dec.raw
    reviewer = read.person_by_user(conn, d["by_user_id"], "from the review desk")
    first = reviewer["first_name"] if reviewer else "The review desk"
    out: dict[str, Any] = {
        "id": str(d["id"]),
        "idea_id": read.key_of(idea),
        "choice": dec.desk_choice,
        "label": DECISION_LABEL[dec.desk_choice],
        "reason": dec.reason or "",
        "by": read.public_person(reviewer),
        "by_line": f"{first} from the review desk",
        "at": dec.desk_at.isoformat(),
        "reason_from_line": f"{first} from the review desk, {day_time(dec.desk_at, now)}",
        **({"return_at": d["return_at"].isoformat()} if d.get("return_at") else {}),
        **({"team_by": d["team_by"].isoformat()} if d.get("team_by") else {}),
        **({"joined_with": dec.joined_with} if dec.joined_with else {}),
        "window": {
            "state": d.get("window_state") or "open",
            "opens_at": d["opens_at"].isoformat() if d.get("opens_at") else dec.desk_at.isoformat(),
            "closes_at": d["closes_at"].isoformat() if d.get("closes_at") else None,
            "max_closes_at": d["max_closes_at"].isoformat() if d.get("max_closes_at") else None,
            "extended_times": int(d.get("extended_times") or 0),
        },
    }
    committee = _committee(dec, now)
    if committee:
        out["committee"] = committee
    if dec.reversed and dec.reversed_at is not None:
        member = read.person_by_user(conn, dec.reversed_by, "from the Ones Committee")
        name = member["name"] if member else "A member"
        lower = DECISION_LABEL[dec.choice].lower()
        if dec.choice == "not_now" and dec.return_at:
            final = (
                f"This is final. It comes back to the review desk on {day(dec.return_at, now)}, "
                "with your answers and crew."
            )
        elif dec.choice == "pick" and dec.team_by:
            final = f"This is final. The build team is chosen by {day(dec.team_by, now)}."  # NOT DRAWN
        else:
            final = "This is final. The idea closes here."  # NOT DRAWN
        out["reversal"] = {
            "to": dec.choice,
            "note": dec.note or "",
            "by": read.public_person(member),
            "at": dec.reversed_at.isoformat(),
            **({"return_at": dec.return_at.isoformat()} if dec.return_at else {}),
            "from_line": f"{name} from the Ones Committee, {day_time(dec.reversed_at, now)}",
            "headline": f"The Ones Committee changed the decision to {lower}",
            "note_label": "The committee’s note to you",
            "was": f"Was: {DECISION_LABEL[dec.desk_choice]}",
            "was_by": f"by {first} from the review desk, {day(dec.desk_at, now)}",
            "final": final,
        }
    return out


def _questions(
    conn: Conn, idea: dict[str, Any], qset: dict[str, Any] | None, now: dt.datetime
) -> dict[str, Any]:
    """The questions card (C-QCARD) as the sharer sees it: none, waiting (with the countdown), partly answered,
    answered. No answer box here: answers are given only on S-R3 (L-QUESTIONS.answer/1, V-ACC.track/3)."""
    key = read.key_of(idea)
    if qset is None or qset["state"] == "queued":
        return {
            "state": "none",
            "empty_line": (
                "No messages yet. If the review desk has a question, it shows up here and in your Inbox, and we "
                "tell you on Teams."
            ),
        }
    reviewer = read.person_by_user(conn, qset["by_user_id"], "from the review desk")
    first = reviewer["first_name"] if reviewer else "The review desk"
    qs = qset["questions"]
    answered = sum(1 for q in qs if q["answered"])
    state = {
        "sent": "waiting",
        "seen": "waiting",
        "partly_answered": "partly_answered",
        "answered": "answered",
        "closed": "closed",
    }[str(qset["state"])]
    if state == "waiting" and answered:
        state = "partly_answered"
    out: dict[str, Any] = {
        "state": state,
        "set_id": str(qset["id"]),
        "from": read.public_person(reviewer),
        "from_line": f"{first} from the review desk, {day_time(qset['sent_at'], now)}"
        if qset.get("sent_at")
        else None,
        "heading": f"{first} has {count(len(qs), 'question')} for you",
        "items": [
            {
                "n": q["n"],
                "text": q["text"],
                "part": q["part"],
                "part_label": PART_LABEL[q["part"]],
                "answered": q["answered"],
            }
            for q in qs
        ],
        "progress": f"{answered} of {len(qs)} answered",
    }
    if qset.get("due_at") and state in ("waiting", "partly_answered"):
        out.update(
            {
                "due_at": qset["due_at"].isoformat(),
                "deadline_line": f"Answer by {day_time(qset['due_at'], now)}. One at a time, typed or spoken.",
                "countdown": countdown(qset["due_at"], now),
                "overdue": qset["due_at"] <= now,
                "action": {
                    "label": "Answer the questions",
                    "to": f"/ideas/{key}/answer",
                    "accessible_name": f"Answer the questions: {idea['title'] or key}",
                },
            }
        )
    return out


def _card(
    conn: Conn,
    state: str,
    idea: dict[str, Any],
    dec: Decided | None,
    qset: dict[str, Any] | None,
    now: dt.datetime,
) -> dict[str, str]:
    """The sentence that says where it stands and what happens next: its first clause in white, the rest dimmer
    (S-06.layout/2), as each state's panel heading and body on the board."""
    reviewer = read.person_by_user(conn, dec.by_user_id) if dec else None
    first = reviewer["first_name"] if reviewer else "The review desk"
    if state == "just_shared":
        by = day(idea["decide_by"], now) if idea.get("decide_by") else None
        return {
            "lead": f"The review desk will look at it by {by}."
            if by
            else "The review desk will look at it soon.",
            "rest": "We’ll tell you on Teams and by email when anything changes.",
        }
    if state == "questions" and qset:
        asker = read.person_by_user(conn, qset["by_user_id"])
        name = asker["first_name"] if asker else "The review desk"
        n = len(qset["questions"])
        due = f"Answer by {day_time(qset['due_at'], now)}." if qset.get("due_at") else ""
        return {"lead": f"{name} from the review desk has {count(n, 'question')} for you.", "rest": due}
    if state == "answers_sent" and qset:
        asker = read.person_by_user(conn, qset["by_user_id"])
        name = asker["first_name"] if asker else "The review desk"
        by = (
            f"The review desk decides by {day(idea['decide_by'], now)}, and you"
            if idea.get("decide_by")
            else "You"
        )
        return {
            "lead": f"Sent. {name} has your answers.",
            "rest": (
                f"Each answer was added to its part of your idea, under What you shared. {by} hear in your "
                "Inbox, on Teams and by email."
            ),
        }
    if state == "picked" and dec:
        joined = ""
        if dec.joined_with:
            other = conn.execute(
                "SELECT idea_id, city FROM ideas WHERE id = %s", (dec.joined_with,)
            ).fetchone()
            if other and other["idea_id"]:
                where = f" from {other['city']}" if other["city"] else ""
                joined = f" and joined it with {other['idea_id']}{where}, so one team builds one fix"
        team = f" The build team is chosen by {day(dec.team_by, now)}." if dec.team_by else ""
        return {
            "lead": "Picked. A team is being chosen to build it.",
            "rest": f"{first} from the review desk picked it on {day(dec.at, now)}{joined}.{team}",
        }
    if state == "not_now" and dec:
        back = day(dec.return_at, now) if dec.return_at else None
        month = MONTHS[local(dec.return_at).month - 1] if dec.return_at else None
        return {
            "lead": f"Not now. The review desk looks at it again on {back}." if back else "Not now.",
            "rest": (
                "Right problem, wrong time. Your idea stays open, with your answers and anyone who teams up, and "
                f"comes back to the review desk first thing in {month}. {first}’s full reason is below."
                if month
                else f"Your idea stays open, with your answers and anyone who teams up. {first}’s full reason is below."
            ),
        }
    if state == "not_picked" and dec:
        carried = read.live_merge_into(conn, str(idea["id"]))
        if carried and carried.get("lead_ref"):
            return {
                "lead": f"Not picked on its own. Your words carry on in {carried['lead_ref']}.",
                "rest": (
                    "It’s the same problem as an idea the review desk is taking forward. Your words were added to "
                    f"it, with credit to you, and you’ll get its updates. {first}’s full reason is below."
                ),
            }
        return {
            "lead": "Not picked.",
            "rest": f"It won’t go ahead. {first}’s full reason is below.",
        }  # NOT DRAWN
    if state == "reversed" and dec:
        return {
            "lead": f"The Ones Committee changed the decision to {DECISION_LABEL[dec.choice].lower()}.",
            "rest": "",
        }
    if state == "withdrawn":
        reason = open_text(
            "ideas", "withdraw_reason_encrypted", str(idea["id"]), idea.get("withdraw_reason_encrypted")
        )
        said = f"Your reason: “{reason}”." if reason else "No reason given."
        return {
            "lead": "Withdrawn. It’s back in your drafts.",
            "rest": f"Nobody else can see it now. {said} Restoring shares it again as it was, and the review desk gets it back.",
        }
    if state == "being_built":  # NOT DRAWN on the Status board
        team_row = read.build_team(conn, str(idea["id"]))
        return {
            "lead": "Being built.",
            "rest": (f"{team_row['name']} is building it. " if team_row else "")
            + "The build team writes to you in the conversation.",
        }
    if state == "shipped":  # NOT DRAWN on the Status board
        checks = read.promises()["impact"]["check_days"]
        return {
            "lead": "Shipped. It’s live.",
            "rest": f"We measure what changed {join_words([str(d) for d in checks])} days after it shipped.",
        }
    if state == "merged":
        m = read.live_merge_into(conn, str(idea["id"]))
        if m and m.get("lead_ref"):
            return {
                "lead": f"Merged into {m['lead_ref']}.",
                "rest": "Your words carry on there, with credit to you, and you get its updates.",
            }
        return {"lead": "Merged.", "rest": ""}
    return {"lead": "", "rest": ""}


def _merged(conn: Conn, idea: dict[str, Any], now: dt.datetime) -> dict[str, Any] | None:
    """S-06.rules/4: where a merged idea went, by whom, with the note and a link (L-MERGE.effects/1)."""
    if idea["status"] != "merged":
        return None
    m = read.live_merge_into(conn, str(idea["id"]))
    if m is None or not m.get("lead_ref"):
        return None
    if m["via"] == "review_desk":
        by = "by the review desk"
    else:
        lead = read.person_by_code(conn, m.get("lead_code"))
        by = f"by {lead['first_name']}" if lead else "by its lead"
    return {
        "to": m["lead_ref"],
        "title": m.get("lead_title") or "",
        "line": f"Merged into {m['lead_ref']} {by}",
        "note": m.get("note") or "",
        "at": m["at"].isoformat(),
        "link": {"label": f"Open {m['lead_ref']}", "to": f"/ideas/{m['lead_ref']}?from={read.key_of(idea)}"},
    }


def _shared_rows(
    conn: Conn, idea: dict[str, Any], w: dict[str, Any] | None, now: dt.datetime
) -> dict[str, Any]:
    """'What you shared' (S-06.layout/5–7): the short summary and sorting as everyone sees them, the hidden chips,
    the answers under their parts, files, and the fix."""
    uid = str(idea["id"])
    answers = read.answers_by_part(conn, uid)
    asker_names: dict[str, str] = {}

    def under(part: str) -> list[dict[str, Any]]:
        out = []
        for a in answers.get(part, []):
            uid_ = str(a["asked_by"])
            if uid_ not in asker_names:
                p = read.person_by_user(conn, uid_)
                asker_names[uid_] = p["first_name"] if p else "the review desk"
            out.append(
                {
                    "id": a["id"],
                    "text": a["text"],
                    "at": a["at"].isoformat(),
                    "line": f"From your answer to {asker_names[uid_]}, {day(a['at'], now)}",
                }
            )
        return out

    worth = read.worth(conn, uid)
    figures: dict[str, Any] = {}
    for side, w_ in worth.items():
        figures[side] = {
            k: v
            for k, v in {
                "hours": hours_range(w_.get("hours_low"), w_.get("hours_high")),
                "cost": money_range(w_.get("cost_low"), w_.get("cost_high")),
                "revenue": money_range(w_.get("revenue_low"), w_.get("revenue_high")),
            }.items()
            if v
        }
        if side == "reviewer":
            rev = read.person_by_user(conn, w_.get("by_user_id"))
            figures[side]["by_line"] = f"Revised by {rev['first_name'] if rev else 'the review desk'}"
            if w_.get("note"):
                figures[side]["note"] = w_["note"]

    hid = [h for h in read.hidden(conn, uid) if h["state"] == "hidden"]
    chips = [str(h["masked"]) for h in hid]
    add_until = (
        f"Add one until {day(idea['edit_closes_at'], now)}"
        if w and w["open"] and idea.get("edit_closes_at")
        else None
    )
    fix_row = read.fix(conn, uid)
    files = [_file(f) for f in read.files(conn, uid)]
    rows = [
        {
            "part": "summary",
            "label": "The problem",
            "value": idea["summary"] or "",
            "answers": under("summary"),
        },
        {"part": "often", "label": "How often", "value": idea["often"] or "", "answers": under("often")},
        {
            "part": "who",
            "label": "Who it affects",
            "value": join_words(list(idea["affects"] or [])),
            "answers": under("who"),
        },
        {
            "part": "cost",
            "label": "What it’s worth",
            "value": brings_words(list(idea["brings"] or [])),
            "figures": figures,
            "answers": under("cost"),
        },
        {"part": "area", "label": "Area", "value": idea["area"] or ""},
    ]
    return {
        "intro": (
            "If the review desk puts it on the Wall, everyone at KFintech sees this short summary. Your own words "
            "stay with you and the review desk."
        ),
        "rows": rows,
        "hidden": {
            "chips": chips[:2],
            "more": max(0, len(chips) - 2),
            **(
                {
                    "more_label": f"+{len(chips) - 2} more",
                    "more_accessible_name": f"See all {len(chips)} hidden details",
                }
                if len(chips) > 2
                else {}
            ),
            "note": "Hidden from everyone",
            "all": [
                {
                    "masked": str(h["masked"]),
                    "kind": h["kind"],
                    "where": f"In {h['file_name']}" if h["file_name"] else "In your words",
                }
                for h in hid
            ],
        },
        "attached": {
            "label": "Attached",
            "files": files,
            "answers": under("evidence"),
            **(
                {}
                if files
                else {
                    "empty_line": "Nothing attached.",
                    **(
                        {"add": {"label": add_until, "to": f"/ideas/{read.key_of(idea)}/edit"}}
                        if add_until
                        else {}
                    ),
                }
            ),
        },
        "fix": {
            "label": "Your fix",
            **(
                {
                    "text": fix_row["how"] or "",
                    "needs": fix_row.get("needs"),
                    "more_label": "Read the full fix",
                }
                if fix_row
                else {
                    "empty_line": "No fix added.",
                    **(
                        {"add": {"label": add_until, "to": f"/ideas/{read.key_of(idea)}/edit"}}
                        if add_until
                        else {}
                    ),
                }
            ),
            "answers": under("fix"),
        },
    }


def sharer_view(
    conn: Conn,
    idea: dict[str, Any],
    me: read.Viewer,
    now: dt.datetime,
    *,
    came_from: str | None = None,
    back: str | None = None,
) -> dict[str, Any]:
    """Everything S-06 shows, for the sharer only (the caller has checked `me.is_sharer(idea)`)."""
    uid = str(idea["id"])
    key = read.key_of(idea)
    qset = read.question_set(conn, uid)
    dec = decided(read.decision(conn, uid))
    state = _state(idea, qset, dec)
    reviewer = read.person_by_user(conn, qset["by_user_id"]) if qset else None
    carried = read.live_merge_into(conn, uid) if idea["status"] == "not_picked" else None
    base = public_idea(
        conn,
        idea,
        now,
        for_sharer=True,
        dec=dec,
        qset=qset,
        carried_into=carried["lead_ref"] if carried else None,
        reviewer_first=reviewer["first_name"] if reviewer else None,
    )
    w = edit_window(idea, qset, now)
    words, unmasked = own_words(conn, uid, me.user_id)
    desk = read.person_by_user(conn, idea.get("reviewer_id"), "from the review desk")
    decision_json = _decision_json(conn, dec, idea, now) if dec else None
    card = _card(conn, state, idea, dec, qset, now)

    actions: dict[str, Any] = {
        "conversation": {"label": "Open the conversation", "to": f"/ideas/{key}/conversation"},
    }
    if w and w["open"]:
        actions["edit"] = {"label": "Edit it", "to": f"/ideas/{key}/edit"}
        actions["withdraw"] = {
            "label": "Withdraw",
            "op": "withdraw",
            "method": "POST",
            "path": f"/api/ideas/{key}/withdraw",
            "confirm": {
                "heading": "Withdraw this idea?",
                "line": "It goes back to your drafts and nobody else will see it. You can restore it any time.",
                "reason_label": "Why are you withdrawing it?",
                "reason_hint": "Optional",
                "placeholder": "For example, it’s already being fixed",
                "confirm_label": "Withdraw it",
                "cancel_label": "Keep it shared",
            },
            "done": "Withdrawn. It’s back in your drafts.",
        }
    if idea["status"] == "withdrawn":
        actions["restore"] = {
            "label": "Restore it",
            "op": "restore",
            "method": "POST",
            "path": f"/api/ideas/{key}/restore",
            "done": "Restored. It’s shared again, as it was.",
        }
    if state == "questions":
        actions["answer"] = {"label": "Answer the questions", "to": f"/ideas/{key}/answer"}
    if idea["status"] == "picked":
        # A-API.ideas `POST /ideas/:id/join-build`; the write is not built yet (no table holds the ask).
        actions["join_build"] = {
            "label": "Ask to join the build team",
            "op": "join_build",
            "method": "POST",
            "path": f"/api/ideas/{key}/join-build",
        }
    if carried and carried.get("lead_ref"):
        actions["open_other"] = {
            "label": f"Open {carried['lead_ref']}",
            "to": f"/ideas/{carried['lead_ref']}?from={key}",
        }

    if came_from == "share":
        crumb = {"label": "Home", "to": "/home"}  # S-06.rules/6: after first sharing, Back goes Home
    else:
        to = safe_back(back, ("/my-ideas",)) or "/my-ideas"
        crumb = {"label": my_ideas_label(to), "to": to}

    conversation: dict[str, Any] | None = None
    if state != "withdrawn":
        # The short view of the conversation (S-06.layout/8). Its entries are lane F's (L-CONVO); this card
        # carries the count, the line under the heading and the link.
        conversation = {
            "heading": "You and the review desk",
            "count": read.entry_count(conn, uid),
            "link": actions["conversation"],
        }
        if state == "reversed":
            conversation["sub_line"] = (
                "The Ones Committee has the last word on this decision. The full conversation is one tap away."
            )
        elif state in ("picked", "not_now", "not_picked", "being_built", "shipped"):
            conversation["sub_line"] = (
                "The review desk has decided. The full conversation, with every answer, is one tap away."
            )
    skip = {dec.joined_with} if dec and dec.joined_with and idea["status"] == "picked" else set()

    first_arrival = came_from == "share"
    idea_json = {
        **base,
        "own_words": words,
        "hidden": [
            {
                "id": str(h["id"]),
                "kind": h["kind"],
                "masked": h["masked"],
                "state": h["state"],
                **({"reason": h["reason"]} if h["reason"] else {}),
                **({"shown_at": h["shown_at"].isoformat()} if h["shown_at"] else {}),
            }
            for h in read.hidden(conn, uid)
        ],
        "files": [_file(f) for f in read.files(conn, uid)],
        "answers_by_part": {
            part: [
                {"id": a["id"], "text": a["text"], "at": a["at"].isoformat(), "added_to": part} for a in items
            ]
            for part, items in read.answers_by_part(conn, uid).items()
        },
        **({"edit_window": w} if w else {}),
        **(
            {
                "review": {
                    "decide_by": idea["decide_by"].isoformat(),
                    **({"reviewer": read.public_person(desk)} if desk else {}),
                    **({"opened_at": idea["opened_at"].isoformat()} if idea.get("opened_at") else {}),
                }
            }
            if idea.get("decide_by")
            else {}
        ),
        **({"decision": decision_json} if decision_json else {}),
        "kept_separate": bool(idea.get("kept_separate")),
        "next_step": {
            "sentence": card["lead"],
            **(
                {"action": {"label": a["label"], "to": a.get("to") or a.get("path")}}
                if (a := actions.get("answer") or actions.get("restore") or actions.get("open_other"))
                else {}
            ),
        },
    }
    versions = conn.execute("SELECT count(*) AS n FROM idea_versions WHERE idea_uuid = %s", (uid,)).fetchone()
    if versions and versions["n"]:
        idea_json["versions"] = {
            "count": int(versions["n"]) + 1,
            "summary": f"{int(versions['n']) + 1} versions.",
        }

    return {
        "view": "sharer",
        "screen": "S-06",
        "idea": idea_json,
        "page": {
            "state": state,
            "state_label": STATE_LABEL[state],
            "pill": pill(base["status"]),
            "breadcrumb": {**crumb, "current": key},
            "shared_label": f"Shared {short_date(idea['shared_at'])}" if idea["shared_at"] else None,
            **(
                {"share_seconds_label": f"Done in {idea['share_seconds']} seconds"}
                if idea.get("share_seconds") is not None and state == "just_shared"
                else {}
            ),
            "first_arrival": first_arrival,
            "card": card,
            "window": _window_words(idea, w, now),
            "actions": actions,
            "questions": _questions(conn, idea, qset, now),
            "shared": _shared_rows(conn, idea, w, now),
            "conversation": conversation,
            "similar": {
                "heading": "Colleagues on something similar",
                "intro": "Matched when you shared. Team up to ask to join their crew, and bring this idea along if you like.",
                "tiles": similar_tiles(conn, idea, me, skip=skip),
            },
            "merged": _merged(conn, idea, now),
            "own_words_unmasked": unmasked,
        },
    }
