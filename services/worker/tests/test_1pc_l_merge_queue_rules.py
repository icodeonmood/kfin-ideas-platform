"""L-MERGE.desk and L-REVIEW.queue without a database (V-ACC.review/12–13 words and defaults; S-R1.layout)."""

from __future__ import annotations

import datetime as dt

from desk import merge, queue
from desk.merge import Side
from desk.promises import DEFAULTS as P
from desk.questions import SetFacts
from desk.queue import DeskIdea, Reversal
from desk.window import open_window

IST = queue.when.IST


def at(d: int, h: int = 0, mi: int = 0, m: int = 11) -> dt.datetime:
    return dt.datetime(2026, m, d, h, mi, tzinfo=IST)


NOW = at(16, 13, 20)
KAVYA = Side("IDEA-2026-001481", "with_review_desk", at(14, 10), "Kavya", 1)
RAVI = Side("IDEA-2026-001412", "with_review_desk", at(2, 15), "Ravi", 4)


def test_L_MERGE_desk_2_the_idea_shared_first_leads_by_default() -> None:
    assert merge.default_lead(KAVYA, RAVI) == "other"
    assert merge.default_lead(RAVI, KAVYA) == "this"
    same = Side("IDEA-2026-001500", "with_review_desk", KAVYA.shared_at, "Arjun", 3)
    assert merge.default_lead(KAVYA, same) == "other"  # same moment: the larger crew
    assert merge.default_lead(same, KAVYA) == "this"


def test_L_MERGE_desk_5_who_can_join_and_who_can_lead() -> None:
    assert merge.refusal(KAVYA, RAVI, "other") is None
    picked = Side(RAVI.idea_id, "picked", RAVI.shared_at, "Ravi", 4)
    assert merge.refusal(KAVYA, picked, "other") is None  # joined with an idea being taken forward
    assert merge.refusal(KAVYA, picked, "this") == "other_not_open"  # a picked idea does not join another
    decided = Side(KAVYA.idea_id, "not_picked", KAVYA.shared_at, "Kavya", 1)
    assert merge.refusal(decided, RAVI, "other") == "already_decided"
    assert merge.refusal(KAVYA, KAVYA, "other") == "same_idea"


def test_V_ACC_review_12_a_short_note_is_refused() -> None:
    assert [e.message for e in merge.check_note("Same thing", P)] == ["Tell both why, in a line or two."]
    assert merge.check_note(merge.NOTE_PREFILL, P) == []


def test_C_SHEET_MERGE_anatomy_words_follow_the_choice() -> None:
    s = merge.sheet(KAVYA, RAVI, "other", NOW)
    assert s.title == "Merge with IDEA-2026-001412?"
    assert (
        s.line
        == "Kavya’s idea joins Ravi’s. Both stay credited, and from now on the review desk decides on one idea."
    )
    assert s.other_option == ("Ravi’s leads, IDEA-2026-001412", "Shared 2 November, 4 on its crew")
    assert s.this_option == ("Kavya’s leads, IDEA-2026-001481", "Shared Saturday, just Kavya so far")
    assert s.team_up == "Kavya joins Ravi’s crew without a request. Both are told why."
    assert merge.sheet(KAVYA, RAVI, "this", NOW).line.startswith("Ravi’s idea joins Kavya’s.")


def test_C_SHEET_MERGE_after_the_banner() -> None:
    assert merge.banner(KAVYA, RAVI, "other", True) == (
        "Merged: Kavya’s idea is now part of IDEA-2026-001412, and both are credited. Kavya is on Ravi’s crew. "
        "Both were told in their Inbox. The Ones Committee can reverse it within 30 days."
    )
    assert "crew" not in merge.banner(KAVYA, RAVI, "other", False)


def idea(n: int, **kw: object) -> DeskIdea:
    base: dict[str, object] = dict(
        idea_id=f"IDEA-2026-00{n}", title=f"Idea {n}", sharer_name="Divya Shah", sharer_first_name="Divya",
        area="Investor service", city="Chennai", status="with_review_desk", decide_by=at(20, 18),
    )  # fmt: skip
    base.update(kw)
    return DeskIdea(**base)  # type: ignore[arg-type]


WAITING = idea(1, questions=SetFacts(3, 0, at(16, 11, 20), at(16, 12, 5), at(19, 18), None))
URGENT = idea(2, questions=SetFacts(2, 0, at(15, 9), at(15, 10), at(16, 21, 0), None), area="Operations")
LATE = idea(3, questions=SetFacts(1, 0, at(13, 9), None, at(16, 8, 20), None))
BACK = idea(4, questions=SetFacts(2, 2, at(13, 9), at(13, 10), at(16, 18), at(16, 12, 20)))
FRESH = idea(5, decide_by=at(22, 18))
DECIDED = idea(
    6,
    status="picked",
    decision="pick",
    decided_at=at(12, 15),
    window=open_window(at(12, 15), P),
    decide_by=at(18, 18),
)
REVERSED = idea(7, status="picked", decision="not_now", decided_at=at(11, 10), window=None,
                reversal=Reversal("pick", at(13, 11)))  # fmt: skip
OLD = idea(8, status="picked", decision="pick", decided_at=at(1, 10))
ALL = [WAITING, URGENT, LATE, BACK, FRESH, DECIDED, REVERSED, OLD]


def test_L_REVIEW_queue_each_idea_sits_on_one_tab() -> None:
    tabs = {i.idea_id[-1]: queue.tab_of(i, NOW, P.decided_this_week_days) for i in ALL}
    assert tabs == {"1": "waiting", "2": "waiting", "3": "waiting", "4": "answered", "5": "to_review",
                    "6": "decided", "7": "decided", "8": None}  # fmt: skip
    assert queue.counts(ALL, NOW, 7) == {"to_review": 1, "waiting": 3, "answered": 1, "decided": 2}


def test_S_R1_layout_1_the_summary_sentence() -> None:
    assert queue.summary(ALL, NOW, 7) == (
        "3 waiting on colleagues. One is overdue and one has under a day left. 1 answered and back with you."
    )
    assert queue.summary([FRESH], NOW, 7) == "1 idea to review."
    assert queue.summary([], NOW, 7) == "Nothing to review."


def test_S_R1_layout_4_rows_and_actions() -> None:
    r = queue.row(WAITING, "waiting", NOW)
    assert (r.who, r.questions, r.time_left, r.variant, r.decide_by, r.action) == (
        "Divya Shah, Investor service, Chennai", "0 of 3 answered, seen 12:05 pm", "3 days to answer", "normal",
        "Friday 20 November", "Open",
    )  # fmt: skip
    r = queue.row(LATE, "waiting", NOW)
    assert (r.questions, r.time_left, r.variant, r.action, r.action_kind) == (
        "Not seen yet", "Overdue by 5 hours", "bad", "Remind Divya", "remind"
    )  # fmt: skip
    r = queue.row(URGENT, "waiting", NOW)
    assert (r.time_left, r.variant) == ("07:40 to answer", "warn")
    r = queue.row(BACK, "answered", NOW)
    assert (r.questions, r.time_left, r.action) == (
        "Both answered, 1 hour ago",
        "4 days to decide",
        "Read answers",
    )
    r = queue.row(FRESH, "to_review", NOW)
    assert (r.questions, r.time_left) == ("No questions asked", "6 days to decide")


def test_S_R1_layout_5_decided_this_week_rows() -> None:
    r = queue.row(DECIDED, "decided", NOW)
    assert (r.decision, r.committee) == (
        "Picked, 12 November",
        "Ones Committee can review it until Saturday 12 December",
    )
    r = queue.row(REVERSED, "decided", NOW)
    assert (r.decision, r.committee) == (
        "Reversed: picked", "The Ones Committee picked it on 13 November, with a note to Divya"
    )  # fmt: skip


def test_S_R1_rules_1_sorting() -> None:
    rows = [queue.row(i, "waiting", NOW) for i in (WAITING, URGENT, LATE)]
    assert [r.idea_id[-1] for r in queue.sort_rows(rows, "waiting", "time_left")] == ["3", "2", "1"]
    assert [r.idea_id[-1] for r in queue.sort_rows(rows, "waiting", "area")] == ["3", "1", "2"]
    decided = [queue.row(i, "decided", NOW) for i in (REVERSED, DECIDED)]
    assert [r.idea_id[-1] for r in queue.sort_rows(decided, "decided", "time_left")] == ["6", "7"]
