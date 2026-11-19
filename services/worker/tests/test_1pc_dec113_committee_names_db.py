"""DEC-113 (BLD-B269): DEC-111 extends to the Ones Committee. A sharer, a crew member and anyone outside the review
desk and the Ones Committee never see the name, initials or id of the committee member who reversed a decision. Lane
B's sharer-side decision read (`GET /ideas/:id/decision`) names the Ones Committee itself: S-06's reversal card
(Status.md "Reversed by the Ones Committee"), J-COMMITTEE/3b's hand-off to the sharer and J-TRACK's reversal line.
The review desk and the committee still read the member's name (S-R2 Decided, S-R4).

Needs Postgres with the handoff cut-over applied (`make up`, then the tests migrate their own database).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from core.db import Conn
from desk import committee, decide, reads
from desk.store import UNKNOWN
from tests import desk_fixtures as f
from tests.desk_fixtures import clean_up_desk_rows  # noqa: F401 (autouse: removes what the helpers made)

DECIDED = f.at(16, 16, 58)  # Monday 16 November 2026, 4:58 pm IST
REVERSED = f.at(24, 17, 40)  # Tuesday 24 November, 5:40 pm
REASON = "Picked. A clear problem, a real number and a simple fix. One team builds one fix."
NOTE = "The SMS templates are frozen until the platform upgrade in January, so a team picked now would wait."
MERGE_NOTE = (
    "These two are different problems at different branches, so each one goes back to its own sharer."
)
THE_COMMITTEE = {
    "id": "", "name": "The Ones Committee", "first_name": "The Ones Committee", "initials": "", "city": None,
    "area": None,
}  # fmt: skip


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
    ravi = f.person(db, "Ravi Nair")
    idea = f.idea(db, kavya, shared_at=f.at(14, 10), city="Vizag")
    f.crew(db, idea, farhan)
    return {
        "kavya": kavya, "farhan": farhan, "ravi": ravi, "idea": idea,
        "ravis": f.idea(db, ravi, title="Rejection SMS codes confuse investors", shared_at=f.at(15, 9)),
        "meera": f.person(db, "Meera Iyer", roles=("reviewer",)),
        "rohan": f.person(db, "Rohan Mehta", roles=("committee",)),
        "anita": f.person(db, "Anita Desai", roles=("committee",)),
    }  # fmt: skip


def _no_member(payload: Any, *members: dict[str, str]) -> None:
    """None of the member's name, first name, initials, user id or contributor code: not even in the JSON."""
    text = json.dumps(payload, ensure_ascii=False, default=str)
    for m in members:
        first, last = m["name"].split()
        assert first not in text and last not in text, text
        assert m["id"] not in text and m["code"] not in text, text
        assert f'"{first[0]}{last[0]}"' not in text, text


def _window(db: Conn, column: str, value: str) -> str:
    row = db.execute(f"SELECT id FROM decision_windows WHERE {column} = %s", (value,)).fetchone()  # noqa: S608
    assert row is not None
    return str(row["id"])


def _read(db: Conn, ref: str, who: dict[str, str]) -> dict[str, Any] | None:
    return committee.decision_for_viewer(db, ref, who["id"], f.at(24, 18))


def test_DEC_113_L_COMMITTEE_S_06_J_COMMITTEE_3b_the_sharer_never_sees_the_member_who_reversed_it(
    db: Conn, cast: dict[str, Any]
) -> None:
    d = decide.send(
        db, cast["idea"]["idea_id"], cast["meera"]["id"], {"choice": "pick", "reason": REASON}, DECIDED
    )
    mine = committee.reverse_window(db, _window(db, "decision_id", d["id"]), cast["rohan"]["id"],
                                    {"to": "not_now", "note": NOTE, "return_in": "3m"}, REVERSED)  # fmt: skip
    # S-R4: the committee's own answer still names the member
    assert (mine["reversal"]["by"]["name"], mine["reversal"]["now_by_line"]) == (
        "Rohan Mehta",
        "by Rohan Mehta, Tuesday 24 November",
    )
    for who in ("kavya", "farhan"):  # the sharer and the crew
        got = _read(db, cast["idea"]["idea_id"], cast[who])
        assert got is not None and got["lines"] is not None and got["lines"]["reversal"] is not None, who
        rev, card = got["reversal"], got["lines"]["reversal"]
        assert rev["by"] == THE_COMMITTEE, who
        assert rev["by"].keys() == UNKNOWN.as_json().keys(), who  # the person shape S-06 already reads
        assert rev["now_by_line"] == "by the Ones Committee, Tuesday 24 November", who
        assert card["from_line"] == "The Ones Committee, Tuesday 24 November, 5:40 pm", who
        assert card["title"] == "The Ones Committee changed the decision to not now", who
        assert card["track_line"] == "Picked, then moved to not now by the Ones Committee", who  # J-TRACK
        assert rev["note"] == NOTE, who  # the committee's note, word for word
        _no_member(got, cast["rohan"])
    assert committee.COMMITTEE_ITSELF == THE_COMMITTEE  # copied into each read, never changed
    # S-R2 Decided and S-R4: the review desk and the committee still read the member's name
    for who in ("meera", "rohan"):
        got = _read(db, cast["idea"]["idea_id"], cast[who])
        assert got is not None and got["lines"] is None, who
        assert (got["reversal"]["by"]["name"], got["reversal"]["by"]["initials"]) == ("Rohan Mehta", "RM"), (
            who
        )
        assert got["reversal"]["now_by_line"] == "by Rohan Mehta, Tuesday 24 November", who
    panel = reads.reviewer_idea(db, cast["idea"]["idea_id"], cast["meera"]["id"], f.at(24, 18))["panel"]
    assert panel["state"] == "decided" and panel["decision"]["reversal"]["by"]["id"] == cast["rohan"]["id"]
    rows = committee.listing(db, cast["anita"]["id"], "reversed", at=f.at(24, 18))["items"]
    row = next(r for r in rows if r["idea"]["id"] == cast["idea"]["idea_id"])
    assert (row["reversal"]["by"]["name"], row["reversal"]["now_by_line"]) == (
        "Rohan Mehta",
        "by Rohan Mehta, Tuesday 24 November",
    )


def test_DEC_113_L_COMMITTEE_L_MERGE_desk_5_neither_sharer_sees_the_members_who_reversed_a_joined_pick_or_its_merge(
    db: Conn, cast: dict[str, Any]
) -> None:
    """A Pick that joined a similar idea (L-MERGE.desk/5): the merged idea's sharer reads the lead's Pick. One member
    reverses the Pick, another then undoes the merge (L-MERGE.effects/7); neither is named to either sharer."""
    d = decide.send(db, cast["idea"]["idea_id"], cast["meera"]["id"],
                    {"choice": "pick", "reason": REASON, "joined_with": cast["ravis"]["idea_id"]}, DECIDED)  # fmt: skip
    committee.reverse_window(db, _window(db, "decision_id", d["id"]), cast["rohan"]["id"],
                             {"to": "not_picked", "note": NOTE}, REVERSED)  # fmt: skip
    joined = _read(db, cast["ravis"]["idea_id"], cast["ravi"])  # read from the idea the Pick joined
    assert joined is not None and joined["joined_into"] == cast["idea"]["idea_id"]
    assert joined["reversal"]["by"] == THE_COMMITTEE
    assert joined["reversal"]["now_by_line"] == "by the Ones Committee, Tuesday 24 November"
    assert joined["lines"]["reversal"]["from_line"] == "The Ones Committee, Tuesday 24 November, 5:40 pm"
    _no_member(joined, cast["rohan"], cast["anita"])
    committee.reverse_window(db, _window(db, "merge_id", d["merge"]["id"]), cast["anita"]["id"],
                             {"note": MERGE_NOTE}, f.at(24, 17, 50))  # fmt: skip
    for ref, who in ((cast["idea"]["idea_id"], cast["kavya"]), (cast["ravis"]["idea_id"], cast["ravi"])):
        got = _read(db, ref, who)
        _no_member(got, cast["rohan"], cast["anita"])
        if got is not None and got.get("reversal"):
            assert got["reversal"]["by"] == THE_COMMITTEE, ref
    lead = _read(db, cast["idea"]["idea_id"], cast["kavya"])
    assert lead is not None and lead["lines"]["reversal"]["from_line"].startswith("The Ones Committee, ")
    # the committee's Reversed rows still name both members (S-R4)
    rows = committee.listing(db, cast["rohan"]["id"], "reversed", at=f.at(24, 18))["items"]
    named = {r["kind"]: r["reversal"]["by"]["name"] for r in rows if r["idea"]["id"] in
             (cast["idea"]["idea_id"], cast["ravis"]["idea_id"])}  # fmt: skip
    assert named == {"decision": "Rohan Mehta", "merge": "Anita Desai"}
