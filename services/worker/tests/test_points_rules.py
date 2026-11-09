"""Points rule parsing and contributor codes (BLD-147). No database or stack: pure functions only."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from points import ledger


def test_rule_points_reads_plain_numbers_and_roles() -> None:
    assert ledger.rule_points(15) == Decimal("15")
    assert ledger.rule_points({"presenter": 3}, "presenter") == Decimal("3")
    assert ledger.rule_points({"originator": 25, "joiner": 12.5}, "joiner") == Decimal("12.5")


def test_rule_points_is_none_when_absent_or_not_a_number() -> None:
    assert ledger.rule_points(None) is None
    assert ledger.rule_points({"presenter": 3}) is None  # a role-keyed rule needs a role
    assert ledger.rule_points({"presenter": 3}, "joiner") is None
    assert ledger.rule_points("restore_forfeited") is None  # appeal_overturned restores milestones (BLD-148)
    assert ledger.rule_points(True) is None


def test_contributor_codes_accept_codes_and_member_objects_and_skip_the_rest() -> None:
    members = [
        {"contributor_code": "CTR-a1b2c3", "role": "lead"},
        "CTR-0f0f0f",
        {"contributor_code": "CTR-a1b2c3"},  # a repeat
        {"role": "sponsor"},
        "Meera",  # never a code
        None,
        {"contributor_code": "CTR-XYZ"},
    ]
    assert ledger.contributor_codes(members) == ["CTR-a1b2c3", "CTR-0f0f0f"]
    assert ledger.contributor_codes(None) == []


def test_nothing_is_coming_soon_and_new_awards_have_words() -> None:
    assert ledger.COMING_SOON == []  # appeals restore milestones now (BLD-148)
    assert ledger.WORDS["presented"] and ledger.WORDS["working_group_member_shipped"]


def test_a_group_back_through_an_appeal_says_its_milestones_were_restored() -> None:
    """BLD-148: awards for a group whose decision was overturned, dated at or after the overturn, say so."""
    decided = dt.datetime(2027, 2, 3, 10, 0, tzinfo=dt.UTC)
    restored = {"CL-9123": decided}
    assert ledger.label("shortlisted", "CL-9123", decided, restored) == "Shortlisted" + ledger.RESTORED
    # The stage-history row and decided_at come from one transaction: a moment either side still counts.
    assert ledger.label("accepted", "CL-9123", decided - dt.timedelta(seconds=1), restored).endswith(
        ledger.RESTORED
    )
    # Milestones from before the decline, other groups and awards with no group read as usual.
    assert ledger.label("shortlisted", "CL-9123", decided - dt.timedelta(days=30), restored) == "Shortlisted"
    assert ledger.label("shortlisted", "CL-9999", decided, restored) == "Shortlisted"
    assert ledger.label("submission", None, decided, restored) == "You shared an idea"
    assert ledger.label("unknown_rule", None, decided, {}) == "Points"
