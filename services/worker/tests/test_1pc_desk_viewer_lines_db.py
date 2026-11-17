"""A decision's words shaped for each viewer (A-API.conventions/6): the sharer's from the Status board, the
reviewer's from the DeskIdea board's Decided state, the committee's from the Committee board (L-DECIDE.rules/5,
L-COMMITTEE.rules/5, V-ACC.committee/2 and /4, J-TRACK)."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from core.db import Conn
from desk import committee, decide, reads
from tests import desk_fixtures as f
from tests.desk_fixtures import clean_up_desk_rows  # noqa: F401 (autouse: removes what the helpers made)

REASON = "Picked. A clear problem, a real number and a simple fix for the branch."
NOTE = "The SMS templates are frozen until the platform upgrade in January, so a team picked now would wait."
DECIDED = f.at(16, 16, 58)  # Monday 16 November, 4:58 pm
OPEN_LINE = (
    "The Ones Committee can review this decision until {day}. If they change it, their note comes to your Inbox. "
    "After that, it stands."
)


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
    d = decide.send(db, idea["idea_id"], meera["id"], {"choice": "pick", "reason": REASON}, DECIDED)
    window = db.execute("SELECT id FROM decision_windows WHERE decision_id = %s", (d["id"],)).fetchone()
    assert window is not None
    return {"kavya": kavya, "farhan": farhan, "meera": meera, "rohan": rohan, "idea": idea,
            "window": str(window["id"])}  # fmt: skip


def _sharer(db: Conn, cast: dict[str, Any], at: dt.datetime, who: str = "kavya") -> dict[str, Any]:
    got = committee.decision_for_viewer(db, cast["idea"]["idea_id"], cast[who]["id"], at)
    assert got is not None and got["lines"] is not None
    return got


def test_L_DECIDE_rules_5_the_sharer_reads_the_committee_line_while_the_window_is_open(
    db: Conn, cast: dict[str, Any]
) -> None:
    got = _sharer(db, cast, f.at(17, 9))
    assert (
        got["lines"]
        == {
            "joined_line": None,  # a Pick that joined nothing (L-MERGE.desk/5 is in test_1pc_desk_review_followup_db)
            "committee_line": OPEN_LINE.format(day="Wednesday 16 December"),
            "reversal": None,
        }
    )
    assert got["decision"]["reason"] == REASON  # word for word
    assert _sharer(db, cast, f.at(17, 9), who="farhan")["lines"]["committee_line"]  # the crew reads it too
    # the desk and the committee read the committee's words, not the sharer's
    for reader in ("meera", "rohan"):
        seen = committee.decision_for_viewer(db, cast["idea"]["idea_id"], cast[reader]["id"], f.at(17, 9))
        assert seen is not None and seen["lines"] is None
    # once the window has closed the decision simply stands
    assert _sharer(db, cast, DECIDED + dt.timedelta(days=31))["lines"]["committee_line"] is None


def test_V_ACC_committee_2_the_sharer_sees_the_extended_date(db: Conn, cast: dict[str, Any]) -> None:
    committee.extend_window(db, cast["window"], cast["rohan"]["id"], f.at(18, 10))
    got = _sharer(db, cast, f.at(18, 11))
    assert got["lines"]["committee_line"] == OPEN_LINE.format(day="Friday 15 January 2027")
    assert (got["window"]["until"], got["window"]["extended"]) == (
        "Until Friday 15 January 2027",
        "Extended once",
    )


def test_V_ACC_committee_4_the_sharer_reads_the_committees_card_and_this_is_final(
    db: Conn, cast: dict[str, Any]
) -> None:
    reversed_at = f.at(24, 17, 40)  # Tuesday 24 November, 5:40 pm
    committee.reverse_window(db, cast["window"], cast["rohan"]["id"],
                             {"to": "not_now", "note": NOTE, "return_in": "3m"}, reversed_at)  # fmt: skip
    got = _sharer(db, cast, f.at(24, 18))
    assert got["lines"]["committee_line"] is None and got["reversal"]["note"] == NOTE
    assert got["lines"]["reversal"] == {
        "from_line": "Rohan Mehta from the Ones Committee, Tuesday 24 November, 5:40 pm",
        "title": "The Ones Committee changed the decision to not now",
        "note_heading": "The committee’s note to you",
        "was_line": "Was: Picked",
        "was_by_line": "by Meera from the review desk, Monday 16 November",
        "final_line": (
            "This is final. It comes back to the review desk on Wednesday 24 February 2027, with your answers and crew."
        ),
        "track_line": "Picked, then moved to not now by the Ones Committee",
    }
    assert dt.datetime.fromisoformat(got["return_at"]) == f.at(24, 17, 40, m=2, y=2027)


def test_V_ACC_committee_4_a_reversal_to_not_picked_has_no_return_line(
    db: Conn, cast: dict[str, Any]
) -> None:
    committee.reverse_window(db, cast["window"], cast["rohan"]["id"], {"to": "not_picked", "note": NOTE},
                             f.at(20, 11))  # fmt: skip
    rev = _sharer(db, cast, f.at(20, 12))["lines"]["reversal"]
    assert (rev["final_line"], rev["track_line"]) == (
        "This is final.", "Picked, then moved to not picked by the Ones Committee"
    )  # fmt: skip


def test_S_R2_panel_decided_the_reviewer_reads_their_own_lines(db: Conn, cast: dict[str, Any]) -> None:
    page = reads.reviewer_idea(db, cast["idea"]["idea_id"], cast["meera"]["id"], f.at(16, 17))
    panel = page["panel"]
    assert panel["state"] == "decided" and "lines" not in panel["decision"]
    assert panel["lines"] == {
        "title": "Decision sent to Kavya",
        "sent_line": "Today, 4:58 pm. Kavya has it now.",
        "reason_heading": "Your reason, as Kavya reads it",
        "committee_heading": "Ones Committee review",
        "window_state": "Open, 30 days left",
        "window_line": (
            "Open until Wednesday 16 December. The committee can extend it, up to 3 months in all, to Tuesday 16 "
            "February 2027. If they reverse it, Kavya gets their note and you see it here. When the window closes, "
            "the decision stands."
        ),
    }
    # the committee's own words stay on the row (S-R4)
    assert panel["decision"]["decision"]["reason_heading"] == "The review desk’s reason, as Kavya read it"
    committee.reverse_window(db, cast["window"], cast["rohan"]["id"], {"to": "not_picked", "note": NOTE},
                             f.at(20, 11))  # fmt: skip
    after = reads.reviewer_idea(db, cast["idea"]["idea_id"], cast["meera"]["id"], f.at(20, 12))["panel"]
    assert (after["lines"]["window_state"], after["lines"]["window_line"]) == (
        "Reversed Friday 20 November",
        None,
    )
    assert after["lines"]["sent_line"] == "Monday 16 November, 4:58 pm. Kavya has it now."
    assert after["decision"]["reversal"]["note"] == NOTE  # "you see it here"
