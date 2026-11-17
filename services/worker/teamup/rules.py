"""The rules and words of team-up and merge requests that need no database (L-TEAMUP, L-MERGE.request, S-H2B,
C-SHEET-TEAMUP).

Words are the boards' (`1pc-handoff/reference/copy/CrewRequest.md`, `Review.md`, `Idea.md`, `Crew.md`), with
BLD-E008 applied: no gendered pronoun for a real person, so "she", "her" become the first name, or "they", "their"
where the name would repeat. Each changed line is listed in `docs/hr-wording/lane-f.md`. Lines the boards do not
draw are marked NOT DRAWN and recorded in `docs/DECISIONS.md` (BLD-F017).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Literal
from zoneinfo import ZoneInfo

from onepc.enums import labels

Answer = Literal["merge", "team_only", "decline"]
Kind = Literal[
    "teamup", "merge"
]  # a team-up request on a shared idea, or a draft merge request (L-MERGE.request)

ANSWERS: tuple[Answer, ...] = ("merge", "team_only", "decline")
NOTE_MAX = 600  # V-FIELDS.teamup/1 (600 is the pack's default)
REASON_MAX = 280  # NOT DRAWN (S-H2B.rules/1): the same limit as the withdraw reason, V-FIELDS.submit/16
IST = ZoneInfo("Asia/Kolkata")

# E-ENUMS.teamup: what each answer makes of the request, per table.
TEAMUP_STATE_FOR: dict[Answer, str] = {
    "merge": "approved_merged",
    "team_only": "approved_team_only",
    "decline": "declined",
}
MERGE_STATE_FOR: dict[Answer, str] = {"merge": "accepted", "team_only": "team_only", "decline": "declined"}
WAITING: dict[Kind, str] = {"teamup": "sent", "merge": "waiting"}
# A draft merge request shown as a TeamUpRequest (the lead's reader uses one shape for both).
AS_TEAMUP_STATE: dict[str, str] = {
    "none": "sent",
    "waiting": "sent",
    "accepted": "approved_merged",
    "team_only": "approved_team_only",
    "declined": "declined",
    "withdrawn": "withdrawn",
}


@dataclass(frozen=True)
class Problem:
    code: str
    message: str
    field: str
    status: int = 422


def check_note(note: str, min_chars: int) -> Problem | None:
    """V-FIELDS.teamup/1 and V-FIELDS.submit/11: at least `min_chars` (30), up to 600."""
    n = len(note.strip())
    if n < min_chars:
        return Problem("note_too_short", f"Add a little more: at least {min_chars} characters.", "note")
    if n > NOTE_MAX:
        return Problem("note_too_long", f"Keep your note to {NOTE_MAX} characters.", "note")  # NOT DRAWN
    return None


def check_reason(reason: str) -> Problem | None:
    if len(reason.strip()) > REASON_MAX:
        return Problem(
            "reason_too_long", f"Keep the reason to {REASON_MAX} characters.", "reason"
        )  # NOT DRAWN
    return None


def answers_for(brings: bool) -> list[dict[str, str]]:
    """S-H2B.reader/5 and rules/3: in this order, Decline (text), Team up only (line), Merge it (primary); with
    nothing brought, Decline and Approve (= team up only, L-TEAMUP.rules/6)."""
    if not brings:
        return [
            {"answer": "decline", "label": "Decline", "style": "text"},
            {"answer": "team_only", "label": "Approve", "style": "primary"},
        ]
    return [
        {"answer": "decline", "label": "Decline", "style": "text"},
        {"answer": "team_only", "label": "Team up only", "style": "line"},
        {"answer": "merge", "label": "Merge it", "style": "primary"},
    ]


def quoted(reason: str) -> str:
    """A reason in curly quotes, closed with a full stop unless it ends with its own, as the boards print both:
    “The crew is full for now”. and “… Better as two.”"""
    return f"“{reason}”" + ("" if reason.rstrip().endswith((".", "!", "?")) else ".")


# --- C-SHEET-TEAMUP.compose/3: the pre-filled note ------------------------------------------------------------
def draft_note(*, area: str | None, role: str | None, closest_title: str | None) -> str:
    """L-TEAMUP.rules/2: a first draft from the person's own closest idea and their role. No model is called
    (lane F's scope has no AI), so this is a fixed template filled with that idea's title and the role (BLD-F011).
    Always 30 characters or more, so the sheet opens with a note that can be sent."""
    parts: list[str] = []
    if area and role:
        parts.append(f"I’m in {area} ({role}).")
    elif area:
        parts.append(f"I’m in {area}.")
    elif role:
        parts.append(f"My role is {role}.")
    if closest_title:
        parts.append(
            f"I shared “{closest_title}”, which is close to yours, and I can bring what I learned from it."
        )
    else:
        parts.append("This touches my work, and I can help shape and test the fix.")
    return " ".join(parts)


# --- S-H2B.reader: the lead's Inbox reader ---------------------------------------------------------------------
def reader_words(name: str, first: str, brought: int) -> dict[str, str]:
    """The reader's own words for this request. `brought` counts the ideas brought (a draft merge request brings
    one). BLD-E008: "her idea", "Her note", "she asks", "Open her idea" use the first name or "their"."""
    if brought == 0:  # NOT DRAWN: the board draws a merge request only (S-H2B.rules/3 names the buttons)
        return {
            "kind": "Team-up request",
            "line": f"{name} asks to team up",
            "note_heading": f"{first}’s note",
            "explain": f"Approve, and {first} joins your crew. Decline, and they see your reason if you give one.",
        }
    ideas = "ideas" if brought > 1 else "idea"
    return {
        "kind": "Merge request",
        "line": f"{name} asks to team up and merge their {ideas} into yours",
        "note_heading": f"{first}’s note",
        "brought_heading": f"The {ideas} {first} asks you to merge into yours",
        "open_label": f"Open {first}’s idea",
        "explain": (
            f"Merge it, and {first}’s {ideas} {'join' if brought > 1 else 'joins'} yours: they are on your crew "
            f"and credited on it. Team up only puts {first} on your crew and keeps their {ideas} separate. "
            "Decline, and they send theirs on its own, with your reason if you give one."
        ),
    }


def lead_result(answer: Answer, first: str, brought: int, reason: str | None) -> dict[str, str]:
    """S-H2B.states, the line the lead's reader shows in place after answering (no Undo, S-H2B.rules/2).
    `state` is the board's tweak: merged, teamed_up, declined."""
    if answer == "merge":
        is_are = "are" if brought > 1 else "is"
        ideas = "ideas" if brought > 1 else "idea"
        text = (f"Merged. {first}’s {ideas} {is_are} now part of yours, and they are on your crew, credited. "
                "We’ve told them.")  # fmt: skip
        return {"state": "merged", "text": text}
    if answer == "team_only":
        if brought == 0:  # NOT DRAWN: Approve with nothing brought
            return {"state": "teamed_up", "text": f"Teamed up. {first} is on your crew. We’ve told them."}
        stays = (
            "Their ideas stay separate, and they send them on their own."
            if brought > 1
            else "Their idea stays separate, and they send it on its own."
        )
        return {"state": "teamed_up", "text": f"Teamed up. {first} is on your crew. {stays} We’ve told them."}
    told = (
        f"{first} sees your reason: {quoted(reason)}" if reason else f"We’ve told {first}."
    )  # no reason: NOT DRAWN
    tail = " They can send theirs on its own." if brought else ""
    return {"state": "declined", "text": f"Declined. {told}{tail}"}


def say_hello(first: str, lead_ref: str) -> dict[str, str]:
    """S-H2B.states: "Say hello to {requester}" opens the lead idea's conversation (S-08)."""
    return {"label": f"Say hello to {first}", "to": f"/ideas/{lead_ref}/conversation"}


# --- What the requester sees: C-SHEET-TEAMUP.after, and L-MERGE.request/4–8 on Check it ------------------------
def requester_after(
    state: str, *, lead_first: str, lead_ref: str, reason: str | None, brought: int
) -> dict[str, object] | None:
    """C-SHEET-TEAMUP.after for a team-up request, by its E-ENUMS.teamup state. None means "back to Team up"."""
    if state == "sent":
        return {"state": "waiting", "line": f"Waiting for {lead_first}",
                "detail": f"{lead_first} reads your note, then approves or declines. You’ll hear in your Inbox.",
                "action": {"label": "Withdraw", "op": "withdraw"}}  # fmt: skip
    if state == "approved_team_only":
        return {"state": "on_crew", "line": "You’re on the crew. You’ll get its updates.",
                "action": {"label": "Say hello", "to": f"/ideas/{lead_ref}/conversation"}}  # fmt: skip
    if state == "approved_merged":
        return {"state": "merged", "line": f"Merged into {lead_ref}, with credit to you.",
                "action": {"label": "Say hello", "to": f"/ideas/{lead_ref}/conversation"}}  # fmt: skip
    if state == "declined":  # NOT DRAWN: "The lead's reason if given; the person can send theirs on its own"
        said = f"{lead_first} declined: {quoted(reason)}" if reason else f"{lead_first} declined."
        return {"state": "declined", "line": said + (" Send yours on its own." if brought else ""),
                "action": None}  # fmt: skip
    return None  # withdrawn or closed: back to "Team up"


def draft_after(
    state: str, *, lead_first: str, lead_ref: str, reason: str | None
) -> dict[str, object] | None:
    """L-MERGE.request/4–8, the Similar ideas part and the bar on Check it (Review board, `merge` tweak)."""
    if state == "waiting":
        return {
            "state": "waiting",
            "label": f"Waiting on {lead_first} to merge",
            "line": f"Waiting for {lead_first} to accept the merge. If {lead_first} declines, you can send yours "
            "on its own.",
            "action": {"label": "Withdraw the request", "op": "withdraw"},
            "can_submit": False,
        }
    if state == "accepted":
        return {
            "state": "accepted",
            "label": f"Merged into {lead_ref}",
            "line": f"{lead_first} accepted. Yours is now part of {lead_ref}, with credit to you. "
            "Nothing else to send.",
            "action": {"label": "See the merged idea", "to": f"/ideas/{lead_ref}"},
            "can_submit": False,
        }
    if state == "team_only":  # NOT DRAWN on the board: L-MERGE.request/6
        return {
            "state": "team_only",
            "label": "You’re on the crew",
            "line": "You’re on the crew. You’ll get its updates. Send yours on its own.",
            "action": None,
            "can_submit": True,
        }
    if state == "declined":
        # no reason: NOT DRAWN
        said = (
            f"{lead_first} kept that idea separate: {quoted(reason)}"
            if reason
            else f"{lead_first} kept that idea separate."
        )
        return {
            "state": "declined",
            "label": f"{lead_first} kept it separate",
            "line": f"{said} Send yours on its own.",
            "action": {"label": "Send mine on its own", "op": "submit"},
            "can_submit": True,
        }
    return None  # withdrawn: the draft is back to normal (L-MERGE.request/8)


# --- Small labels ----------------------------------------------------------------------------------------------
def status_meta(ref: str, status: str) -> str:
    """C-SHEET-TEAMUP.compose/4: "IDEA-2026-001481, with the review desk"."""
    label = labels("idea_status").get(status, status)
    return f"{ref}, {label[:1].lower()}{label[1:]}"


def shared_label(at: dt.datetime | None, now: dt.datetime) -> str:
    """ "Shared Saturday." in office time (S-H2B.reader/3): today, yesterday, a weekday this week, else the date."""
    if at is None:
        return ""
    day, today = at.astimezone(IST).date(), now.astimezone(IST).date()
    gap = (today - day).days
    if gap <= 0:
        return "Shared today."
    if gap == 1:
        return "Shared yesterday."
    if gap < 7:
        return f"Shared {day.strftime('%A')}."
    return f"Shared {day.day} {day.strftime('%b')}."
