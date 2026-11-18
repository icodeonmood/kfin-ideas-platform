"""The Ones Committee (L-COMMITTEE, S-R4): every desk decision and desk merge in its window, extend, reverse once.

A window's state is worked out on read from its dates (`desk.window`), so a list is right even before the expiry
timer has run; `close_window` is the timer's handler and only records what the dates already say.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any, Literal

from core.db import Conn
from desk import adapters, decide, join_build, promises, when
from desk.store import (
    COMMITTEE,
    READERS,
    Refused,
    actor,
    audit,
    audited,
    has_role,
    is_own,
    now,
    person_by_code,
    person_by_user,
    require_role,
    seal,
    sharers_and_crew,
    unseal,
)
from desk.window import Window, WindowRefused, extend, reverse, words
from onepc.words import REVIEW_DESK, REVIEW_DESK_START

Tab = Literal["window", "reversed", "expired"]
TABS: tuple[Tab, ...] = ("window", "reversed", "expired")
TAB_LABELS = {"window": "In the window", "reversed": "Reversed", "expired": "Expired"}
Sort = Literal["closing", "decided", "area"]
EXPLANATION = (
    "The review desk decides on the committee’s behalf, and the sharer hears at once. For 30 days after, you can "
    "reverse a decision, with a note the sharer reads. Extend a window 30 days at a time, up to 3 months. Then it "
    "expires and the decision stands."
)
# The line under each choice when reversing (S-R4 Reversing; L-DECIDE.options).
REVERSE_LINES = {
    "pick": "Take it forward. A build team is chosen next.",
    "not_now": "Right problem, wrong time. It comes back to the review desk in {months}.",
    "not_picked": "It won’t go ahead.",
}
_DESK_SAID = {
    "pick": "said picked it",
    "not_now": "said not now",
    "not_picked": "didn’t pick it",
}  # S-R4 Reversing

_ROWS = """
SELECT w.id AS window_id, w.state, w.opens_at, w.closes_at, w.max_closes_at, w.extended_times,
       w.decision_id, w.merge_id,
       d.choice, d.reason_encrypted, d.by_user_id AS decided_by, d.return_at,
       m.note_encrypted AS merge_note, m.by_user_id AS merged_by, m.lead_idea_uuid,
       r.id AS reversal_id, r.to_choice, r.note_encrypted AS reversal_note, r.by_user_id AS reversed_by,
       r.at AS reversed_at, r.return_at AS reversed_return_at,
       i.id AS idea_uuid, i.idea_id, i.title, i.area, i.city, i.contributor_code, i.status,
       li.idea_id AS lead_idea_id, li.contributor_code AS lead_code, d.id AS this_decision_id,
       d.joined_with, ji.idea_id AS joined_idea_id, ji.city AS joined_city
FROM decision_windows w
LEFT JOIN idea_decisions d ON d.id = w.decision_id
LEFT JOIN merges m ON m.id = w.merge_id
LEFT JOIN decision_reversals r ON r.window_id = w.id
JOIN ideas i ON i.id = coalesce(d.idea_uuid, m.merged_idea_uuid)
LEFT JOIN ideas li ON li.id = m.lead_idea_uuid
LEFT JOIN ideas ji ON ji.id = d.joined_with
"""


def _window(r: dict[str, Any]) -> Window:
    return Window(
        r["opens_at"], r["closes_at"], r["max_closes_at"], int(r["extended_times"]), r["reversed_at"]
    )


def _months(p: promises.Promises, return_in: str | None) -> str:
    n = p.return_months_for(return_in or p.return_default)
    return f"{n} month{'s' * (n != 1)}"


def _row_json(
    conn: Conn, r: dict[str, Any], user_id: str, at: dt.datetime, p: promises.Promises
) -> dict[str, Any]:
    tz = when.IST
    w = _window(r)
    ww = words(w, at, p, tz)
    sharer = person_by_code(conn, r["contributor_code"])
    is_merge = r["merge_id"] is not None
    desk_person = person_by_user(conn, r["merged_by"] if is_merge else r["decided_by"])
    if is_merge:
        label = "Merged"
        said = unseal(r["merge_note"], "merges", "note_encrypted", str(r["merge_id"]))
        choice = None
    else:
        label = decide.LABELS[str(r["choice"])]
        said = unseal(r["reason_encrypted"], "idea_decisions", "reason_encrypted", str(r["decision_id"]))
        choice = str(r["choice"])
    reversal = None
    if r["reversal_id"] is not None:
        member = person_by_user(conn, r["reversed_by"])
        now_label = decide.LABELS[str(r["to_choice"])] if r["to_choice"] else "Not merged"
        reversed_day = when.day(r["reversed_at"], at, tz)
        reversal = {  # the Reversed row's four lines (S-R4, Committee board)
            "to": r["to_choice"],
            "note": unseal(r["reversal_note"], "decision_reversals", "note_encrypted", str(r["reversal_id"])),
            "by": member.as_json(),
            "at": r["reversed_at"].isoformat(),
            "now_line": f"Now: {now_label}",
            "now_by_line": f"by {member.name}, {reversed_day}",
            "reversed_line": f"Reversed {reversed_day}",
            "final_line": f"Final. {sharer.first_name} has the note.",
        }
    own = _own(conn, user_id, r)
    open_ = ww.state in ("open", "extended")
    return {
        "window_id": str(r["window_id"]),
        "kind": "merge" if is_merge else "decision",
        "idea": {"id": r["idea_id"], "title": r["title"],
                 "meta": f"{r['idea_id']}, {sharer.name}, {r['area'] or ''}, {r['city'] or ''}".rstrip(", ")},
        "sharer": sharer.as_json(),
        "decision": {
            "choice": choice, "label": label, "merged_into": r["lead_idea_id"] if is_merge else None,
            "by_line": f"by {desk_person.first_name} from the review desk, {when.day(r['opens_at'], at, tz)}",
            "reason": said, "reason_heading": f"The review desk’s reason, as {sharer.first_name} read it",
        },
        "window": {
            "state": ww.state, "opens_at": w.opens_at.isoformat(), "closes_at": w.closes_at.isoformat(),
            "max_closes_at": w.max_closes_at.isoformat(), "extended_times": w.extended_times,
            "left": ww.left, "until": ww.until, "extended": ww.extended, "extend_to": ww.extend_to,
            "limit_line": ww.limit_line, "closed_line": ww.closed_line,
            "open_line": (
                f"Open until {when.day(w.closes_at, at, tz)}. You can extend it 30 days at a time, up to "
                f"{ww.max_until}. When it closes, the decision stands."
            ) if open_ else None,
        },
        "reversal": reversal,
        "can_extend": open_ and ww.extend_to is not None,
        "can_reverse": open_ and not own,  # L-COMMITTEE.rules/9: hidden on a member's own idea
        "action": "Review" if open_ else "See it",
        "area": r["area"] or "",
    }  # fmt: skip


def _own(conn: Conn, user_id: str, r: dict[str, Any]) -> bool:
    """L-COMMITTEE.rules/9: a member's own idea. For a desk merge both ideas count: the one that joined and the
    one that leads."""
    if is_own(conn, user_id, {"id": r["idea_uuid"], "contributor_code": r["contributor_code"]}):
        return True
    return r["merge_id"] is not None and is_own(
        conn, user_id, {"id": r["lead_idea_uuid"], "contributor_code": r["lead_code"]}
    )


# A reversal changes a decision that still stands as the desk left it (picked may already be being built).
STILL = {"pick": ("picked", "being_built"), "not_now": ("not_now",), "not_picked": ("not_picked",)}


def _tab(r: dict[str, Any], at: dt.datetime) -> Tab:
    state = _window(r).state(at)
    return "reversed" if state == "reversed" else "expired" if state == "expired" else "window"


def listing(conn: Conn, user_id: str, tab: str = "window", sort: str = "closing", at: dt.datetime | None = None,
            limit: int = 200) -> dict[str, Any]:  # fmt: skip
    """GET /committee (A-API.committee): one tab's rows, every tab's count and the summary sentence."""
    t = at or now()
    p = promises.get()
    require_role(conn, user_id, COMMITTEE)  # the worker checks too, not only the web's page rule
    rows = [dict(r) for r in conn.execute(_ROWS + " ORDER BY w.closes_at").fetchall()]
    by_tab: dict[str, list[dict[str, Any]]] = {k: [] for k in TABS}
    for r in rows:
        by_tab[_tab(r, t)].append(r)
    chosen = by_tab.get(tab if tab in TABS else "window", [])
    if sort == "decided":
        chosen.sort(key=lambda r: r["opens_at"], reverse=True)
    elif sort == "area":
        chosen.sort(key=lambda r: ((r["area"] or "").lower(), r["closes_at"]))
    elif tab == "reversed":
        chosen.sort(key=lambda r: r["reversed_at"], reverse=True)
    month_start = t.astimezone(when.IST).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    mine = conn.execute(
        "SELECT count(*) AS n FROM decision_reversals WHERE by_user_id = %s AND at >= %s",
        (user_id, month_start),
    ).fetchone()
    n_open, n_mine = len(by_tab["window"]), int(mine["n"]) if mine else 0
    summary = f"{n_open} decision{'s' * (n_open != 1)} open to review."
    if n_mine:
        summary += f" You reversed {n_mine} this month."
    return {
        "items": [_row_json(conn, r, user_id, t, p) for r in chosen[:limit]],
        "total": len(chosen),
        "counts": {k: len(v) for k, v in by_tab.items()},
        "summary": summary,
        "explanation": EXPLANATION,
    }


def _load(conn: Conn, window_id: str, *, lock: bool) -> dict[str, Any]:
    try:
        uuid.UUID(window_id)
    except ValueError:
        raise Refused(404, "not_found") from None
    if lock:  # lock the window row itself; the joins only read
        conn.execute("SELECT id FROM decision_windows WHERE id = %s FOR UPDATE", (window_id,))
    row = conn.execute(_ROWS + " WHERE w.id = %s", (window_id,)).fetchone()
    if row is None:
        raise Refused(404, "not_found")
    return dict(row)


def _refuse(exc: WindowRefused) -> Refused:
    messages = {
        "at_limit": "This window is at the 3-month limit.",
        "window_closed": "This window has closed. The decision stands.",
        "already_reversed": "This decision has already been reversed. That was final.",
    }
    return Refused(409, exc.code, messages[exc.code])


def extend_window(conn: Conn, window_id: str, user_id: str, at: dt.datetime | None = None) -> dict[str, Any]:
    """L-COMMITTEE.rules/2: 30 more days, up to 3 months from the decision in all. Errors: at_limit,
    window_closed, already_reversed."""
    t = at or now()
    p = promises.get()
    require_role(conn, user_id, COMMITTEE)
    with audited(conn), conn.transaction():
        r = _load(conn, window_id, lock=True)
        before = _window(r)
        try:
            w = extend(before, t, p)
        except WindowRefused as exc:
            raise _refuse(exc) from None
        conn.execute(
            "UPDATE decision_windows SET closes_at = %s, extended_times = %s, state = 'extended', "
            "last_extended_by = %s WHERE id = %s",
            (w.closes_at, w.extended_times, user_id, window_id),
        )
        adapters.schedule(conn, "committee.window_close", f"window:{window_id}", w.closes_at)
        audit(conn, actor(user_id), "committee.extend", f"window:{window_id}",
              before={"closes_at": before.closes_at.isoformat()},
              after={"closes_at": w.closes_at.isoformat(), "extended_times": w.extended_times})  # fmt: skip
        r.update(closes_at=w.closes_at, extended_times=w.extended_times, state="extended")
        return _row_json(conn, r, user_id, t, p)


def reverse_window(conn: Conn, window_id: str, user_id: str, body: dict[str, Any],
                   at: dt.datetime | None = None) -> dict[str, Any]:  # fmt: skip
    """L-COMMITTEE.rules/3–5: once, final, with a note the sharer reads word for word. A decision takes one of the
    other two choices and all its consequences; a desk merge is undone (L-MERGE.effects/7). Errors: to_required,
    note_too_short, window_closed, already_reversed, own_idea."""
    t = at or now()
    p = promises.get()
    note = str(body.get("note") or "")
    require_role(conn, user_id, COMMITTEE)
    with audited(conn), conn.transaction():
        # lane C's locks on the idea (and a merge's lead), in uuid order, before the window's and the ideas' row
        # locks: the note is hidden below (BLD-B247)
        seen = _load(conn, window_id, lock=False)
        adapters.lock_refs(conn, str(seen["idea_uuid"]), str(seen["lead_idea_uuid"] or seen["idea_uuid"]))
        r = _load(conn, window_id, lock=True)
        locked = sorted({str(r["idea_uuid"]), str(r["lead_idea_uuid"] or r["idea_uuid"])})
        rows = {str(x["id"]): dict(x) for x in conn.execute(
            "SELECT * FROM ideas WHERE id = ANY(%s::uuid[]) ORDER BY id FOR UPDATE", (locked,))}  # fmt: skip
        idea = rows[str(r["idea_uuid"])]
        if _own(conn, user_id, r):
            raise Refused(
                403, "own_idea", "This is your own idea. Another member takes it.",
                audit=(actor(user_id), "committee.own_idea_refused", f"window:{window_id}", {}),
            )  # fmt: skip
        is_merge = r["merge_id"] is not None
        to = None if is_merge else body.get("to")
        return_in = body.get("return_in") if to == "not_now" else None
        if not is_merge:
            errors = decide.check_reversal(to, str(r["choice"]), note, return_in, p)
        else:
            errors = decide.check_reversal("pick", "not_picked", note, None, p)  # a merge needs only the note
        if errors:
            e = errors[0]
            raise Refused(422, e.code, e.message, e.field)
        try:
            w = reverse(_window(r), t)
        except WindowRefused as exc:
            raise _refuse(exc) from None
        # The window may still be open while the idea has moved on: a Not now that came back and was decided again,
        # a merge already undone. Then this decision no longer stands as the desk left it, and it is not reversed.
        latest = conn.execute(
            "SELECT id FROM idea_decisions WHERE idea_uuid = %s ORDER BY at DESC LIMIT 1", (r["idea_uuid"],)
        ).fetchone()
        overtaken = (
            (idea["status"] != "merged" or str(idea["merged_into"]) != str(r["lead_idea_uuid"]))
            if is_merge
            else (latest is None or str(latest["id"]) != str(r["this_decision_id"])
                  or idea["status"] not in STILL[str(r["choice"])])
        )  # fmt: skip
        if overtaken:
            raise Refused(
                409, "window_closed", "A newer decision has replaced this one. There is nothing to reverse."
            )
        masked, _ = adapters.hide(conn, str(r["idea_uuid"]), note.strip(), by=user_id)
        reversal_id = str(uuid.uuid4())
        return_at = decide.return_at(t, return_in or p.return_default, p) if to == "not_now" else None
        conn.execute(
            "INSERT INTO decision_reversals (id, window_id, to_choice, note_encrypted, by_user_id, at, return_in, "
            "return_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (reversal_id, window_id, to, seal(masked, "decision_reversals", "note_encrypted", reversal_id), user_id,
             t, (return_in or p.return_default) if to == "not_now" else None, return_at),
        )  # fmt: skip
        conn.execute("UPDATE decision_windows SET state = 'reversed' WHERE id = %s", (window_id,))
        desk_user = r["merged_by"] if is_merge else r["decided_by"]
        if is_merge:
            from desk import merging  # the merge's own effects (L-MERGE.effects/7)

            merging.reverse_merge(conn, str(r["merge_id"]), user_id, masked, t)
        else:
            conn.execute(
                "UPDATE ideas SET status = %s WHERE id = %s", (decide.STATUS_AFTER[str(to)], r["idea_uuid"])
            )
            adapters.say(conn, str(r["idea_uuid"]), "committee.reversed", author_user_id=user_id,
                         payload={"window_id": window_id, "to": str(to)}, at=t)  # fmt: skip
            # L-INBOX.kinds: a reversal goes to the sharer, the crew and the reviewer, each once
            told = list(dict.fromkeys([*sharers_and_crew(conn, idea), str(desk_user)]))
            adapters.tell(
                conn, "decision_reversed", told, idea_uuid=str(r["idea_uuid"]), sender=user_id,
                actions=[("Read the note", f"/ideas/{r['idea_id']}", "primary")],  # L-INBOX.kinds
                refs={"window_id": window_id, "to": str(to)},
            )  # fmt: skip
            if return_at:
                adapters.schedule(conn, "desk.not_now_return", f"idea:{r['idea_uuid']}", return_at)
        audit(conn, actor(user_id), "committee.reverse", f"window:{window_id}",
              before={"choice": r["choice"], "kind": "merge" if is_merge else "decision"},
              after={"to": to, "reversal_id": reversal_id})  # fmt: skip
        r.update(reversal_id=reversal_id, to_choice=to, reversal_note=seal(masked, "decision_reversals",
                 "note_encrypted", reversal_id), reversed_by=user_id, reversed_at=w.reversed_at, state="reversed")  # fmt: skip
        return _row_json(conn, r, user_id, t, p)


def reversing_words(
    conn: Conn, window_id: str, user_id: str, at: dt.datetime | None = None
) -> dict[str, Any]:
    """S-R4 Reversing: the form's words for this decision (the two other choices, each with its line). For the
    committee only."""
    t = at or now()
    p = promises.get()
    require_role(conn, user_id, COMMITTEE)
    r = _load(conn, window_id, lock=False)
    sharer = person_by_code(conn, r["contributor_code"])
    desk_person = person_by_user(conn, r["merged_by"] or r["decided_by"])
    if r["merge_id"] is not None:
        intro = (f"On “{r['title']}”. The review desk merged it into {r['lead_idea_id']}. {sharer.first_name} reads "
                 f"your note at once, and {desk_person.first_name} from the review desk sees it too.")  # fmt: skip
        options: list[dict[str, str]] = []
    else:
        choice = str(r["choice"])
        intro = (f"On “{r['title']}”. The review desk {_DESK_SAID[choice]}. {sharer.first_name} reads your note at "
                 f"once, and {desk_person.first_name} from the review desk sees it too.")  # fmt: skip
        options = [
            {"to": c, "label": decide.LABELS[c], "line": REVERSE_LINES[c].format(months=_months(p, None))}
            for c in decide.CHOICES if c != choice
        ]  # fmt: skip
    _ = t
    return {
        "title": "Reverse the decision", "intro": intro, "options": options,
        "note_label": f"Your note to {sharer.first_name}", "note_help": f"{sharer.first_name} reads this word for word.",
        "final_line": "This is final. The review desk’s decision stays on record, next to yours.",
        "send_label": f"Reverse and tell {sharer.first_name}",
    }  # fmt: skip


def close_window(conn: Conn, window_id: str, at: dt.datetime | None = None) -> bool:
    """Timer handler (L-COMMITTEE.rules/6): a window that reached its end with nothing done is recorded as
    expired. The decision stands; nothing else changes. Screens already show it from the dates."""
    t = at or now()
    with conn.transaction():
        row = conn.execute(
            "SELECT state, closes_at FROM decision_windows WHERE id = %s FOR UPDATE", (window_id,)
        ).fetchone()
        if row is None or row["state"] not in ("open", "extended") or row["closes_at"] > t:
            return False
        conn.execute("UPDATE decision_windows SET state = 'expired' WHERE id = %s", (window_id,))
        return True


def _lower(label: str) -> str:
    """'Not now' as it sits inside a sentence: 'not now'."""
    return label[:1].lower() + label[1:]


def sharer_lines(
    conn: Conn, r: dict[str, Any], at: dt.datetime, p: promises.Promises, *, joined_side: bool = False
) -> dict[str, Any]:
    """The sharer's words for a decision (reference/copy/Status.md; A-API.conventions/6): the Picked card's joined
    line when the Pick joined a similar idea (L-MERGE.desk/5), the committee line while the window is open
    (L-DECIDE.rules/5), and the committee's card once it reversed the decision (L-COMMITTEE.rules/5,
    V-ACC.committee/4). `joined_side`: the reader's idea is the one the Pick joined, so the line names the lead.
    DEC-111: the sharer and the crew read the review desk, never the reviewer's name ("Meera from the review desk
    picked it on …" on the board); the committee member who reversed it is still named."""
    tz = when.IST
    w = _window(r)
    open_ = w.is_open(at)
    joined_line = None
    if r["choice"] == "pick" and r["joined_with"] is not None:
        ref, city = (r["idea_id"], r["city"]) if joined_side else (r["joined_idea_id"], r["joined_city"])
        joined_line = (
            f"{REVIEW_DESK_START} picked it on {when.day(r['opens_at'], at, tz)} and joined it with "
            f"{ref}{f' from {city}' if city else ''}, so one team builds one fix."
        )
    lines: dict[str, Any] = {
        "joined_line": joined_line,
        "committee_line": (
            f"The Ones Committee can review this decision until {when.day(w.closes_at, at, tz)}. If they change it, "
            "their note comes to your Inbox. After that, it stands."
        ) if open_ else None,
        "reversal": None,
    }  # fmt: skip
    if r["reversal_id"] is not None and r["to_choice"]:
        member = person_by_user(conn, r["reversed_by"])
        was, now_label = decide.LABELS[str(r["choice"])], decide.LABELS[str(r["to_choice"])]
        final = "This is final."
        if r["to_choice"] == "not_now" and r["reversed_return_at"]:
            final += (f" It comes back to the review desk on {when.day(r['reversed_return_at'], at, tz)}, with your "
                      "answers and crew.")  # fmt: skip
        lines["reversal"] = {
            "from_line": f"{member.name} from the Ones Committee, {when.day_time(r['reversed_at'], at, tz)}",
            "title": f"The Ones Committee changed the decision to {_lower(now_label)}",
            "note_heading": "The committee’s note to you",
            "was_line": f"Was: {was}",
            "was_by_line": f"by {REVIEW_DESK}, {when.day(r['opens_at'], at, tz)}",
            "final_line": final,
            "track_line": f"{was}, then moved to {_lower(now_label)} by the Ones Committee",
        }  # fmt: skip
    return lines


def reviewer_lines(
    conn: Conn, r: dict[str, Any], at: dt.datetime, p: promises.Promises, viewer_id: str | None = None
) -> dict[str, Any]:
    """The reviewer's words for a decision (S-R2 Decided, reference/copy/DeskIdea.md): who has it, the reason as
    the sharer reads it, and the committee's window from the desk's side. "Your reason" only for the reviewer who
    decided; any other reader (another reviewer, the committee) reads the review desk's reason and who sent it."""
    tz = when.IST
    w = _window(r)
    ww = words(w, at, p, tz)
    first = person_by_code(conn, r["contributor_code"]).first_name
    sent_day = when.which_day(r["opens_at"], at, tz)
    sent_at = f"{sent_day[:1].upper()}{sent_day[1:]}, {when.clock(r['opens_at'], tz)}."
    if viewer_id is not None and str(viewer_id) == str(r["decided_by"]):
        sent_line, reason_heading = f"{sent_at} {first} has it now.", f"Your reason, as {first} reads it"
    else:
        desk_first = person_by_user(conn, r["decided_by"]).first_name
        sent_line, reason_heading = (
            f"{sent_at} {desk_first} sent it.",
            f"The review desk’s reason, as {first} read it",
        )
    # at the 3-month limit the committee cannot extend it again (L-COMMITTEE.rules/2)
    extend = (
        f"The committee can extend it, up to {p.window_max_months} months in all, to {ww.max_until}."
        if ww.extend_to is not None
        else f"{ww.limit_line}."
    )
    window_state = {
        "open": f"Open, {ww.left}", "extended": f"{ww.extended}, {ww.left}",
        "reversed": f"Reversed {when.day(r['reversed_at'], at, tz)}" if r["reversed_at"] else "Reversed",
        "expired": ww.closed_line,
    }[ww.state]  # fmt: skip
    return {
        "title": f"Decision sent to {first}",
        "sent_line": sent_line,
        "reason_heading": reason_heading,
        "committee_heading": "Ones Committee review",
        "window_state": window_state,
        "window_line": (
            f"Open until {when.day(w.closes_at, at, tz)}. {extend} If they reverse it, {first} gets their note "
            "and you see it here. When the window closes, the decision stands."
        ) if w.is_open(at) else None,
    }  # fmt: skip


def for_idea(
    conn: Conn,
    idea_uuid: str,
    viewer_id: str,
    at: dt.datetime | None = None,
    *,
    lines: Literal["sharer", "reviewer"] | None = None,
    joined_side: bool = False,
) -> dict[str, Any] | None:
    """The latest decision on an idea with its window and any reversal, for the reviewer's page (S-R2 Decided)
    and the sharer's (S-06). None when the desk has not decided. `lines` adds that viewer's words under `lines`
    (`sharer_lines`, `reviewer_lines`); the rest of the row keeps the committee's (S-R4), except that the sharer's
    names the review desk, not the reviewer, and has no reason heading (DEC-111). `joined_side`: read from the idea
    the Pick joined (`decision_for_viewer`)."""
    t = at or now()
    p = promises.get()
    r = conn.execute(_ROWS + " WHERE d.idea_uuid = %s ORDER BY d.at DESC LIMIT 1", (idea_uuid,)).fetchone()
    if r is None:
        return None
    row = dict(r)
    out = _row_json(conn, row, viewer_id, t, p)
    out["decided_at"] = r["opens_at"].isoformat()
    out["return_at"] = (r["reversed_return_at"] or r["return_at"]).isoformat() if (
        r["reversed_return_at"] or r["return_at"]) else None  # fmt: skip
    if lines == "sharer":
        out["lines"] = sharer_lines(conn, row, t, p, joined_side=joined_side)
        # DEC-111: the sharer and the crew read the review desk, never the reviewer, in the row's words too; Status.md
        # draws no heading over the reason ("The review desk’s reason, as Kavya read it" is the committee's, S-R4)
        out["decision"]["by_line"] = f"by {REVIEW_DESK}, {when.day(row['opens_at'], t, when.IST)}"
        out["decision"]["reason_heading"] = None
    elif lines == "reviewer":
        out["lines"] = reviewer_lines(conn, row, t, p, viewer_id)
    return out


def _joined_into(conn: Conn, idea: dict[str, Any]) -> dict[str, Any] | None:
    """The lead idea, when a Pick on it joined this one (L-MERGE.desk/5): the merged idea has no decision of its own,
    and its sharer's page reads the lead's Pick, whose reason was the note to both (BLD-B239). A desk merge made
    without a Pick has none: its page shows the merge."""
    if idea["status"] != "merged" or idea["merged_into"] is None:
        return None
    row = conn.execute(
        "SELECT li.* FROM ideas li WHERE li.id = %s AND EXISTS (SELECT 1 FROM idea_decisions d "
        "WHERE d.idea_uuid = li.id AND d.joined_with = %s)",
        (idea["merged_into"], idea["id"]),
    ).fetchone()
    return dict(row) if row is not None else None


def may_read_decision(conn: Conn, viewer_id: str, idea: dict[str, Any]) -> bool:
    """P-PRODUCT.privacy: the decision and its reason are for the sharer, the crew, the review desk and the
    committee. Everyone else sees the stage only."""
    if is_own(conn, viewer_id, idea):
        return True
    if has_role(conn, viewer_id, READERS):
        return True
    return _on_crew(conn, viewer_id, idea)


def _on_crew(conn: Conn, viewer_id: str, idea: dict[str, Any]) -> bool:
    try:
        uuid.UUID(str(viewer_id))
    except ValueError:
        return False
    return (
        conn.execute(
            "SELECT 1 FROM crew_members c JOIN contributor_map m ON m.contributor_code = c.contributor_code "
            "WHERE c.idea_uuid = %s AND m.user_id = %s AND c.left_at IS NULL LIMIT 1",
            (idea["id"], viewer_id),
        ).fetchone()
        is not None
    )


def decision_for_viewer(
    conn: Conn, ref: str, viewer_id: str, at: dt.datetime | None = None
) -> dict[str, Any] | None:
    """GET /ideas/:id/decision: the full decision for those P-PRODUCT.privacy allows; for anyone else only what the
    stage track already shows (the outcome's label), never the reason or who decided. On an idea a Pick joined
    (status merged), the lead's Pick, with `joined_into` naming the lead."""
    from desk.store import load_idea

    idea = load_idea(conn, ref)
    sharer_side = is_own(conn, viewer_id, idea) or _on_crew(conn, viewer_id, idea)
    lead = _joined_into(conn, idea)  # who may read it is still decided on this idea, below
    full = for_idea(conn, str((lead or idea)["id"]), viewer_id, at, lines="sharer" if sharer_side else None,
                    joined_side=lead is not None)  # fmt: skip
    if full is not None:
        full["joined_into"] = lead["idea_id"] if lead is not None else None
        # Ask to join the build team (L-DECIDE.rules/6, DEC-111): for the sharer and the crew only, on the idea whose
        # Pick this is (the lead, on an idea a Pick joined); None for anyone else, the desk and committee included
        full["join_build"] = join_build.join_build_for(conn, str((lead or idea)["id"]), viewer_id)
    if full is not None and not sharer_side:
        full["lines"] = None  # the desk and the committee read the committee's words (S-R2, S-R4)
    if full is None or may_read_decision(conn, viewer_id, idea):
        return full
    return {
        "stage_only": True,
        "decision": {"choice": full["decision"]["choice"], "label": full["decision"]["label"]},
    }
