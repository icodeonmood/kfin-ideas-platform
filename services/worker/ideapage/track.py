"""The five-stage track for one idea (C-TRACK, E-ENUMS.idea-status 'Stage on the track'), with the detail line
under each node as the boards write it (reference/copy/Status.md, Idea.md).

The sharer's track says more than a colleague's: the questions waiting for them, the reviewer having their
answers, how many personal details were hidden. A colleague sees the stage, the dates and how many similar ideas
are linked, never the decision's reason or who decided beyond the stage (P-PRODUCT.privacy, S-09.rules/1).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any

from core.db import Conn
from ideapage import adapters, read
from ideapage.adapters import SimilarStatus
from ideapage.words import DECISION_LABEL, Node, count, day, when_shared
from sla.calendar import add_working_days

STATUS_OF_CHOICE = {"pick": "picked", "not_now": "not_now", "not_picked": "not_picked"}
KIND_WORDS = {
    "folio": "folio number",
    "pan": "PAN",
    "phone": "phone number",
    "email": "email address",
    "account": "account number",
    "aadhaar": "Aadhaar number",
    "name": "name",
}


@dataclass
class Decided:
    """The decision as it stands now: the desk's, or the committee's reversal of it (final)."""

    choice: str
    at: dt.datetime
    reason: str | None
    by_user_id: str
    return_at: dt.datetime | None
    team_by: dt.datetime | None
    joined_with: str | None
    window_state: str | None
    closes_at: dt.datetime | None
    reversed: bool
    desk_choice: str
    desk_at: dt.datetime
    note: str | None
    reversed_by: str | None
    reversed_at: dt.datetime | None
    raw: dict[str, Any]


def decided(d: dict[str, Any] | None) -> Decided | None:
    if d is None:
        return None
    reversed_ = d.get("reversal_id") is not None and d.get("to_choice") is not None
    choice = str(d["to_choice"] if reversed_ else d["choice"])
    team_by = d.get("team_by")
    if reversed_ and choice == "pick":
        # L-COMMITTEE.rules/5: a reversal to pick has the pick's consequences, a build team by the usual date.
        team_by = add_working_days(d["reversed_at"], int(read.promises()["team_by"]["working_days"]))
    elif reversed_:
        team_by = None
    return Decided(
        choice=choice,
        at=d["reversed_at"] if reversed_ else d["at"],
        reason=d.get("reason"),
        by_user_id=str(d["by_user_id"]),
        return_at=(d.get("reversed_return_at") if reversed_ else d.get("return_at")),
        team_by=team_by,
        joined_with=str(d["joined_with"]) if d.get("joined_with") and not reversed_ else None,
        window_state=d.get("window_state"),
        closes_at=d.get("closes_at"),
        reversed=reversed_,
        desk_choice=str(d["choice"]),
        desk_at=d["at"],
        note=d.get("note"),
        reversed_by=str(d["reversed_by"]) if d.get("reversed_by") else None,
        reversed_at=d.get("reversed_at"),
        raw=d,
    )


def reviewed_line(dec: Decided, now: dt.datetime, *, sees_reversal: bool) -> str:
    """'Picked, Monday 16 November', or 'Picked, then moved to not now by the Ones Committee'. The reversal is
    worded only for the sharer, the crew, the review desk and the Ones Committee; a colleague sees the stage as it
    stands now and its date (P-PRODUCT.privacy, DEC-104)."""
    if dec.reversed and sees_reversal:
        return (
            f"{DECISION_LABEL[dec.desk_choice]}, then moved to {DECISION_LABEL[dec.choice].lower()} "
            "by the Ones Committee"
        )
    return f"{DECISION_LABEL[dec.choice]}, {day(dec.at, now)}"


# L-SIMILAR.failure's own sentence, as lane C's `submit.check.COULDNT_CHECK` and J-SHARE's handover show it. Drawn
# for Check it; on the track (Status.md, Idea.md draw only counts) it is NOT DRAWN: HR sign-off (BLD-E052).
COULDNT_CHECK = "Couldn’t check for similar ideas. The review desk will."


def similar_words(n_similar: int, similar: SimilarStatus, *, for_sharer: bool) -> str | None:
    """The similar-ideas half of the Checked line, by whether they were checked (L-SIMILAR.failure, BLD-E052):
    linked ideas are counted whenever there are some. With none, "done" keeps the count wording, "failed" is the
    pack's couldn't-check sentence and never "none found", and "none" (nothing recorded) says nothing (None)."""
    if n_similar or similar == "done":
        if not for_sharer:
            return count(n_similar, "similar idea") + " linked"
        return count(n_similar, "similar idea") + " found" if n_similar else "no similar ideas found"
    return COULDNT_CHECK if similar == "failed" else None


def checked_line(
    n_hidden: int, kinds: list[str], n_similar: int, similar: SimilarStatus, *, for_sharer: bool
) -> str | None:
    """'Personal details hidden, 2 similar ideas found' (sharer); '3 similar ideas linked' (colleague). A check
    that failed reads 'Personal details hidden. Couldn’t check for similar ideas. The review desk will.', as lane
    C's handover composes it (`submit.send.checked_line`), so J-SHARE's end and S-06 say the same."""
    words = similar_words(n_similar, similar, for_sharer=for_sharer)
    if not for_sharer:
        return words
    if n_hidden > 1:
        first = "Personal details hidden"
    elif n_hidden == 1:
        first = f"1 {KIND_WORDS.get(kinds[0], 'detail')} hidden"
    else:
        first = "No personal details found"
    if words is None:
        return first
    return f"{first}. {words}" if words == COULDNT_CHECK else f"{first}, {words}"


def stages(
    conn: Conn,
    idea: dict[str, Any],
    now: dt.datetime,
    *,
    for_sharer: bool,
    dec: Decided | None,
    qset: dict[str, Any] | None,
    carried_into: str | None = None,
    reviewer_first: str | None = None,
    sees_reversal: bool | None = None,
) -> list[Node]:
    """Five nodes, or none for a draft or a merged idea (E-ENUMS.idea-status: 'none; links to the surviving
    idea'). `sees_reversal` (default: the sharer only) says whether the Reviewed node may say the Ones Committee
    moved the decision; the crew, the desk and the committee may, a colleague may not."""
    insider = for_sharer if sees_reversal is None else sees_reversal
    status = str(idea["status"])
    if status in ("draft", "merged") or idea["shared_at"] is None:
        return []
    uid = str(idea["id"])
    shared = Node("done", when_shared(idea["shared_at"], now), idea["shared_at"])
    if status == "checking":
        return [
            shared,
            Node("now", "Checking…"),
            Node("to_come"),
            Node("to_come", "If it’s picked"),
            Node("to_come", "Then we measure what changed"),
        ]
    # Only the details still hidden: one the sharer brought back with "Show it" is no longer hidden (L-HIDE).
    hid = [h for h in read.hidden(conn, uid) if h["state"] == "hidden"] if for_sharer else []
    checked = Node(
        "done",
        checked_line(
            len(hid),
            [str(h["kind"]) for h in hid],
            read.similar_count(conn, uid),
            adapters.similar_status(conn, uid),
            for_sharer=for_sharer,
        ),
        read.status_at(conn, uid, "with_review_desk"),
    )
    built_later = Node("to_come", "If it’s picked")
    shipped_later = Node("to_come", "Then we measure what changed")

    if status == "withdrawn":
        off = Node("not_going_ahead")
        return [shared, checked, Node("not_going_ahead", "Withdrawn before review"), off, off]

    if status in ("with_review_desk", "needs_you"):
        by = f"By {day(idea['decide_by'], now)}" if idea.get("decide_by") else None
        line = by
        if for_sharer and qset is not None:
            if read.has_open_questions(qset) and qset.get("sent_at"):
                n = len(qset["questions"])
                line = f"{count(n, 'question')} for you since {day(qset['sent_at'], now)}"
            elif qset["state"] in read.ANSWERED_SET_STATES and reviewer_first:
                # `reviewer_first` is the reviewer's first name for the review desk and the Ones Committee, and
                # "The review desk" for anyone else (DEC-111, `sharer.sharer_view`)
                line = (
                    f"{reviewer_first} has your answers. {by}"
                    if by
                    else f"{reviewer_first} has your answers."
                )
        return [shared, checked, Node("now", line), built_later, shipped_later]

    reviewed = Node(
        "done", reviewed_line(dec, now, sees_reversal=insider) if dec else None, dec.at if dec else None
    )
    if status == "picked":
        team = f"Team chosen by {day(dec.team_by, now)}" if dec and dec.team_by else None
        return [shared, checked, reviewed, Node("now", team), shipped_later]
    if status == "being_built":
        team_row = read.build_team(conn, uid)
        line = f"Being built: {team_row['name']}" if team_row else "Being built"
        return [
            shared,
            checked,
            reviewed,
            Node("now", line, read.status_at(conn, uid, "being_built")),
            shipped_later,
        ]
    if status == "shipped":
        at = read.status_at(conn, uid, "shipped")
        on = day(at, now) if at else None
        return [
            shared,
            checked,
            reviewed,
            Node("done", f"Built, {on}" if on else None, at),
            Node("done", f"Live since {on}" if on else None, at),
        ]
    if status == "not_now":
        back = f"Looked at again on {day(dec.return_at, now)}" if dec and dec.return_at else None
        return [shared, checked, reviewed, Node("to_come", back), shipped_later]
    if status == "not_picked":
        if carried_into:
            return [
                shared,
                checked,
                reviewed,
                Node("not_going_ahead", "Not going ahead on its own"),
                Node("not_going_ahead", f"Carries on in {carried_into}"),
            ]
        return [shared, checked, reviewed, Node("not_going_ahead"), Node("not_going_ahead")]
    return [shared, checked, Node("now"), built_later, shipped_later]
