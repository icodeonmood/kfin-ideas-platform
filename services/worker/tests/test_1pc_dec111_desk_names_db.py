"""DEC-111 (BLD-B257): a sharer, and the crew, never see the name of the person at the review desk. What lane B sends
them names "the review desk": the decision's lines and row words (L-DECIDE, S-06, Status.md), the open question set
(L-QUESTIONS, C-QCARD, S-R3), the sent answers' lines and the answers under each part. The review desk and the Ones
Committee still read each other's names, and the committee member who reversed a decision is still named.

Needs Postgres with the handoff cut-over applied (`make up`, then the tests migrate their own database).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from core.db import Conn
from desk import asking, committee, decide
from tests import desk_fixtures as f
from tests.desk_fixtures import clean_up_desk_rows  # noqa: F401 (autouse: removes what the helpers made)

SENT = f.at(16, 11, 20)  # Monday 16 November 2026, 11:20 am IST
DECIDED = f.at(16, 16, 58)  # Monday 16 November, 4:58 pm
QS: list[dict[str, Any]] = [
    {"part": "summary", "text": "Is it mostly R07, or all rejection codes?"},
    {"part": "often", "text": "Is the 40 calls a day at one branch, or across Hyderabad?"},
]
REASON = "Picked. A clear problem, a real number and a simple fix for the branch."
NOTE = "The SMS templates are frozen until the platform upgrade in January, so a team picked now would wait."


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
    kavya, farhan = f.person(db, "Kavya Menon"), f.person(db, "Farhan Shaikh")
    meera = f.person(db, "Meera Iyer", roles=("reviewer",))
    rohan = f.person(db, "Rohan Mehta", roles=("committee",))
    idea = f.idea(db, kavya)
    f.crew(db, idea, farhan)
    return {"kavya": kavya, "farhan": farhan, "meera": meera, "rohan": rohan, "idea": idea}


def _seen(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def _no_reviewer(payload: Any, cast: dict[str, Any]) -> None:
    """Not the reviewer's first name, full name, initials as a person, nor their id: not even in the JSON."""
    text = _seen(payload)
    assert "Meera" not in text and "Iyer" not in text, text
    assert cast["meera"]["id"] not in text, text
    assert '"MI"' not in text, text


def _send_set(db: Conn, cast: dict[str, Any]) -> dict[str, Any]:
    return asking.send_set(
        db, cast["idea"]["idea_id"], cast["meera"]["id"], {"questions": QS, "time_to_answer": "3d"}, SENT
    )


def test_DEC_111_L_QUESTIONS_C_QCARD_S_R3_the_sharers_set_names_the_desk_and_the_desks_keeps_the_reviewer(
    db: Conn, cast: dict[str, Any]
) -> None:
    desks = _send_set(db, cast)
    assert desks["by"]["first_name"] == "Meera"  # the desk's own read keeps the name
    kavya = cast["kavya"]["id"]
    got = asking.open_set_for_sharer(db, cast["idea"]["idea_id"], kavya, f.at(16, 12))
    assert got is not None and got["by"] is None
    assert got["send_label"] == "Answer at least one question"
    _no_reviewer(got, cast)
    asking.save_answer(
        db, got["questions"][0]["id"], kavya, "All of them. R07 is about half.", at=f.at(16, 12, 5)
    )
    again = asking.open_set_for_sharer(db, cast["idea"]["idea_id"], kavya, f.at(16, 12, 6))
    assert again is not None and again["send_label"] == "Send 1 answer to the review desk"
    _no_reviewer(again, cast)


def test_DEC_111_L_QUESTIONS_S_R3_the_sent_lines_and_the_answers_under_each_part_name_the_desk(
    db: Conn, cast: dict[str, Any]
) -> None:
    sent = _send_set(db, cast)
    kavya = cast["kavya"]["id"]
    asking.save_answer(db, sent["questions"][1]["id"], kavya, "Hyderabad alone.", at=f.at(16, 16, 20))
    done = asking.send_answers(db, sent["id"], kavya, f.at(16, 16, 32))
    assert done["sent_line"] == "Sent to the review desk, 4:32 pm"
    assert done["decides_by"] is None or done["decides_by"].startswith("The review desk decides by ")
    assert "reviewer_first_name" not in done
    _no_reviewer(done, cast)
    # the answers under each part, as the sharer's S-06 reads them (J-TRACK/5)
    [often] = asking.answers_by_part(db, cast["idea"]["id"])["often"]
    assert (often["asked_by"], often["by"], often["answer"]) == (
        "the review desk",
        "Kavya",
        "Hyderabad alone.",
    )
    _no_reviewer(asking.answers_by_part(db, cast["idea"]["id"]), cast)


def test_DEC_111_L_DECIDE_S_06_the_sharer_and_the_crew_read_the_desk_and_the_desk_and_committee_the_name(
    db: Conn, cast: dict[str, Any]
) -> None:
    decide.send(
        db, cast["idea"]["idea_id"], cast["meera"]["id"], {"choice": "pick", "reason": REASON}, DECIDED
    )
    at = f.at(17, 9)
    for who in ("kavya", "farhan"):  # the sharer, the crew
        got = committee.decision_for_viewer(db, cast["idea"]["idea_id"], cast[who]["id"], at)
        assert got is not None and got["lines"] is not None, who
        assert got["decision"]["by_line"] == "by the review desk, Monday 16 November", who
        assert got["decision"]["reason_heading"] is None, who  # Status.md draws no heading over the reason
        assert got["decision"]["reason"] == REASON, who
        _no_reviewer(got, cast)
    for who in ("meera", "rohan"):  # the desk and the committee keep the reviewer's name
        got = committee.decision_for_viewer(db, cast["idea"]["idea_id"], cast[who]["id"], at)
        assert got is not None and got["lines"] is None, who
        assert got["decision"]["by_line"] == "by Meera from the review desk, Monday 16 November", who
        assert got["decision"]["reason_heading"] == "The review desk’s reason, as Kavya read it", who


def test_DEC_111_L_COMMITTEE_S_06_after_a_reversal_the_sharer_reads_the_desk_and_the_member_by_name(
    db: Conn, cast: dict[str, Any]
) -> None:
    d = decide.send(
        db, cast["idea"]["idea_id"], cast["meera"]["id"], {"choice": "pick", "reason": REASON}, DECIDED
    )
    window = db.execute("SELECT id FROM decision_windows WHERE decision_id = %s", (d["id"],)).fetchone()
    assert window is not None
    committee.reverse_window(db, str(window["id"]), cast["rohan"]["id"],
                             {"to": "not_picked", "note": NOTE}, f.at(20, 11))  # fmt: skip
    got = committee.decision_for_viewer(db, cast["idea"]["idea_id"], cast["kavya"]["id"], f.at(20, 12))
    assert got is not None and got["lines"]["reversal"] is not None
    rev = got["lines"]["reversal"]
    assert rev["was_by_line"] == "by the review desk, Monday 16 November"
    assert rev["from_line"].startswith("Rohan Mehta from the Ones Committee, ")  # committee names stay
    assert got["reversal"]["by"]["name"] == "Rohan Mehta"
    _no_reviewer(got, cast)
    # the committee's own row still names the reviewer (S-R4)
    rows = committee.listing(db, cast["rohan"]["id"], "reversed", at=f.at(20, 12))["items"]
    mine = next(r for r in rows if r["idea"]["id"] == cast["idea"]["idea_id"])
    assert mine["decision"]["by_line"] == "by Meera from the review desk, Monday 16 November"
