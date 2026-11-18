"""S-06, the sharer's own idea page: where it is, what happens next and by when, and what they can do now.

States are named as S-06.states names them ("Just shared", "Questions from the review desk", "Answers sent",
"Picked", "Not now", "Not picked, with the reason", "Reversed by the Ones Committee", "Withdrawn"); the statuses
the board does not draw on this page (being built, shipped, merged) follow the same pattern and are marked
NOT DRAWN in the words. Copy is the board's (reference/copy/Status.md), with a first name where the board has a
pronoun for a real person (BLD-E008).

Lane B owns the review side of this page (J-TRACK, J-COMMITTEE): the questions card (`GET /ideas/:id/question-set`,
`QuestionsCard`), and the decision with its reason word for word, the committee's window and any reversal
(`GET /ideas/:id/decision`). This page does not build those: it says which of the two a state's card sentence is
composed from (`page.card_from`) and whether a question set is open (`has_open_questions`). Answers under their
parts come from lane B's `desk.asking.answers_by_part` through `ideapage.adapters`.

The sharer's own words: the page returns the masked copy of each message. The unmasked copy is in the worker-only
`idea_words_sealed` (DEC-103); its reader belongs to lane C (L-HIDE), and `SEALED_WORDS_HOOK` is where it plugs in.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from typing import Any

from core.db import Conn
from ideapage import adapters, read
from ideapage.shape import at_desk, my_ideas_label, public_idea, safe_back, similar_tiles
from ideapage.track import STATUS_OF_CHOICE, Decided, decided
from ideapage.words import (
    brings_words,
    count,
    countdown,
    day,
    hours_range,
    join_words,
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


# A state whose card sentence names the decision or the questions is composed by the screen from lane B's
# endpoint: the decision (`GET /ideas/:id/decision`) or the open set (`GET /ideas/:id/question-set`).
CARD_FROM = {
    "questions": "question_set",
    "picked": "decision",
    "not_now": "decision",
    "not_picked": "decision",
    "reversed": "decision",
}


def _state(idea: dict[str, Any], qset: dict[str, Any] | None, dec: Decided | None) -> str:
    status = str(idea["status"])
    if at_desk(idea):
        # J-TRACK.steps/4-5: once answers are sent the page says so ("Answers sent"), also when a question was
        # skipped and stays open until the deadline; the questions card then sits under the sentence for the rest
        # (C-QCARD.states "Partly answered", BLD-E051).
        if qset and qset["state"] in (*read.ANSWERED_SET_STATES, read.PARTLY_ANSWERED):
            return "answers_sent"
        if status == "needs_you" or read.has_open_questions(qset):
            return "questions"
        return "just_shared"
    if status in ("picked", "not_now", "not_picked"):
        if dec and dec.reversed and STATUS_OF_CHOICE.get(dec.choice) == status:
            return "reversed"
        return status
    return status if status in STATE_LABEL else "just_shared"


def edit_window(idea: dict[str, Any], qset: dict[str, Any] | None, now: dt.datetime) -> dict[str, Any] | None:
    """L-SUBMIT.edit/1: until the desk opens it, at the latest `edit_closes_at` (3 days after sharing); a question
    set sent closes it too (L-SUBMIT.edit/5, J-TRACK step 3). None once it is past review."""
    if not at_desk(idea):
        return None
    closes = idea.get("edit_closes_at")
    opened = idea.get("opened_at")
    asked = idea["status"] == "needs_you" or bool(qset and qset["state"] != "queued")
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
    """The window line under the track (S-06.layout/4), with its countdown while it is open."""
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
            # PhoneStatus.md says it shorter
            "phone_line": (
                f"Open to changes until {day(closes, now)}. Edit or withdraw it before the review desk opens it."
            ),
            "countdown": countdown(closes, now),
        }
    if opened is not None:
        line = (
            f"The review desk opened it on {day(opened, now)}, so the idea itself can’t be changed now. "
            "Write to them in the conversation."
        )
    else:  # NOT DRAWN: the three days ran out, or questions came, before the desk opened it
        line = (
            "The idea itself can’t be changed now. Write to the review desk in the conversation."
            if closes is None or now < closes
            else f"The time for changes ended on {day(closes, now)}, so the idea itself can’t be changed now. "
            "Write to the review desk in the conversation."
        )
    return {"open": False, "line": line}


def _card(
    conn: Conn,
    state: str,
    idea: dict[str, Any],
    qset: dict[str, Any] | None,
    now: dt.datetime,
) -> dict[str, str] | None:
    """The sentence that says where it stands and what happens next: its first clause in white, the rest dimmer
    (S-06.layout/2). None for a state in CARD_FROM: the screen composes it from lane B's endpoint."""
    if state in CARD_FROM:
        return None
    if state == "just_shared":
        by = day(idea["decide_by"], now) if idea.get("decide_by") else None
        return {
            "lead": f"The review desk will look at it by {by}."
            if by
            else "The review desk will look at it soon.",
            "rest": "We’ll tell you on Teams and by email when anything changes.",
            "phone_rest": "We’ll tell you on Teams and by email.",  # PhoneStatus.md
        }
    if state == "answers_sent":
        asker = read.person_by_user(conn, qset["by_user_id"]) if qset else None
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
        # The card says where it went and by whom, once (S-06.rules/4); the merged block under it carries the note
        # and the link, not the line again.
        m = _merged(conn, idea, now)
        if m:
            return {
                "lead": f"{m['line']}.",
                "rest": "Your words carry on there, with credit to you, and you get its updates.",
            }
        return {"lead": "Merged.", "rest": ""}
    return None


def _answers_under(raw: dict[str, list[dict[str, Any]]], part: str, now: dt.datetime) -> list[dict[str, Any]]:
    """Sent answers under their part (L-QUESTIONS.answer/5), from lane B's reader: the answer and the line
    "From your answer to Meera, Monday 16 November". Questions not answered are the questions card's, not here."""
    out = []
    for a in raw.get(part, []):
        if not a.get("answer"):
            continue
        at = dt.datetime.fromisoformat(str(a["answered_at"])) if a.get("answered_at") else None
        who = a.get("asked_by") or "the review desk"
        out.append(
            {
                "id": str(a.get("question_id") or ""),
                "text": str(a["answer"]),
                **({"at": at.isoformat()} if at else {}),
                "line": f"From your answer to {who}, {day(at, now)}" if at else f"From your answer to {who}",
                "files": list(a.get("files") or []),
            }
        )
    return out


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
        # The lead's name only when they show it on the Wall (DEC-104), as the colleague's page does.
        lead = read.person_by_code(conn, m.get("lead_code"))
        by = f"by {lead['first_name']}" if lead and read.shows_name(lead) else "by its lead"
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
    answers = adapters.answers_by_part(conn, uid)

    def under(part: str) -> list[dict[str, Any]]:
        return _answers_under(answers, part, now)

    worth = read.worth(conn, uid)
    figures: dict[str, Any] = {}
    for side, w_ in worth.items():
        figures[side] = {
            k: v
            for k, v in {
                # "About" only before a figure the sharer marked as approximate (L-WORTH/1); NULL reads as not
                "hours": hours_range(w_.get("hours_low"), w_.get("hours_high"), w_.get("hours_about")),
                "cost": money_range(w_.get("cost_low"), w_.get("cost_high"), w_.get("cost_about")),
                "revenue": money_range(
                    w_.get("revenue_low"), w_.get("revenue_high"), w_.get("revenue_about")
                ),
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
    """Everything S-06 shows that lane B's endpoints do not, for the sharer only (the caller has checked
    `me.is_sharer(idea)`)."""
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
    card = _card(conn, state, idea, qset, now)
    # A set partly answered is still open: its card sits under "Sent." for the questions left (BLD-E051)
    open_questions = state == "questions" or (state == "answers_sent" and read.has_open_questions(qset))

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
    if carried and carried.get("lead_ref"):
        actions["open_other"] = {
            "label": f"Open {carried['lead_ref']}",
            "to": f"/ideas/{carried['lead_ref']}?from={key}",
        }

    if came_from == "share":
        crumb = {"label": "Home", "to": "/home"}  # S-06.rules/6: after first sharing, Back goes Home
    elif came_from == "wall":
        # From the Wall, Back returns to the Wall's own view (J-BROWSE/5, P-ROUTES.state)
        crumb = {"label": "Wall", "to": safe_back(back, ("/wall",)) or "/wall"}
    else:
        to = safe_back(back, ("/my-ideas",)) or "/my-ideas"
        crumb = {"label": my_ideas_label(to), "to": to}

    conversation: dict[str, Any] | None = None
    if state != "withdrawn":
        # The short view of the conversation (S-06.layout/8). Its entries are lane F's (L-CONVO) and the questions
        # card in it is lane B's (C-QCARD); this card carries the count, the empty line and the link.
        n_entries = read.entry_count(conn, uid)
        conversation = {
            "heading": "You and the review desk",
            "count": n_entries,
            "link": actions["conversation"],
        }
        if n_entries == 0 and qset is None:
            conversation["empty_line"] = (
                "No messages yet. If the review desk has a question, it shows up here and in your Inbox, and we "
                "tell you on Teams."
            )
            conversation["phone_empty_line"] = (  # PhoneStatus.md
                "No messages yet. If the review desk has a question, it shows up here and in your Inbox."
            )
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
        "has_open_questions": open_questions,
        "kept_separate": bool(idea.get("kept_separate")),
        **(
            {
                "next_step": {
                    "sentence": card["lead"],
                    **(
                        {"action": {"label": a["label"], "to": a.get("to") or a.get("path")}}
                        if (a := actions.get("restore") or actions.get("open_other"))
                        else {}
                    ),
                }
            }
            if card
            else {}
        ),
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
            # The phone's line under the title (PhoneStatus.md): "Reference IDEA-…, shared Saturday 14 November,
            # Investor service"
            **(
                {
                    "reference_line": ", ".join(
                        x
                        for x in (f"Reference {key}", f"shared {day(idea['shared_at'], now)}", idea["area"])
                        if x
                    )
                }
                if idea["shared_at"] and idea["idea_id"]
                else {}
            ),
            **(
                {"share_seconds_label": f"Done in {idea['share_seconds']} seconds"}
                if idea.get("share_seconds") is not None and first_arrival
                else {}
            ),
            "first_arrival": first_arrival,
            "card": card,
            **({"card_from": CARD_FROM[state]} if state in CARD_FROM else {}),
            "window": _window_words(idea, w, now),
            "actions": actions,
            "lane_b": {
                "question_set": f"/api/ideas/{key}/question-set",
                "decision": f"/api/ideas/{key}/decision",
            },
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
