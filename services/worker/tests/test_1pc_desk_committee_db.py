"""L-COMMITTEE against the database (V-ACC.committee/1–6, S-R4.layout, S-R4.rules/2–4)."""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from core.db import Conn
from desk import committee, decide
from desk.store import Refused
from tests import desk_fixtures as f
from tests.desk_fixtures import clean_up_desk_rows  # noqa: F401 (autouse: removes what the helpers made)

REASON = "Picked. A clear problem, a real number and a simple fix for the branch."
NOTE = "Right problem, but the SMS vendor changes in March. Let us look again then."
DECIDED = f.at(16, 16, 58)


@pytest.fixture
def repo(company_repo: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    from core.config import get_settings

    monkeypatch.setenv("COMPANY_REPO_PATH", str(company_repo))
    get_settings.cache_clear()
    yield company_repo
    monkeypatch.undo()
    get_settings.cache_clear()


@pytest.fixture
def cast(db: Conn, repo: Path) -> dict[str, Any]:
    kavya = f.person(db, "Kavya Menon")
    meera = f.person(db, "Meera Iyer", roles=("reviewer",))
    rohan = f.person(db, "Rohan Mehta", roles=("committee",))
    idea = f.idea(db, kavya)
    d = decide.send(db, idea["idea_id"], meera["id"], {"choice": "pick", "reason": REASON}, DECIDED)
    window = db.execute("SELECT id FROM decision_windows WHERE decision_id = %s", (d["id"],)).fetchone()
    assert window is not None
    return {
        "kavya": kavya,
        "meera": meera,
        "rohan": rohan,
        "idea": idea,
        "decision": d,
        "window": str(window["id"]),
    }


def test_V_ACC_committee_1_a_five_day_old_decision_is_listed_with_its_reason(
    db: Conn, cast: dict[str, Any]
) -> None:
    got = committee.listing(db, cast["rohan"]["id"], at=DECIDED + dt.timedelta(days=5, hours=1))
    assert got["counts"] == {"window": 1, "reversed": 0, "expired": 0}
    assert got["summary"] == "1 decision open to review."
    row = got["items"][0]
    assert row["idea"]["meta"].startswith(
        f"{cast['idea']['idea_id']}, Kavya Menon, Investor service, Hyderabad"
    )
    assert row["decision"]["label"] == "Picked" and row["decision"]["reason"] == REASON
    assert row["decision"]["by_line"] == "by Meera from the review desk, Monday 16 November"
    assert row["decision"]["reason_heading"] == "The review desk’s reason, as Kavya read it"
    assert (row["window"]["left"], row["window"]["until"]) == ("25 days left", "Until Wednesday 16 December")
    assert row["window"]["extend_to"] == "Extend to Friday 15 January 2027" and row["action"] == "Review"


def test_V_ACC_committee_2_extend_moves_the_end_30_days(db: Conn, cast: dict[str, Any]) -> None:
    row = committee.extend_window(db, cast["window"], cast["rohan"]["id"], DECIDED + dt.timedelta(days=2))
    assert (row["window"]["state"], row["window"]["extended"]) == ("extended", "Extended once")
    assert row["window"]["until"] == "Until Friday 15 January 2027"
    assert "committee.extend" in f.audit_actions(db, f"window:{cast['window']}")


def test_V_ACC_committee_3_no_extension_past_three_months(db: Conn, cast: dict[str, Any]) -> None:
    """V-ACC.committee/3, L-COMMITTEE.rules/2, S-R4.rules/2 (BLD-B263): the second extension goes to the 3-month date
    the button names, Tuesday 16 February 2027, and the stored end agrees with the label; no 2-day stub follows."""
    t = DECIDED + dt.timedelta(days=2)
    row = committee.extend_window(db, cast["window"], cast["rohan"]["id"], t)
    assert row["window"]["extend_to"] == "Extend to Tuesday 16 February 2027"
    row = committee.extend_window(db, cast["window"], cast["rohan"]["id"], t)
    stored = db.execute("SELECT closes_at, max_closes_at FROM decision_windows WHERE id = %s",
                        (cast["window"],)).fetchone()  # fmt: skip
    assert stored is not None and stored["closes_at"] == stored["max_closes_at"]
    assert (
        row["window"]["until"] == "Until Tuesday 16 February 2027"
        and row["window"]["extended"] == "Extended twice"
    )
    assert row["can_extend"] is False and row["window"]["limit_line"] == "At the 3-month limit"
    with pytest.raises(Refused) as refused:
        committee.extend_window(db, cast["window"], cast["rohan"]["id"], t)
    assert refused.value.code == "at_limit"


def test_V_ACC_committee_4_a_reversal_is_final_and_the_idea_takes_the_new_decision(
    db: Conn, cast: dict[str, Any]
) -> None:
    t = f.at(20, 11)
    row = committee.reverse_window(
        db, cast["window"], cast["rohan"]["id"], {"to": "not_now", "note": NOTE, "return_in": "3m"}, t
    )
    assert row["reversal"]["to"] == "not_now" and row["reversal"]["note"] == NOTE
    assert [row["reversal"][k] for k in ("now_line", "now_by_line", "reversed_line", "final_line")] == [
        "Now: Not now", "by Rohan Mehta, Friday 20 November", "Reversed Friday 20 November",
        "Final. Kavya has the note.",
    ]  # fmt: skip
    assert row["can_extend"] is False and row["can_reverse"] is False and row["action"] == "See it"
    status = db.execute("SELECT status FROM ideas WHERE id = %s", (cast["idea"]["id"],)).fetchone()
    assert status == {"status": "not_now"}
    got = committee.listing(db, cast["rohan"]["id"], tab="reversed", at=t)
    assert (
        got["counts"]["reversed"] == 1
        and got["summary"] == "0 decisions open to review. You reversed 1 this month."
    )
    agains: tuple[Callable[[], object], ...] = (lambda: committee.reverse_window(db, cast["window"], cast["rohan"]["id"],
                                                   {"to": "not_picked", "note": NOTE}, t),
                  lambda: committee.extend_window(db, cast["window"], cast["rohan"]["id"], t))  # fmt: skip
    for again in agains:
        with pytest.raises(Refused) as refused:
            again()
        assert refused.value.code == "already_reversed"
    assert "committee.reverse" in f.audit_actions(db, f"window:{cast['window']}")
    assert "committee.reversed" in f.events(db, cast["idea"]["id"])


def test_V_ACC_committee_5_a_window_left_alone_expires_and_the_decision_stands(
    db: Conn, cast: dict[str, Any]
) -> None:
    after = DECIDED + dt.timedelta(days=31)
    got = committee.listing(db, cast["rohan"]["id"], tab="expired", at=after)
    assert got["counts"] == {"window": 0, "reversed": 0, "expired": 1}
    assert got["items"][0]["window"]["closed_line"] == (
        "Expired Wednesday 16 December. After 30 days. The decision stands."
    )
    assert committee.close_window(db, cast["window"], after) is True
    assert committee.close_window(db, cast["window"], after) is False
    with pytest.raises(Refused) as refused:
        committee.reverse_window(
            db, cast["window"], cast["rohan"]["id"], {"to": "not_picked", "note": NOTE}, after
        )
    assert refused.value.code == "window_closed"
    status = db.execute("SELECT status FROM ideas WHERE id = %s", (cast["idea"]["id"],)).fetchone()
    assert status == {"status": "picked"}


def test_V_ACC_committee_6_a_reversal_needs_a_choice_and_a_note(db: Conn, cast: dict[str, Any]) -> None:
    for body, code in (
        ({"note": NOTE}, "to_required"),
        ({"to": "not_picked", "note": "Too short"}, "note_too_short"),
    ):
        with pytest.raises(Refused) as refused:
            committee.reverse_window(db, cast["window"], cast["rohan"]["id"], body, f.at(18, 10))
        assert refused.value.code == code
    assert db.execute("SELECT count(*) AS n FROM decision_reversals").fetchone() == {"n": 0}


def test_L_COMMITTEE_rules_9_a_member_cannot_reverse_their_own_idea(db: Conn, cast: dict[str, Any]) -> None:
    mine = f.idea(db, cast["rohan"])
    decide.send(db, mine["idea_id"], cast["meera"]["id"], {"choice": "not_picked", "reason": REASON}, DECIDED)
    rows = committee.listing(db, cast["rohan"]["id"], at=f.at(17, 9))["items"]
    by_idea = {r["idea"]["id"]: r for r in rows}
    assert (
        by_idea[mine["idea_id"]]["can_reverse"] is False
        and by_idea[cast["idea"]["idea_id"]]["can_reverse"] is True
    )
    window = db.execute(
        "SELECT w.id FROM decision_windows w JOIN idea_decisions d ON d.id = w.decision_id WHERE d.idea_uuid = %s",
        (mine["id"],),
    ).fetchone()
    assert window is not None
    with pytest.raises(Refused) as refused:
        committee.reverse_window(
            db, str(window["id"]), cast["rohan"]["id"], {"to": "pick", "note": NOTE}, f.at(17, 9)
        )
    assert refused.value.code == "own_idea"


def test_S_R4_reversing_words(db: Conn, cast: dict[str, Any]) -> None:
    w = committee.reversing_words(db, cast["window"], cast["rohan"]["id"])
    assert w["intro"].startswith(
        f"On “{cast['idea']['title']}”. The review desk said picked it. Kavya reads your note"
    )
    assert [o["to"] for o in w["options"]] == ["not_now", "not_picked"]
    assert (
        w["options"][0]["line"] == "Right problem, wrong time. It comes back to the review desk in 3 months."
    )
    assert w["send_label"] == "Reverse and tell Kavya"


def test_for_idea_gives_the_decision_with_its_window(db: Conn, cast: dict[str, Any]) -> None:
    got = committee.for_idea(db, str(cast["idea"]["id"]), cast["meera"]["id"], DECIDED)
    assert (
        got is not None and got["window"]["left"] == "30 days left" and got["decision"]["label"] == "Picked"
    )


def test_S_R4_states_tab_J_COMMITTEE_3c_closed_tabs_list_the_latest_first(
    db: Conn, cast: dict[str, Any]
) -> None:
    """S-R4.states `tab`, S-R4.layout/2, J-COMMITTEE/3c (BLD-B265). Committee.md "State: tab=Expired" draws
    Wednesday 18 November above Wednesday 11 November: the Expired tab lists the most recently expired first.
    Reversed lists the most recently reversed first. "In the window" keeps "Closing soonest". All three under the
    default sort, "Closing soonest"."""
    meera, rohan = cast["meera"]["id"], cast["rohan"]["id"]

    def decided(on: dt.datetime) -> str:
        idea = f.idea(db, cast["kavya"], shared_at=on - dt.timedelta(days=2))
        decide.send(db, idea["idea_id"], meera, {"choice": "not_picked", "reason": REASON}, on)
        return str(idea["idea_id"])

    older, newer = decided(f.at(12, 10, m=10)), decided(f.at(19, 10, m=10))  # expire 11 and 18 November
    later = decided(f.at(18, 10))  # closes Friday 18 December, after the cast's Wednesday 16 December
    at = f.at(20, 12)
    expired = committee.listing(db, rohan, tab="expired", sort="closing", at=at)["items"]
    assert [r["idea"]["id"] for r in expired] == [newer, older]
    assert [r["window"]["closed_line"] for r in expired] == [
        "Expired Wednesday 18 November. After 30 days. The decision stands.",
        "Expired Wednesday 11 November. After 30 days. The decision stands.",
    ]
    window = committee.listing(db, rohan, tab="window", at=at)["items"]
    assert [r["idea"]["id"] for r in window] == [cast["idea"]["idea_id"], later]  # closing soonest

    by_idea = {r["idea"]["id"]: r["window_id"] for r in window}
    committee.reverse_window(db, by_idea[later], rohan, {"to": "pick", "note": NOTE}, f.at(20, 12, 5))
    committee.reverse_window(
        db, by_idea[cast["idea"]["idea_id"]], rohan, {"to": "not_picked", "note": NOTE}, f.at(20, 12, 30)
    )
    reversed_ = committee.listing(db, rohan, tab="reversed", at=f.at(20, 13))["items"]
    assert [r["idea"]["id"] for r in reversed_] == [
        cast["idea"]["idea_id"],
        later,
    ]  # reversed 12:30, then 12:05
