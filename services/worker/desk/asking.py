"""Questions from the review desk, and the sharer's answers, against the database (L-QUESTIONS, A-API.questions,
E-ENTITIES.review `QuestionSet`, S-R3, C-QCARD).

The rules that need no database (parts, checks, states, the words) are in `desk.questions`; the clocks are in
`desk.clock`. This module stores and moves a set:

- the reviewer: `suggested`, `send_set`, `give_more_time`, `remind`; and `remind_due`, the reminder timer's handler;
- the sharer: `open_set_for_sharer`, `save_answer`, `send_answers`;
- the reads: `facts` (the desk queue's Questions column) and `answers_by_part` (the sharer's idea page, S-06).

Questions and answers are stored as the masked copy, encrypted per row (`questions.text_encrypted`,
`answers.text_encrypted`). Audit entries and conversation payloads carry IDs and enums only (non-negotiable 3).

DEC-111: what the sharer reads never names the reviewer. The sharer's set has no `by`, and its lines (the send
button, "Sent to …", "… decides by …", who asked under each part) name the review desk. The desk's reads keep the name.
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Sequence
from typing import Any

from core.db import Conn
from core.logging import get_logger
from desk import adapters, clock, promises, questions, review, when
from desk.decide import FieldError
from desk.questions import PART_NAMES, PARTS, SetFacts
from desk.store import (
    CUSTOMER_DETAIL,
    DESK_SEES,
    FILES_CHECKED,
    Person,
    Refused,
    actor,
    audit,
    audited,
    code_of,
    load_idea,
    now,
    own_codes,
    person_by_code,
    person_by_user,
    refuse_own,
    seal,
    unseal,
    user_of,
)
from hide import HideError
from onepc.words import REVIEW_DESK, REVIEW_DESK_START

log = get_logger("desk.asking")

OPEN: tuple[str, ...] = ("sent", "seen", "partly_answered")  # a set the sharer can still answer
CLOSED = "The review desk has decided, so these questions are closed."
NOTHING_ANSWERED = "Answer at least one question"
ANSWER_IN_PROGRESS = (
    "Someone else who shared this idea is answering this question. You can answer the others."
)
FILE_CANT_BE_ADDED = "That file can’t be added to this answer."
NOT_SAVED = "Couldn’t save that. Try again."  # S-R3's failure line (lib/desk/answers.ts SAVE_FAILED)
NOT_SENT = "Your answers didn’t send. Try again."  # S-R3's send failure line (answer-view.tsx)
REMINDER_KIND = "desk.answer_reminder"


def _iso(t: dt.datetime | None) -> str | None:
    return t.isoformat() if t else None


def _uuid(value: str) -> str:
    """A set, question or answer id from the URL; anything that is not a uuid is simply not found."""
    try:
        return str(uuid.UUID(str(value)))
    except ValueError:
        raise Refused(404, "not_found") from None


def _refused(e: FieldError) -> Refused:
    return Refused(422, e.code, e.message, e.field)


def _answer_action(idea: dict[str, Any]) -> tuple[str, str, str]:
    return ("Answer the questions", f"/ideas/{idea['idea_id']}/answer", "primary")


def _sharers(conn: Conn, idea: dict[str, Any]) -> list[str]:
    """The sharer, and the sharers of ideas merged into this one (all credited, all may answer)."""
    return [u for c in sorted(own_codes(conn, idea)) if (u := user_of(conn, c))]


def _sharer_code(conn: Conn, idea: dict[str, Any], user_id: str) -> str:
    """The acting person's contributor code if they are a sharer of this idea; to anyone else it does not exist."""
    code = code_of(conn, user_id)
    if code is None or code not in own_codes(conn, idea):
        raise Refused(404, "not_found")
    return code


def _load_set(conn: Conn, set_id: str, *, lock: bool = False) -> dict[str, Any]:
    row = conn.execute(
        f"SELECT * FROM question_sets WHERE id = %s{' FOR UPDATE' if lock else ''}",  # noqa: S608 (fixed text)
        (set_id,),
    ).fetchone()
    if row is None:
        raise Refused(404, "not_found")
    return dict(row)


def _ensure_open(s: dict[str, Any]) -> None:
    """The reviewer's actions on a set (more time, a reminder) need one the sharer can still answer."""
    if s["state"] == "closed":
        raise Refused(409, "set_closed", CLOSED)
    if s["state"] == "answered":
        raise Refused(409, "set_answered", "All the questions are answered.")
    if s["state"] not in OPEN:
        raise Refused(404, "not_found")  # queued: never sent


def _reviewer_set(
    conn: Conn, set_id: str, user_id: str, action: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """The idea (locked first, as everywhere on the desk) and the set (locked), for a reviewer's action."""
    first = _load_set(conn, set_id)
    idea = load_idea(conn, str(first["idea_uuid"]), lock=True)
    refuse_own(conn, user_id, idea, action)
    s = _load_set(conn, set_id, lock=True)
    _ensure_open(s)
    return idea, s


def _schedule_reminders(
    conn: Conn, set_id: str, start: dt.datetime, due: dt.datetime, p: promises.Promises
) -> None:
    for t in clock.reminders(start, due, p):
        adapters.schedule(conn, REMINDER_KIND, f"question_set:{set_id}", t, {"set_id": set_id})


def _working_day_after(due: dt.datetime, p: promises.Promises, cal: clock.Calendar) -> dt.datetime:
    """The deadline hour on the first working day after the answer deadline (the reviewer's moved date)."""
    day = due.astimezone(cal.tz).date() + dt.timedelta(days=1)
    while not cal.working(day):
        day += dt.timedelta(days=1)
    return cal.at(day, p.deadline_hour)


def _countdown(due: dt.datetime, t: dt.datetime, suffix: str, tz: dt.tzinfo) -> dict[str, str]:
    c = clock.countdown(due, t, tz)
    return {"label": c.label(suffix), "variant": c.variant}


# ---------------------------------------------------------------------------------------------------------------
# Reading a set
# ---------------------------------------------------------------------------------------------------------------

_QUESTIONS = """
SELECT q.id, q.seq, q.part, q.text_encrypted, q.suggested, q.created_at,
       a.id AS answer_id, a.by_code, a.text_encrypted AS answer_encrypted, a.added_to, a.saved_at, a.sent_at
FROM questions q LEFT JOIN answers a ON a.question_id = q.id
WHERE q.set_id = %s ORDER BY q.seq
"""


def _rows(conn: Conn, set_id: Any) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute(_QUESTIONS, (set_id,)).fetchall()]


def _question_text(r: dict[str, Any]) -> str:
    return unseal(r["text_encrypted"], "questions", "text_encrypted", str(r["id"])) or ""


def _answer_text(r: dict[str, Any]) -> str:
    return unseal(r["answer_encrypted"], "answers", "text_encrypted", str(r["answer_id"])) or ""


def _files(conn: Conn, answer_ids: Sequence[str]) -> dict[str, list[dict[str, Any]]]:
    """E-ENTITIES FileItem, short form, for the files attached to each answer, in every state: the sharer sees all
    of their own. A link's `type` is "link" (it has no MIME type); a file's is its MIME type. `customer_detail` marks
    a file in which the scan found a customer detail (DEC-107)."""
    out: dict[str, list[dict[str, Any]]] = {}
    if not answer_ids:
        return out
    for r in conn.execute(
        "SELECT id, answer_id, kind, name, mime, bytes, pages, file_state, hidden_note FROM attachments "
        "WHERE answer_id = ANY(%s::uuid[]) ORDER BY created_at, id",
        (list(answer_ids),),
    ).fetchall():
        out.setdefault(str(r["answer_id"]), []).append(
            {"id": r["id"], "kind": r["kind"], "name": r["name"],
             "type": "link" if r["kind"] == "link" else r["mime"], "size": r["bytes"],
             "pages": r["pages"], "state": r["file_state"], "hidden_note": r["hidden_note"],
             "customer_detail": r["file_state"] == CUSTOMER_DETAIL}
        )  # fmt: skip
    return out


def _only(files: list[dict[str, Any]], states: Sequence[str]) -> list[dict[str, Any]]:
    """What someone other than the file's sharer may see (DEC-107): the desk `DESK_SEES`, a co-sharer the checked
    files only. Never a file still checking, infected or locked."""
    return [x for x in files if x["state"] in states]


def _set_facts(s: dict[str, Any], rows: Sequence[dict[str, Any]]) -> SetFacts:
    sent = [r["sent_at"] for r in rows if r["sent_at"] is not None]
    return SetFacts(
        count=len(rows), answered=len(sent), sent_at=s["sent_at"], seen_at=s["seen_at"], due_at=s["due_at"],
        answered_at=max(sent) if sent else None, closed=s["state"] == "closed",
    )  # fmt: skip


def _has_content(answer: dict[str, Any]) -> bool:
    return bool(str(answer["text"]).strip()) or bool(answer["files"])


def _set_json(
    conn: Conn, s: dict[str, Any], idea: dict[str, Any], t: dt.datetime, *, viewer_code: str | None
) -> dict[str, Any]:
    """E-ENTITIES.review QuestionSet. Sent answers show to everyone who reads the set; a saved, unsent answer only
    to the sharer who wrote it (`viewer_code`), never to a co-sharer credited through a merge."""
    rows = _rows(conn, s["id"])
    shown = {
        str(r["answer_id"])
        for r in rows
        if r["answer_id"]
        and (r["sent_at"] is not None or (viewer_code is not None and r["by_code"] == viewer_code))
    }
    files = _files(conn, sorted(shown))
    people: dict[str, Person] = {}

    def by(code: str) -> dict[str, Any]:
        if code not in people:
            people[code] = person_by_code(conn, code)
        return people[code].as_json()

    items = []
    for r in rows:
        answer = None
        aid = str(r["answer_id"]) if r["answer_id"] else None
        if aid in shown:
            theirs = files.get(aid or "", [])
            if r["by_code"] != viewer_code:  # the desk, or a co-sharer reading another sharer's sent answer
                theirs = _only(theirs, DESK_SEES if viewer_code is None else FILES_CHECKED)
            answer = {
                "id": aid, "question_id": str(r["id"]), "text": _answer_text(r), "files": theirs,
                "by": by(str(r["by_code"])), "at": _iso(r["sent_at"] or r["saved_at"]), "added_to": r["added_to"],
                "added_to_name": PART_NAMES.get(str(r["added_to"]), ""), "saved_at": _iso(r["saved_at"]),
                "sent_at": _iso(r["sent_at"]), "sent": r["sent_at"] is not None,
            }  # fmt: skip
        items.append(
            {"id": str(r["id"]), "seq": r["seq"], "part": r["part"], "part_name": PART_NAMES[str(r["part"])],
             "text": _question_text(r), "suggested": bool(r["suggested"]), "answer": answer}
        )  # fmt: skip
    f = _set_facts(s, rows)
    return {
        "id": str(s["id"]), "idea_id": idea["idea_id"], "by": person_by_user(conn, str(s["by_user_id"])).as_json(),
        "state": s["state"], "time_to_answer": s["time_to_answer"], "sent_at": _iso(s["sent_at"]),
        "seen_at": _iso(s["seen_at"]), "due_at": _iso(s["due_at"]), "answered_at": _iso(s["answered_at"]),
        "extended_times": s["extended_times"], "reminded_at": _iso(s["reminded_at"]), "count": f.count,
        "answered": f.answered, "overdue": questions.overdue(f, t), "questions": items,
    }  # fmt: skip


# ---------------------------------------------------------------------------------------------------------------
# The reviewer (L-QUESTIONS.ask, L-QUESTIONS.clock/3)
# ---------------------------------------------------------------------------------------------------------------


def _filled(conn: Conn, idea: dict[str, Any]) -> dict[str, bool]:
    """Which parts of the idea have something in them, for the suggestions (L-QUESTIONS.ask/3)."""

    def exists(sql: str) -> bool:
        return conn.execute(sql, (idea["id"],)).fetchone() is not None

    return {
        "summary": bool(str(idea.get("summary") or "").strip()),
        "often": bool(str(idea.get("often") or "").strip()),
        "who": bool(idea.get("affects")),
        "cost": exists("SELECT 1 FROM idea_worth WHERE idea_uuid = %s LIMIT 1"),
        "evidence": exists("SELECT 1 FROM attachments WHERE idea_uuid = %s LIMIT 1"),
        "fix": exists("SELECT 1 FROM idea_fix WHERE idea_uuid = %s"),
    }


def _asked(conn: Conn, idea_uuid: Any, user_id: str) -> list[str]:
    """What was asked on the idea, and what this reviewer has queued. Another reviewer's queued set is theirs alone
    (BLD-B272), so it is never read here."""
    rows = conn.execute(
        "SELECT q.id, q.text_encrypted FROM questions q JOIN question_sets s ON s.id = q.set_id "
        "WHERE s.idea_uuid = %s AND (s.state <> 'queued' OR s.by_user_id = %s)",
        (idea_uuid, user_id),
    ).fetchall()
    return [_question_text(dict(r)) for r in rows]


def suggested(conn: Conn, ref: str, user_id: str) -> list[dict[str, str]]:
    """`GET /desk/ideas/:id/suggested-questions`: one per part, the idea's gaps first, none already asked."""
    with audited(conn), conn.transaction():
        idea = load_idea(conn, ref, lock=True)
        refuse_own(conn, user_id, idea, "ask")
        found = questions.suggestions(_filled(conn, idea), _asked(conn, idea["id"], user_id))
        return [{"part": s.part, "text": s.text} for s in found]


# The panel's revision is the browser's clock in milliseconds or one more than the last (BLD-B272); anything that is
# not a whole number in this range is refused, so a stored revision always fits the column and a JSON number.
REV_MAX = 2**53 - 1


def _latest_set(conn: Conn, idea_uuid: Any) -> dict[str, Any] | None:
    """The set the panel works from (`desk.reads._panel`): the latest one sent and not closed."""
    row = conn.execute(
        "SELECT id, state FROM question_sets WHERE idea_uuid = %s AND state NOT IN ('queued', 'closed') "
        "ORDER BY created_at DESC LIMIT 1",
        (idea_uuid,),
    ).fetchone()
    return dict(row) if row else None


def save_queue(
    conn: Conn, ref: str, user_id: str, body: dict[str, Any], at: dt.datetime | None = None
) -> dict[str, Any]:
    """`PUT /desk/ideas/:id/question-sets/queued` (BLD-B272, amends BLD-B244): the reviewer's whole queue for the idea,
    stored as their queued set so it is still there when they come back (S-R2.panel Asking, L-QUESTIONS.states). It
    replaces the queued set the idea had (one queued set per idea, as Send already takes whichever is there).
    `body`: `{questions: [{part, text, suggested?}], time_to_answer, rev, after}`.

    - Each question is hidden before it is stored (`adapters.hide_queued`, the same `hide` as Send; L-HIDE): only the
      masked copy is kept, sealed as Send seals it. A question stored by this reviewer and sent back unchanged (the
      page shows the masked copy) is already masked and is kept as it is, with no second model call.
    - A save that comes too late keeps nothing (409 `queue_stale`): the idea has left the desk (decided or merged:
      `review.ensure_on_desk`, 409 `already_decided`); a set was sent since the panel's read (`after`, the latest set
      the panel knew, `desk.reads._panel`'s `set_id`; null when none), or one is still waiting on answers; or the
      stored queue is this reviewer's with a revision no lower than `rev` (an older save overtaken, or another tab).
    - Audited with IDs, counts and parts only, never the words; nothing is logged (non-negotiable 3)."""
    t = at or now()
    p = promises.get()
    raw = body.get("questions")
    if not isinstance(raw, list):
        raise Refused(422, "questions_required", "Add a question first.", "questions")
    asked: list[dict[str, Any]] = [q if isinstance(q, dict) else {} for q in raw]
    chosen = body.get("time_to_answer")
    rev = body.get("rev")
    if isinstance(rev, bool) or not isinstance(rev, int) or not 0 < rev <= REV_MAX:
        raise Refused(422, "rev_invalid", None, "rev")
    after_raw = body.get("after")
    after = after_raw if isinstance(after_raw, str) and after_raw else None  # compared as the worker wrote it
    with audited(conn), conn.transaction():
        # lane C's lock before any row lock: the questions are hidden below (BLD-B247), as in `send_set`
        adapters.lock_refs(conn, ref)
        idea = load_idea(conn, ref, lock=True)
        refuse_own(conn, user_id, idea, "ask")
        review.ensure_on_desk(idea)
        errors = [e for e in questions.check_set(asked, chosen, p) if e.code != "no_questions"]
        if errors:
            raise _refused(errors[0])
        latest = _latest_set(conn, idea["id"])
        if (str(latest["id"]) if latest else None) != after or (
            latest is not None and latest["state"] in OPEN
        ):
            raise Refused(409, "queue_stale")
        current = conn.execute(
            "SELECT id, by_user_id, queue_rev FROM question_sets WHERE idea_uuid = %s AND state = 'queued' FOR UPDATE",
            (idea["id"],),
        ).fetchone()
        mine = current is not None and str(current["by_user_id"]) == user_id
        if mine and current is not None and rev <= int(current["queue_rev"] or 0):
            raise Refused(409, "queue_stale")
        # masked copies this reviewer already stored: one sent back unchanged needs no second pass
        kept = (
            {
                _question_text(dict(r))
                for r in conn.execute(
                    "SELECT id, text_encrypted FROM questions WHERE set_id = %s", (current["id"],)
                ).fetchall()
            }
            if mine and current is not None
            else set()
        )
        if current is not None:  # one queued set per idea: this save replaces it (its questions go with it)
            conn.execute("DELETE FROM question_sets WHERE id = %s", (current["id"],))
        set_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO question_sets (id, idea_uuid, by_user_id, state, time_to_answer, queue_rev, created_at) "
            "VALUES (%s, %s, %s, 'queued', %s, %s, %s)",
            (set_id, idea["id"], user_id, chosen, rev, t),
        )
        for seq, q in enumerate(asked, start=1):
            qid = str(uuid.uuid4())
            text = str(q["text"]).strip()
            masked = (
                text
                if text in kept
                else adapters.hide_queued(conn, str(idea["id"]), text, by=user_id, question_id=qid)
            )
            conn.execute(
                "INSERT INTO questions (id, set_id, seq, part, text_encrypted, suggested, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (qid, set_id, seq, q["part"], seal(masked, "questions", "text_encrypted", qid),
                 bool(q.get("suggested")), t),
            )  # fmt: skip
        audit(conn, actor(user_id), "desk.queue_questions", f"idea:{idea['idea_id']}",
              after={"set_id": set_id, "count": len(asked), "parts": [str(q["part"]) for q in asked],
                     "time_to_answer": chosen, "rev": rev, "replaced": str(current["id"]) if current else None})  # fmt: skip
        return {"set_id": set_id, "rev": rev, "count": len(asked)}


def send_set(
    conn: Conn, ref: str, user_id: str, body: dict[str, Any], at: dt.datetime | None = None
) -> dict[str, Any]:
    """`POST /desk/ideas/:id/question-sets`: the queued questions go to the sharer as one set with a time to
    answer. The idea moves to Needs you, the answer clock starts, and the sharer is told (L-QUESTIONS.ask/4–6).
    `body`: `{questions: [{part, text, suggested?}], time_to_answer?, move_decide_by?}`."""
    t = at or now()
    p = promises.get()
    cal = clock.office_calendar()
    raw = body.get("questions")
    asked: list[dict[str, Any]] = (
        [q if isinstance(q, dict) else {} for q in raw] if isinstance(raw, list) else []
    )
    chosen = body.get("time_to_answer")
    with audited(conn), conn.transaction():
        # lane C's lock before any row lock: the questions are hidden below (BLD-B247)
        adapters.lock_refs(conn, ref)
        idea = load_idea(conn, ref, lock=True)
        refuse_own(conn, user_id, idea, "ask")
        review.ensure_on_desk(idea)
        errors = questions.check_set(asked, chosen, p)
        if errors:
            raise _refused(errors[0])
        sharer = person_by_code(conn, idea["contributor_code"])
        if conn.execute(
            "SELECT 1 FROM question_sets WHERE idea_uuid = %s AND state = ANY(%s) LIMIT 1",
            (idea["id"], list(OPEN)),
        ).fetchone():
            raise Refused(
                409, "set_open",
                f"{sharer.first_name} still has questions open. Ask a follow-up once they are answered.",
            )  # fmt: skip
        if idea["opened_at"] is None:  # asking is opening (L-REVIEW.open/1)
            review.open_idea(conn, idea["idea_id"], user_id, t)
        time_to_answer = str(chosen or p.answer_default)
        due = clock.answer_due(t, time_to_answer, p, cal)
        set_id = str(uuid.uuid4())
        # The body carries the queue; a queued set kept for this idea is now sent, so it goes (one queued per idea).
        conn.execute("DELETE FROM question_sets WHERE idea_uuid = %s AND state = 'queued'", (idea["id"],))
        conn.execute(
            "INSERT INTO question_sets (id, idea_uuid, by_user_id, state, time_to_answer, sent_at, due_at, created_at) "
            "VALUES (%s, %s, %s, 'sent', %s, %s, %s, %s)",
            (set_id, idea["id"], user_id, time_to_answer, t, due, t),
        )
        for seq, q in enumerate(asked, start=1):
            qid = str(uuid.uuid4())
            masked, _ = adapters.hide(conn, str(idea["id"]), str(q["text"]).strip(), by=user_id)
            conn.execute(
                "INSERT INTO questions (id, set_id, seq, part, text_encrypted, suggested, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (qid, set_id, seq, q["part"], seal(masked, "questions", "text_encrypted", qid),
                 bool(q.get("suggested")), t),
            )  # fmt: skip
        conn.execute("UPDATE ideas SET status = 'needs_you' WHERE id = %s", (idea["id"],))
        decide_by = idea["decide_by"]
        if body.get("move_decide_by") and decide_by is not None and clock.after_decide_by(due, decide_by):
            decide_by = review.move_decide_by(conn, idea, user_id, _working_day_after(due, p, cal), cal)
        adapters.say(conn, str(idea["id"]), "desk.asked", author_user_id=user_id,
                     payload={"set_id": set_id, "count": len(asked)}, question_set_id=set_id,
                     entry_type="questions", at=t)  # fmt: skip
        adapters.tell(
            conn, "questions", _sharers(conn, idea), idea_uuid=str(idea["id"]), sender=user_id, needs_you=True,
            due_at=due, actions=[_answer_action(idea)], refs={"set_id": set_id, "count": len(asked)},
            dedupe_key=adapters.questions_key(set_id),
        )  # fmt: skip
        _schedule_reminders(conn, set_id, t, due, p)
        audit(conn, actor(user_id), "desk.ask", f"idea:{idea['idea_id']}",
              before={"status": idea["status"]},
              after={"set_id": set_id, "count": len(asked), "parts": [str(q["part"]) for q in asked],
                     "time_to_answer": time_to_answer, "due_at": due.isoformat()})  # fmt: skip
        out = _set_json(conn, _load_set(conn, set_id), idea, t, viewer_code=None)
        after = decide_by is not None and clock.after_decide_by(due, decide_by)
        out.update({
            "due_label": questions.deadline_line(sharer.first_name, due, t, cal.tz),
            "countdown": _countdown(due, t, "to answer", cal.tz),
            "after_decide_by": after,
            "after_decide_by_line": questions.AFTER_DECIDE_BY if after else None,
            "decide_by": _iso(decide_by),
        })  # fmt: skip
        return out


def give_more_time(conn: Conn, set_id: str, user_id: str, at: dt.datetime | None = None) -> dict[str, Any]:
    """`POST /question-sets/:id/extend`: "Give 2 more days", once per click (L-QUESTIONS.clock/3)."""
    t = at or now()
    p = promises.get()
    cal = clock.office_calendar()
    tz = cal.tz
    sid = _uuid(set_id)
    with audited(conn), conn.transaction():
        idea, s = _reviewer_set(conn, sid, user_id, "give_more_time")
        due = clock.give_more_time(s["due_at"], p, t, cal)  # from now when it is overdue
        n = int(s["extended_times"]) + 1
        conn.execute("UPDATE question_sets SET due_at = %s, extended_times = %s WHERE id = %s", (due, n, sid))
        # V-ACC.track/3: the sharer's Needs you item moves to the new deadline, so Home, Inbox, the idea page and the
        # conversation count down to the same time. Posted again under the set's key, which keeps one item.
        count = conn.execute("SELECT count(*) AS n FROM questions WHERE set_id = %s", (sid,)).fetchone()
        adapters.tell(
            conn, "questions", _sharers(conn, idea), idea_uuid=str(idea["id"]), sender=user_id, needs_you=True,
            due_at=due, actions=[_answer_action(idea)],
            refs={"set_id": sid, "count": int(count["n"]) if count else 0, "more_time": True},
            dedupe_key=adapters.questions_key(sid),
        )  # fmt: skip
        _schedule_reminders(conn, sid, t, due, p)  # 1 day and 2 hours before the new deadline
        audit(conn, actor(user_id), "desk.give_more_time", f"idea:{idea['idea_id']}",
              before={"set_id": sid, "due_at": _iso(s["due_at"])},
              after={"set_id": sid, "due_at": due.isoformat(), "extended_times": n})  # fmt: skip
        sharer = person_by_code(conn, idea["contributor_code"])
        return {
            "id": sid, "due_at": due.isoformat(), "extended_times": n,
            "due_label": questions.deadline_line(sharer.first_name, due, t, tz),
            "countdown": _countdown(due, t, "to answer", tz),
        }  # fmt: skip


def _remind(
    conn: Conn,
    idea: dict[str, Any],
    s: dict[str, Any],
    recipients: Sequence[str],
    sender: str,
    t: dt.datetime,
    dedupe_key: str | None = None,
) -> None:
    sid = str(s["id"])
    day = t.astimezone(clock.office_calendar().tz).date().isoformat()
    adapters.tell(
        conn, "answer_reminder", recipients, idea_uuid=str(idea["id"]), sender=sender, needs_you=True,
        due_at=s["due_at"], actions=[_answer_action(idea)], refs={"set_id": sid},
        dedupe_key=dedupe_key or f"{adapters.questions_key(sid)}:{day}:{t.astimezone(clock.office_calendar().tz):%H}",
    )  # fmt: skip
    conn.execute("UPDATE question_sets SET reminded_at = %s WHERE id = %s", (t, sid))


def remind(conn: Conn, set_id: str, user_id: str, at: dt.datetime | None = None) -> dict[str, Any]:
    """`POST /question-sets/:id/remind`: "Send a reminder", or "Remind {sharer}" on an overdue row."""
    t = at or now()
    sid = _uuid(set_id)
    with audited(conn), conn.transaction():
        idea, s = _reviewer_set(conn, sid, user_id, "remind")
        _remind(conn, idea, s, _sharers(conn, idea), user_id, t)
        audit(conn, actor(user_id), "desk.remind", f"idea:{idea['idea_id']}", after={"set_id": sid})
        return {"id": sid, "reminded_at": t.isoformat()}


def _reminders_on(conn: Conn, user_id: str) -> bool:
    row = conn.execute("SELECT reminders FROM comms_prefs WHERE user_id = %s", (user_id,)).fetchone()
    return row is None or bool(row["reminders"])


def remind_due(conn: Conn, set_id: str, at: dt.datetime | None = None) -> bool:
    """Timer handler (`desk.answer_reminder`): 1 day and 2 hours before the deadline (L-QUESTIONS.clock/2). Does
    nothing for a set that is answered or closed, for a sharer with reminders off (S-H6), once the deadline has
    passed, before a threshold that falls after the sending (`clock.reminders`), or for a timer set before "Give 2
    more days" moved the deadline (it would come too early)."""
    t = at or now()
    p = promises.get()
    try:
        sid = _uuid(set_id)
    except Refused:
        return False
    with conn.transaction():
        row = conn.execute("SELECT * FROM question_sets WHERE id = %s FOR UPDATE", (sid,)).fetchone()
        if row is None or row["state"] not in OPEN or row["due_at"] is None:
            return False
        s = dict(row)
        # the same thresholds the timer path schedules: only those after the set was sent, so a 1-day set (its
        # "1 day before" falls on the sending itself) is never reminded the moment it arrives
        passed = [x for x in clock.reminders(s["sent_at"] or s["created_at"], s["due_at"], p) if x <= t]
        if t >= s["due_at"] or not passed:
            return False
        # once per threshold: the latest of "1 day before" and "2 hours before" already passed, unless a reminder
        # (timed or by hand) has gone since then, so a sweep every few minutes reminds twice in all
        crossed = max(passed)
        if s["reminded_at"] is not None and s["reminded_at"] >= crossed:
            return False
        found = conn.execute(
            "SELECT id, idea_id, contributor_code FROM ideas WHERE id = %s", (s["idea_uuid"],)
        ).fetchone()
        if found is None:
            return False
        idea = dict(found)
        recipients = [u for u in _sharers(conn, idea) if _reminders_on(conn, u)]
        if not recipients:
            return False
        # one per (set, threshold): a retry or an overlapping run never sends it twice (lane A's ask)
        _remind(
            conn, idea, s, recipients, "system", t, f"{adapters.questions_key(sid)}:{crossed:%Y%m%dT%H%M%z}"
        )
        audit(conn, "system", "desk.answer_reminder", f"idea:{idea['idea_id']}", after={"set_id": sid})
        return True


# ---------------------------------------------------------------------------------------------------------------
# The sharer (L-QUESTIONS.answer, S-R3)
# ---------------------------------------------------------------------------------------------------------------


def open_set_for_sharer(
    conn: Conn, ref: str, user_id: str, at: dt.datetime | None = None, set_id: str | None = None
) -> dict[str, Any] | None:
    """`GET /ideas/:id/question-set`: the latest set sent (not closed), with the sharer's own saved answers and
    S-R3's words. The first look marks it seen; the desk shows "seen 12:05 pm". With `set_id` (the Inbox reader
    opening one item), a different open set is not that item's: nothing is returned and nothing is marked seen."""
    t = at or now()
    tz = clock.office_calendar().tz
    with conn.transaction():
        idea = load_idea(conn, ref)
        code = _sharer_code(conn, idea, user_id)
        row = conn.execute(
            "SELECT * FROM question_sets WHERE idea_uuid = %s AND state NOT IN ('queued', 'closed') "
            "ORDER BY sent_at DESC NULLS LAST, created_at DESC LIMIT 1 FOR UPDATE",
            (idea["id"],),
        ).fetchone()
        if row is None or (set_id is not None and str(row["id"]) != set_id):
            return None
        s = dict(row)
        if s["seen_at"] is None:
            seen = conn.execute(
                "UPDATE question_sets SET seen_at = %s, state = CASE WHEN state = 'sent' THEN 'seen' ELSE state END "
                "WHERE id = %s RETURNING *",
                (t, s["id"]),
            ).fetchone()
            s = dict(seen) if seen else s
        out = _set_json(conn, s, idea, t, viewer_code=code)
        answers = [q["answer"] for q in out["questions"] if q["answer"] and _has_content(q["answer"])]
        ready = sum(1 for a in answers if not a["sent"])
        out.update({
            "by": None,  # DEC-111: the sharer never sees who at the review desk asked, not even in the JSON
            "idea": {"id": idea["idea_id"], "title": idea["title"]},
            "countdown": _countdown(s["due_at"], t, "left to answer", tz),
            "deadline": f"Answer by {when.deadline(s['due_at'], t, tz)}",
            "progress": f"{len(answers)} of {out['count']} answered",
            "send_label": questions.send_answers_label(ready),
        })  # fmt: skip
        return out


def _link_files(conn: Conn, idea: dict[str, Any], answer_id: str, file_ids: Sequence[str]) -> None:
    """Attach `file_ids` to the answer. Only the idea's own files, not on another answer. A file holding a customer
    detail can be attached and sent (DEC-107): it is marked, and only the sharer, the desk and the committee open it.
    Nothing is detached here: removing a file is the file row's own action."""
    ids = sorted({str(i) for i in file_ids})
    if not ids:
        return
    rows = {
        str(r["id"]): dict(r)
        for r in conn.execute(
            "SELECT id, idea_uuid, file_state, answer_id FROM attachments WHERE id = ANY(%s) FOR UPDATE",
            (ids,),
        ).fetchall()
    }
    for fid in ids:
        r = rows.get(fid)
        if r is None or r["idea_uuid"] != idea["id"] or (r["answer_id"] and str(r["answer_id"]) != answer_id):
            raise Refused(422, "file_not_found", FILE_CANT_BE_ADDED, "file_ids")
    conn.execute("UPDATE attachments SET answer_id = %s WHERE id = ANY(%s)", (answer_id, ids))


def _answer_body(text: Any, file_ids: Any) -> tuple[str | None, tuple[str, ...]]:
    """The body's types, checked before anything else (A-API.conventions/2): text is text, file_ids a list of ids."""
    if text is not None and not isinstance(text, str):
        raise Refused(422, "answer_invalid", "Write your answer as text.", "text")
    if file_ids is None:
        return text, ()
    if not isinstance(file_ids, list | tuple) or not all(isinstance(i, str) for i in file_ids):
        raise Refused(422, "file_not_found", FILE_CANT_BE_ADDED, "file_ids")
    return text, tuple(file_ids)


def _empty_draft(conn: Conn, answer: dict[str, Any]) -> bool:
    """A draft answer with no text and no file: nobody's yet (L-QUESTIONS.answer/4)."""
    if answer["text_encrypted"] is not None:
        return False
    return (
        conn.execute("SELECT 1 FROM attachments WHERE answer_id = %s LIMIT 1", (answer["id"],)).fetchone()
        is None
    )


def save_answer(
    conn: Conn,
    question_id: str,
    user_id: str,
    text: Any,
    file_ids: Any = (),
    at: dt.datetime | None = None,
) -> dict[str, Any]:
    """`PUT /questions/:id/answer`: autosave a draft answer, masked (L-QUESTIONS.answer/4, /6), and attach any
    `file_ids` (files already on the answer stay). `text` and `file_ids` arrive as the body has them."""
    t = at or now()
    p = promises.get()
    qid = _uuid(question_id)
    text, file_ids = _answer_body(text, file_ids)
    with conn.transaction():
        # lane C's lock on the idea first, read with no row lock, then the set (BLD-B247)
        on = conn.execute(
            "SELECT s.idea_uuid FROM questions q JOIN question_sets s ON s.id = q.set_id WHERE q.id = %s",
            (qid,),
        ).fetchone()
        if on is None:
            raise Refused(404, "not_found")
        adapters.lock_idea(conn, str(on["idea_uuid"]))
        q = conn.execute(
            "SELECT q.id, q.part, q.set_id, s.idea_uuid, s.state FROM questions q "
            "JOIN question_sets s ON s.id = q.set_id WHERE q.id = %s FOR UPDATE OF s",
            (qid,),
        ).fetchone()
        if q is None or q["state"] == "queued":
            raise Refused(404, "not_found")
        idea = load_idea(conn, str(q["idea_uuid"]))
        code = _sharer_code(conn, idea, user_id)
        if q["state"] == "closed":
            raise Refused(409, "set_closed", CLOSED)
        existing = conn.execute(
            "SELECT id, by_code, sent_at, text_encrypted FROM answers WHERE question_id = %s FOR UPDATE",
            (qid,),
        ).fetchone()
        if existing and existing["sent_at"] is not None:
            raise Refused(409, "answer_sent", "This answer is already with the review desk.")
        # one answer row per question (answers.question_id is unique): a co-sharer's draft stays theirs, unless it
        # holds nothing yet (an autosave of an empty box), which another credited sharer takes over
        if existing and existing["by_code"] != code and not _empty_draft(conn, existing):
            raise Refused(409, "answer_in_progress", ANSWER_IN_PROGRESS)
        errors = questions.check_answer(text, p)
        if errors:
            raise _refused(errors[0])
        aid = str(existing["id"]) if existing else str(uuid.uuid4())
        # the sharer's answer: its details keep their ids across autosaves and their own words are sealed for them
        # (L-HIDE.rules/4). Autosave runs the patterns only; the gatekeeper runs once, on send (BLD-B247). A refusal
        # from hiding (the sealed words under this id are someone else's) is S-R3's failure line, never a raw error,
        # and so is any other failure inside it (500, tried again by the screen); the log has its type only.
        masked, hidden = "", 0
        if text and text.strip():
            try:
                done = adapters.hide_answer(
                    conn, str(idea["id"]), text, by=user_id, answer_id=aid, gatekeeper=False
                )
            except HideError:
                raise Refused(409, "answer_not_saved", NOT_SAVED) from None
            except Exception:
                log.exception("desk.answer_hide_failed", step="save")
                raise Refused(500, "answer_not_saved", NOT_SAVED) from None
            masked, hidden = done.masked, done.hidden_count
        elif existing:
            # an emptied box hides nothing and keeps no words any more, so a co-sharer may take it over
            adapters.forget_answer(conn, str(idea["id"]), aid)
        sealed = seal(masked, "answers", "text_encrypted", aid) if masked.strip() else None
        if existing:
            conn.execute(
                "UPDATE answers SET by_code = %s, text_encrypted = %s, saved_at = %s WHERE id = %s",
                (code, sealed, t, aid),
            )
        else:
            conn.execute(
                "INSERT INTO answers (id, question_id, by_code, text_encrypted, added_to, saved_at) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (aid, qid, code, sealed, q["part"], t),
            )
        _link_files(conn, idea, aid, file_ids)
        return {
            "id": aid, "question_id": qid, "text": masked, "hidden": hidden,
            "files": _files(conn, [aid]).get(aid, []), "added_to": q["part"],
            "added_to_name": PART_NAMES[str(q["part"])], "saved_at": t.isoformat(), "sent": False,
        }  # fmt: skip


def send_answers(conn: Conn, set_id: str, user_id: str, at: dt.datetime | None = None) -> dict[str, Any]:
    """`POST /question-sets/:id/send`: every saved answer not yet sent goes to the review desk at once
    (L-QUESTIONS.answer/3, /5). Unanswered questions stay open until the deadline."""
    t = at or now()
    tz = clock.office_calendar().tz
    sid = _uuid(set_id)
    with audited(conn), conn.transaction():
        first = _load_set(conn, sid)
        adapters.lock_idea(conn, str(first["idea_uuid"]))  # lane C's lock before any row lock (BLD-B247)
        idea = load_idea(conn, str(first["idea_uuid"]), lock=True)
        code = _sharer_code(conn, idea, user_id)
        s = _load_set(conn, sid, lock=True)
        if s["state"] == "queued":
            raise Refused(404, "not_found")
        if s["state"] == "closed":
            raise Refused(409, "set_closed", CLOSED)
        rows = _rows(conn, sid)
        # only the caller's own drafts go: a co-sharer's unsent answer is theirs to send (L-QUESTIONS.answer/3)
        unsent = [
            r for r in rows if r["answer_id"] is not None and r["sent_at"] is None and r["by_code"] == code
        ]
        files = _files(conn, [str(r["answer_id"]) for r in unsent])
        ready = [r for r in unsent if _answer_text(r).strip() or files.get(str(r["answer_id"]))]
        if not ready:
            raise Refused(422, "nothing_answered", NOTHING_ANSWERED)
        _gatekeep(conn, str(idea["id"]), ready, user_id)
        # DEC-107: a file holding a customer detail goes too, marked; the desk decides whether it stays
        conn.execute(
            "UPDATE answers SET sent_at = %s WHERE id = ANY(%s::uuid[])",
            (t, [str(r["answer_id"]) for r in ready]),
        )
        answered = sum(1 for r in rows if r["sent_at"] is not None) + len(ready)
        state = "answered" if answered >= len(rows) else "partly_answered"
        conn.execute("UPDATE question_sets SET state = %s, answered_at = %s WHERE id = %s", (state, t, sid))
        if state == "answered" and idea["status"] == "needs_you":
            conn.execute("UPDATE ideas SET status = 'with_review_desk' WHERE id = %s", (idea["id"],))
        if state == "answered":  # every question answered: the item and its reminders leave Needs you
            adapters.resolve(conn, adapters.questions_key(sid))
        adapters.say(conn, str(idea["id"]), "sharer.answered", payload={"set_id": sid, "count": len(ready)},
                     author_code=code, question_set_id=sid, entry_type="answers", at=t)  # fmt: skip
        audit(conn, actor(user_id), "desk.answers_sent", f"idea:{idea['idea_id']}",
              before={"set_id": sid, "state": s["state"]},
              after={"set_id": sid, "count": len(ready), "state": state})  # fmt: skip
        decide_by = idea["decide_by"]
        # DEC-111: S-R3's sent lines name the review desk, never the reviewer ("Sent to Meera, 4:32 pm" on the board)
        return {
            "set_id": sid, "state": state, "sent": len(ready), "answered": answered, "count": len(rows),
            "sent_at": t.isoformat(), "progress": f"{answered} of {len(rows)} answered",
            "sent_line": f"Sent to {REVIEW_DESK}, {when.clock(t, tz)}",
            "spare": questions.spare_line(t, s["due_at"], tz),
            "decides_by": f"{REVIEW_DESK_START} decides by {when.day(decide_by, t, tz)}" if decide_by else None,
        }  # fmt: skip


def _gatekeep(conn: Conn, idea_uuid: str, ready: Sequence[dict[str, Any]], user_id: str) -> None:
    """Before an answer reaches the desk, one pass with the gatekeeper over the sharer's own words (autosave ran the
    patterns only), and the masked copy written again (non-negotiable 4; L-HIDE.rules/1; BLD-B247). An answer with no
    sealed words (one saved before they were kept) is checked as stored. Any refusal, or any other failure inside
    hiding, is S-R3's send failure line, never a raw error. When the gateway is down lane C's hide goes on with the
    patterns, audits `hide.gatekeeper_skipped` and queues a `hide.recheck` (BLD-C067): the answers are sent."""
    for r in ready:
        aid = str(r["answer_id"])
        stored = _answer_text(r)
        if not stored.strip():
            continue  # files only: the file checks cover them
        try:
            words = adapters.answer_words(conn, idea_uuid, aid)
            done = adapters.hide_answer(
                conn, idea_uuid, words or stored, by=user_id, answer_id=aid, gatekeeper=True
            )
        except HideError:
            raise Refused(409, "answers_not_sent", NOT_SENT) from None
        except Exception:
            log.exception("desk.answer_hide_failed", step="send")
            raise Refused(500, "answers_not_sent", NOT_SENT) from None
        if done.masked != stored:
            conn.execute(
                "UPDATE answers SET text_encrypted = %s WHERE id = %s",
                (seal(done.masked, "answers", "text_encrypted", aid) if done.masked.strip() else None, aid),
            )


# ---------------------------------------------------------------------------------------------------------------
# The desk's reads (S-R1 Questions column, S-R2 answers under each part)
# ---------------------------------------------------------------------------------------------------------------


def facts(conn: Conn, idea_uuid: Any) -> SetFacts | None:
    """The latest set sent on an idea, as `desk.questions` reads it: how many asked, answered (sent), seen, due."""
    row = conn.execute(
        "SELECT s.state, s.sent_at, s.seen_at, s.due_at, "
        "(SELECT count(*) FROM questions q WHERE q.set_id = s.id) AS n, "
        "(SELECT count(a.sent_at) FROM questions q JOIN answers a ON a.question_id = q.id WHERE q.set_id = s.id) "
        "AS answered, "
        "(SELECT max(a.sent_at) FROM questions q JOIN answers a ON a.question_id = q.id WHERE q.set_id = s.id) "
        "AS answered_at "
        "FROM question_sets s WHERE s.idea_uuid = %s AND s.state <> 'queued' "
        "ORDER BY s.sent_at DESC NULLS LAST, s.created_at DESC LIMIT 1",
        (idea_uuid,),
    ).fetchone()
    if row is None:
        return None
    return SetFacts(
        count=int(row["n"]), answered=int(row["answered"]), sent_at=row["sent_at"], seen_at=row["seen_at"],
        due_at=row["due_at"], answered_at=row["answered_at"], closed=row["state"] == "closed",
    )  # fmt: skip


def answers_by_part(conn: Conn, idea_uuid: Any) -> dict[str, list[dict[str, Any]]]:
    """Every question sent on the idea under its part, with its answer once sent (drafts stay the sharer's), who
    asked and answered and when, and the answer's files (L-QUESTIONS.answer/5; V-ACC.review/8). Read for the sharer's
    idea page (lane E's `ideapage.sharer`; the desk's S-R2 has its own read in `desk.reads`), so `asked_by` is the
    review desk, never the reviewer's name (DEC-111): "From your answer to the review desk, Monday 16 November"."""
    rows = [
        dict(r)
        for r in conn.execute(
            "SELECT s.by_user_id, s.sent_at AS asked_at, q.id, q.part, q.text_encrypted, "
            "a.id AS answer_id, a.by_code, a.text_encrypted AS answer_encrypted, a.added_to, a.sent_at "
            "FROM question_sets s JOIN questions q ON q.set_id = s.id "
            "LEFT JOIN answers a ON a.question_id = q.id AND a.sent_at IS NOT NULL "
            "WHERE s.idea_uuid = %s AND s.state <> 'queued' ORDER BY s.sent_at, s.created_at, q.seq",
            (idea_uuid,),
        ).fetchall()
    ]
    files = {
        k: _only(v, DESK_SEES)
        for k, v in _files(conn, [str(r["answer_id"]) for r in rows if r["answer_id"]]).items()
    }
    sharers: dict[str, str] = {}
    out: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by = None
        if r["answer_id"]:
            code = str(r["by_code"])
            if code not in sharers:
                sharers[code] = person_by_code(conn, code).first_name
            by = sharers[code]
        part = str(r["added_to"] or r["part"])
        out.setdefault(part, []).append(
            {"question_id": str(r["id"]), "question": _question_text(r), "asked_at": _iso(r["asked_at"]),
             "asked_by": REVIEW_DESK, "answer": _answer_text(r) if r["answer_id"] else None,
             "answered_at": _iso(r["sent_at"]), "by": by,
             "files": files.get(str(r["answer_id"]), []) if r["answer_id"] else []}
        )  # fmt: skip
    return {p: out[p] for p in PARTS if p in out}
