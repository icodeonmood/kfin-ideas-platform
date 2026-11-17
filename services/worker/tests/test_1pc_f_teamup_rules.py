"""L-TEAMUP and L-MERGE.request rules and words that need no database: the note, the answers, the pre-filled
note, and the exact copy of S-H2B.states, C-SHEET-TEAMUP.after and the Review board's merge states, with BLD-E008
applied (no gendered pronoun for a real person)."""

from __future__ import annotations

import datetime as dt
import re

import pytest

from teamup import rules

PRONOUN = re.compile(r"\b(she|her|hers|he|him|his)\b", re.IGNORECASE)


def test_L_TEAMUP_rules_2_the_note_needs_30_characters_and_at_most_600() -> None:
    short = rules.check_note("x" * 29, 30)
    assert short is not None and (short.code, short.field) == ("note_too_short", "note")
    assert short.message == "Add a little more: at least 30 characters."
    assert rules.check_note("  " + "x" * 30 + "  ", 30) is None
    long = rules.check_note("x" * 601, 30)
    assert long is not None and long.code == "note_too_long"


def test_L_TEAMUP_rules_2_the_pre_filled_note_comes_from_the_closest_idea_and_role() -> None:
    note = rules.draft_note(area="Investor service", role="Senior executive", closest_title="R07 SMS calls")
    assert note == (
        "I’m in Investor service (Senior executive). I shared “R07 SMS calls”, which is close to yours, "
        "and I can bring what I learned from it."
    )
    bare = rules.draft_note(area=None, role=None, closest_title=None)
    assert len(bare) >= 30 and "“" not in bare


def test_V_ACC_teamup_5_the_answers_are_decline_team_up_only_merge_it_in_that_order() -> None:
    assert [a["label"] for a in rules.answers_for(True)] == ["Decline", "Team up only", "Merge it"]
    assert [a["style"] for a in rules.answers_for(True)] == ["text", "line", "primary"]


def test_L_TEAMUP_rules_6_with_nothing_brought_the_answers_are_decline_and_approve() -> None:
    answers = rules.answers_for(False)
    assert [(a["label"], a["answer"]) for a in answers] == [("Decline", "decline"), ("Approve", "team_only")]


def test_S_H2B_states_the_lead_result_lines_follow_the_board_with_BLD_E008() -> None:
    assert rules.lead_result("merge", "Kavya", 1, None) == {
        "state": "merged",
        "text": "Merged. Kavya’s idea is now part of yours, and they are on your crew, credited. We’ve told them.",
    }
    assert rules.lead_result("team_only", "Kavya", 1, None)["text"] == (
        "Teamed up. Kavya is on your crew. Their idea stays separate, and they send it on its own. We’ve told them."
    )
    assert rules.lead_result("decline", "Kavya", 1, "The crew is full for now")["text"] == (
        "Declined. Kavya sees your reason: “The crew is full for now”. They can send theirs on its own."
    )
    assert rules.say_hello("Kavya", "IDEA-2026-001412") == {
        "label": "Say hello to Kavya",
        "to": "/ideas/IDEA-2026-001412/conversation",
    }


@pytest.mark.parametrize("brought", [0, 1, 2])
def test_BLD_E008_no_gendered_pronoun_in_any_line_lane_F_writes(brought: int) -> None:
    lines: list[str] = []
    for ans in rules.ANSWERS:
        lines.append(rules.lead_result(ans, "Kavya", brought, "Full for now")["text"])
        lines.append(rules.lead_result(ans, "Kavya", brought, None)["text"])
    lines += list(rules.reader_words("Kavya Menon", "Kavya", brought).values())
    for state in ("sent", "approved_team_only", "approved_merged", "declined"):
        after = rules.requester_after(state, lead_first="Ravi", lead_ref="IDEA-2026-001412", reason="x", brought=brought)
        assert after is not None
        lines.append(str(after["line"]))
    for state in ("waiting", "accepted", "team_only", "declined"):
        after = rules.draft_after(state, lead_first="Ravi", lead_ref="IDEA-2026-001412", reason="x")
        assert after is not None
        lines += [str(after["label"]), str(after["line"])]
    assert [line for line in lines if PRONOUN.search(line)] == []


def test_S_H2B_reader_words_for_a_merge_request() -> None:
    words = rules.reader_words("Kavya Menon", "Kavya", 1)
    assert words["kind"] == "Merge request"
    assert words["line"] == "Kavya Menon asks to team up and merge their idea into yours"
    assert words["open_label"] == "Open Kavya’s idea"
    assert rules.reader_words("Kavya Menon", "Kavya", 0)["kind"] == "Team-up request"


def test_C_SHEET_TEAMUP_after_waiting_and_approved() -> None:
    waiting = rules.requester_after("sent", lead_first="Ravi", lead_ref="IDEA-2026-001412", reason=None, brought=0)
    assert waiting is not None and waiting["line"] == "Waiting for Ravi"
    assert waiting["action"] == {"label": "Withdraw", "op": "withdraw"}
    on = rules.requester_after("approved_team_only", lead_first="Ravi", lead_ref="IDEA-2026-001412", reason=None,
                               brought=0)  # fmt: skip
    assert on is not None and on["line"] == "You’re on the crew. You’ll get its updates."
    merged = rules.requester_after("approved_merged", lead_first="Ravi", lead_ref="IDEA-2026-001412", reason=None,
                                   brought=1)  # fmt: skip
    assert merged is not None and merged["line"] == "Merged into IDEA-2026-001412, with credit to you."
    assert rules.requester_after("withdrawn", lead_first="Ravi", lead_ref="x", reason=None, brought=0) is None


def test_L_MERGE_request_4_to_7_the_Check_it_words_match_the_Review_board() -> None:
    w = rules.draft_after("waiting", lead_first="Ravi", lead_ref="IDEA-2026-001412", reason=None)
    assert w is not None and w["label"] == "Waiting on Ravi to merge" and w["can_submit"] is False
    assert w["line"] == "Waiting for Ravi to accept the merge. If Ravi declines, you can send yours on its own."
    assert w["action"] == {"label": "Withdraw the request", "op": "withdraw"}
    a = rules.draft_after("accepted", lead_first="Ravi", lead_ref="IDEA-2026-001412", reason=None)
    assert a is not None and a["label"] == "Merged into IDEA-2026-001412"
    assert a["line"] == "Ravi accepted. Yours is now part of IDEA-2026-001412, with credit to you. Nothing else to send."
    assert a["action"] == {"label": "See the merged idea", "to": "/ideas/IDEA-2026-001412"}
    reason = "Mine is about the SMS wording, yours is about the calls it causes. Better as two."
    d = rules.draft_after("declined", lead_first="Ravi", lead_ref="IDEA-2026-001412", reason=reason)
    assert d is not None and d["label"] == "Ravi kept it separate"
    assert d["line"] == f"Ravi kept that idea separate: “{reason}” Send yours on its own."
    assert d["action"] == {"label": "Send mine on its own", "op": "submit"} and d["can_submit"] is True
    t = rules.draft_after("team_only", lead_first="Ravi", lead_ref="IDEA-2026-001412", reason=None)
    assert t is not None and t["can_submit"] is True
    assert rules.draft_after("withdrawn", lead_first="Ravi", lead_ref="x", reason=None) is None


def test_small_labels() -> None:
    assert rules.status_meta("IDEA-2026-001481", "with_review_desk") == "IDEA-2026-001481, with the review desk"
    now = dt.datetime(2026, 11, 17, 9, 0, tzinfo=dt.UTC)
    assert rules.shared_label(dt.datetime(2026, 11, 14, 6, 0, tzinfo=dt.UTC), now) == "Shared Saturday."
    assert rules.shared_label(dt.datetime(2026, 11, 17, 4, 0, tzinfo=dt.UTC), now) == "Shared today."
    assert rules.shared_label(dt.datetime(2026, 11, 2, 4, 0, tzinfo=dt.UTC), now) == "Shared 2 Nov."
