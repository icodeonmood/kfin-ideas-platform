"""Decisions: Pick, Not now, Not picked (L-DECIDE), and the committee's reversal checks (L-COMMITTEE.rules/3).

This part holds the rules that need no database: what a decision must carry, the messages a field shows, the
wording check, and the dates a decision sets. Writing a decision is added once the cut-over's tables exist.
"""

from __future__ import annotations

import datetime as dt
import re
import uuid
from dataclasses import dataclass
from typing import Any, Literal

from desk import adapters, clock, promises, when
from desk.promises import RETURN_IN, Promises
from desk.review import ensure_on_desk
from desk.store import (
    Refused,
    actor,
    audit,
    audited,
    load_idea,
    now,
    person_by_code,
    refuse_own,
    seal,
    sharers_and_crew,
)
from desk.window import add_months, open_window

Choice = Literal["pick", "not_now", "not_picked"]
CHOICES: tuple[Choice, ...] = ("pick", "not_now", "not_picked")
LABELS: dict[str, str] = {"pick": "Picked", "not_now": "Not now", "not_picked": "Not picked"}
STATUS_AFTER: dict[str, str] = {"pick": "picked", "not_now": "not_now", "not_picked": "not_picked"}
# The reason field's question follows the choice (L-DECIDE.rules/1).
REASON_LABELS: dict[str, str] = {
    "pick": "Why are you picking it?",
    "not_now": "Why not now, and what would change it?",
    "not_picked": "Why isn’t it going ahead?",
}


@dataclass(frozen=True)
class FieldError:
    """A-API.conventions/2: `message` is ready to show under the field named by `field`."""

    code: str
    field: str
    message: str


def _length(text: str) -> int:
    return len(text.strip())


def check_decision(
    choice: str | None, reason: str | None, return_in: str | None, sharer_first_name: str, p: Promises
) -> list[FieldError]:
    """V-FIELDS.review/4–6. An empty list means the decision can be sent."""
    errors: list[FieldError] = []
    if choice not in CHOICES:
        errors.append(FieldError("choice_required", "choice", "Choose Pick, Not now or Not picked first."))
    n = _length(reason or "")
    if n < p.reason_min:
        errors.append(
            FieldError(
                "reason_too_short",
                "reason",
                f"Give {sharer_first_name} a reason of at least a line, {p.reason_min} characters or more.",
            )
        )
    elif n > p.reason_max:
        errors.append(
            FieldError("reason_too_long", "reason", f"Keep the reason under {p.reason_max:,} characters.")
        )
    if choice == "not_now" and return_in is not None and return_in not in RETURN_IN:
        errors.append(FieldError("return_in_invalid", "return_in", "Choose when it comes back."))
    return errors


def check_reversal(
    to: str | None, original: str, note: str | None, return_in: str | None, p: Promises
) -> list[FieldError]:
    """V-FIELDS.committee/1–2: one of the two other decisions, and a note of a line or more."""
    errors: list[FieldError] = []
    if to not in CHOICES or to == original:
        errors.append(FieldError("to_required", "to", "Choose what to change it to."))
    n = _length(note or "")
    if n < p.reversal_note_min:
        errors.append(
            FieldError(
                "note_too_short",
                "note",
                f"Write a note of at least a line, {p.reversal_note_min} characters or more.",
            )
        )
    elif n > p.reversal_note_max:
        errors.append(
            FieldError("note_too_long", "note", f"Keep the note under {p.reversal_note_max:,} characters.")
        )
    if to == "not_now" and return_in is not None and return_in not in RETURN_IN:
        errors.append(FieldError("return_in_invalid", "return_in", "Choose when it comes back."))
    return errors


def counter(text: str, sharer_first_name: str, p: Promises) -> str:
    """The line under the reason: '12 of at least 30 characters', then '{sharer} reads this word for word.'"""
    n = _length(text)
    if n < p.reason_min:
        return f"{n} of at least {p.reason_min} characters"
    return f"{sharer_first_name} reads this word for word."


# L-DECIDE.rules/4 and F-COPY: words the product never uses to a sharer, with a plainer way to say it.
_WORDING: tuple[tuple[str, str], ...] = (
    (r"\bduplicates?\b", "say it is the same problem as another idea, and name it"),
    (r"\brejected\b", "say it is not going ahead, and why"),
    (r"\balready solved\b", "say what already fixes it, and where"),
    (r"\bappeals?\b", "say the Ones Committee can review the decision"),
    (r"\binvalid\b", "say what is missing"),
)


@dataclass(frozen=True)
class WordingNote:
    word: str
    suggestion: str


def wording_check(reason: str) -> list[WordingNote]:
    """Warn, never block: the reason is the reviewer's own (`NOT DRAWN:` default of L-DECIDE.rules/4)."""
    notes: list[WordingNote] = []
    for pattern, suggestion in _WORDING:
        m = re.search(pattern, reason, flags=re.IGNORECASE)
        if m:
            notes.append(WordingNote(m.group(0), suggestion))
    return notes


def return_at(decided_at: dt.datetime, return_in: str, p: Promises) -> dt.datetime:
    """L-DECIDE.rules/7: Not now comes back after 1, 3 or 6 months."""
    return add_months(decided_at, p.return_months_for(return_in))


@dataclass(frozen=True)
class DecisionDates:
    return_at: dt.datetime | None
    team_by: dt.datetime | None


def dates_for(choice: Choice, decided_at: dt.datetime, return_in: str | None, p: Promises,
              cal: clock.Calendar) -> DecisionDates:  # fmt: skip
    """What a decision schedules: Not now's return date, Pick's team-by date."""
    if choice == "not_now":
        return DecisionDates(return_at(decided_at, return_in or p.return_default, p), None)
    if choice == "pick":
        return DecisionDates(None, clock.team_by(decided_at, p, cal))
    return DecisionDates(None, None)


def return_words(t: dt.datetime, sharer_first_name: str, now: dt.datetime, tz: dt.tzinfo = when.IST) -> str:
    """'Comes back to you and Kavya on Tuesday 16 February 2027' (the reviewer's line)."""
    return f"Comes back to you and {sharer_first_name} on {when.day(t, now, tz)}"


# ---------------------------------------------------------------------------------------------------------------
# Sending a decision (L-DECIDE.rules/3, /5–10)
# ---------------------------------------------------------------------------------------------------------------


def _refused(e: FieldError, status: int = 422) -> Refused:
    return Refused(status, e.code, e.message, e.field)


def send(
    conn: Any, ref: str, user_id: str, body: dict[str, Any], at: dt.datetime | None = None
) -> dict[str, Any]:
    """The reviewer sends Pick, Not now or Not picked with a reason. The sharer reads it at once, the committee's
    window opens, open question sets close and queued ones are dropped. Never edited afterwards (rules/9)."""
    t = at or now()
    p = promises.get()
    cal = clock.office_calendar()
    choice, reason = body.get("choice"), str(body.get("reason") or "")
    return_in = body.get("return_in") if choice == "not_now" else None
    with audited(conn), conn.transaction():
        idea = load_idea(conn, ref, lock=True)
        refuse_own(conn, user_id, idea, "decide")
        ensure_on_desk(idea)
        sharer = person_by_code(conn, idea["contributor_code"])
        errors = check_decision(choice, reason, return_in, sharer.first_name, p)
        if errors:
            raise _refused(errors[0])
        notes = wording_check(reason)
        if notes and not body.get("wording_ok"):
            words = ", ".join(f"“{n.word}”" for n in notes)
            raise Refused(
                422, "wording_check",
                f"{sharer.first_name} reads this word for word. The product never says {words}: "
                f"{notes[0].suggestion}. Send it anyway if you mean it.",
                "reason",
            )  # fmt: skip
        joined = None
        if choice == "pick" and body.get("joined_with"):
            other = conn.execute(
                "SELECT id, status FROM ideas WHERE idea_id = %s", (str(body["joined_with"]),)
            ).fetchone()
            if (
                other is None
                or other["id"] == idea["id"]
                or other["status"] in ("draft", "withdrawn", "merged")
            ):
                raise Refused(
                    422, "joined_with_invalid", "Choose a similar idea that is still open.", "joined_with"
                )
            joined = other["id"]
        dates = dates_for(choice, t, return_in, p, cal)  # type: ignore[arg-type]
        masked, _ = adapters.hide(conn, str(idea["id"]), reason.strip())
        decision_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO idea_decisions (id, idea_uuid, choice, reason_encrypted, by_user_id, at, joined_with, "
            "return_in, return_at, team_by) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (decision_id, idea["id"], choice, seal(masked, "idea_decisions", "reason_encrypted", decision_id),
             user_id, t, joined, (return_in or p.return_default) if choice == "not_now" else None,
             dates.return_at, dates.team_by),
        )  # fmt: skip
        w = open_window(t, p)
        conn.execute(
            "INSERT INTO decision_windows (decision_id, opens_at, closes_at, max_closes_at) VALUES (%s, %s, %s, %s)",
            (decision_id, w.opens_at, w.closes_at, w.max_closes_at),
        )
        conn.execute(
            "UPDATE ideas SET status = %s, reviewer_id = coalesce(reviewer_id, %s), opened_at = coalesce(opened_at, %s), "
            "opened_by = coalesce(opened_by, %s), edit_closes_at = least(coalesce(edit_closes_at, %s), %s) WHERE id = %s",
            (STATUS_AFTER[str(choice)], user_id, t, user_id, t, t, idea["id"]),
        )
        # rules/10: open question sets close; queued ones were never sent and are dropped (L-REVIEW.panel)
        conn.execute("DELETE FROM question_sets WHERE idea_uuid = %s AND state = 'queued'", (idea["id"],))
        closed = conn.execute(
            "UPDATE question_sets SET state = 'closed', closed_at = %s WHERE idea_uuid = %s AND state <> 'closed' "
            "RETURNING id",
            (t, idea["id"]),
        ).fetchall()
        for (
            done
        ) in closed:  # L-INBOX.rules/3: the questions leave the sharer's Needs you with their reminders
            adapters.resolve(conn, adapters.questions_key(str(done["id"])))
        adapters.say(conn, str(idea["id"]), "desk.decided", author_user_id=user_id,
                     payload={"decision_id": decision_id, "choice": str(choice)}, at=t)  # fmt: skip
        adapters.tell(  # L-INBOX.kinds: a decision goes to the sharer and the crew
            conn, "decision", sharers_and_crew(conn, idea), idea_uuid=str(idea["id"]), sender=user_id,
            actions=[("See the decision", f"/ideas/{idea['idea_id']}", "primary")],
            refs={"decision_id": decision_id, "choice": str(choice)},
        )  # fmt: skip
        if dates.return_at:
            adapters.schedule(conn, "desk.not_now_return", f"idea:{idea['id']}", dates.return_at)
        adapters.schedule(conn, "committee.window_close", f"decision:{decision_id}", w.closes_at)
        audit(conn, actor(user_id), "desk.decide", f"idea:{idea['idea_id']}",
              before={"status": idea["status"]},
              after={"decision_id": decision_id, "choice": str(choice), "return_in": return_in,
                     "joined_with": str(joined) if joined else None})  # fmt: skip
        return {
            "id": decision_id, "idea_id": idea["idea_id"], "choice": choice, "label": LABELS[str(choice)],
            "reason": masked, "at": t.isoformat(), "return_at": dates.return_at.isoformat() if dates.return_at else None,
            "team_by": dates.team_by.isoformat() if dates.team_by else None,
            "window": {"state": "open", "opens_at": w.opens_at.isoformat(), "closes_at": w.closes_at.isoformat(),
                       "max_closes_at": w.max_closes_at.isoformat(), "extended_times": 0},
        }  # fmt: skip


def return_from_not_now(conn: Any, idea_uuid: str, at: dt.datetime | None = None) -> bool:
    """Timer handler (lane A's engine calls it on the return date): Not now comes back to "To review"
    (L-DECIDE.rules/7). A decision reversed since then, or an idea that moved on, is left alone."""
    t = at or now()
    with conn.transaction():
        idea = conn.execute("SELECT * FROM ideas WHERE id = %s FOR UPDATE", (idea_uuid,)).fetchone()
        if idea is None or idea["status"] != "not_now":
            return False
        latest = conn.execute(
            "SELECT d.return_at, r.return_at AS reversed_return FROM idea_decisions d "
            "JOIN decision_windows w ON w.decision_id = d.id LEFT JOIN decision_reversals r ON r.window_id = w.id "
            "WHERE d.idea_uuid = %s ORDER BY d.at DESC LIMIT 1",
            (idea_uuid,),
        ).fetchone()
        due = latest and (latest["reversed_return"] or latest["return_at"])
        if due is None or due > t:
            return False
        decide = clock.decide_by(t, promises.get(), clock.office_calendar())
        conn.execute(
            "UPDATE ideas SET status = 'with_review_desk', decide_by = %s, opened_at = NULL, opened_by = NULL "
            "WHERE id = %s",
            (decide, idea_uuid),
        )
        adapters.say(conn, idea_uuid, "desk.back_from_not_now", at=t)
        return True
