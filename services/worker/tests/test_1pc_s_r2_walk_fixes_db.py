"""Lane G's walk on S-R2, against the database (BLD-B264): the empty Fix and Attached parts read the board's words on
the page and in the listen script (S-R2.panel, L-LISTEN/2), and a similar idea's line is built from the bits that
exist when its sharer has no city or no area (S-R2.similar, J-REVIEW/A5). Synthetic data only."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from core.db import Conn
from desk import committee, decide, reads
from desk.store import joined
from tests import desk_fixtures as f
from tests.desk_fixtures import clean_up_desk_rows  # noqa: F401 (autouse: removes what the helpers made)

NOW = f.at(16, 13, 20)
REASON = "Picked. A clear problem, a real number and a simple fix for the branch."


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
    return {
        "kavya": f.person(db, "Kavya Menon"),
        "ravi": f.person(db, "Ravi Nair"),
        "meera": f.person(db, "Meera Iyer", roles=("reviewer",)),
        "rohan": f.person(db, "Rohan Mehta", roles=("committee",)),
    }


def _link(db: Conn, idea: dict[str, Any], other: dict[str, Any]) -> None:
    db.execute(
        "INSERT INTO similar_links (idea_uuid, other_idea_uuid, strength, reason) VALUES (%s, %s, 'close', "
        "'Same R07 SMS in Hyderabad')",
        (idea["id"], other["id"]),
    )


def test_S_R2_panel_L_LISTEN_2_no_fix_and_no_files_read_the_boards_words(
    db: Conn, cast: dict[str, Any]
) -> None:
    """An idea with no fix and nothing attached: the page's Fix reads "No fix suggested. It was optional." and its
    Attached "Nothing attached."; the listen script reads the same words for both."""
    idea = f.idea(db, cast["kavya"])
    page = reads.reviewer_idea(db, idea["idea_id"], cast["meera"]["id"], NOW)
    parts = {p["part"]: p for p in page["parts"]}
    assert (parts["fix"]["text"], parts["fix"]["empty"]) == ("", "No fix suggested. It was optional.")
    assert (parts["evidence"]["text"], parts["evidence"]["empty"]) == ("", "Nothing attached.")
    assert parts["who"]["text"] == "" and parts["who"]["empty"] == "Not given."
    said = {p.part: p.text for p in reads.script_for(db, idea["idea_id"], NOW).parts}
    assert said["fix"] == parts["fix"]["empty"] and said["evidence"] == parts["evidence"]["empty"]


@pytest.mark.parametrize(
    ("columns", "bits"),
    [
        ({"city": None}, "Ravi Nair, Investor service"),
        ({"area": None}, "Ravi Nair, Hyderabad"),
        ({"city": None, "area": None}, "Ravi Nair"),
    ],
    ids=["no-city", "no-area", "neither"],
)
def test_S_R2_similar_J_REVIEW_A5_a_line_from_the_bits_that_exist(
    db: Conn, cast: dict[str, Any], columns: dict[str, Any], bits: str
) -> None:
    """DeskIdea.md: "IDEA-…, Ravi Nair, Investor service, Hyderabad. 4 on its crew". With no city it reads
    "…, Investor service. 1 on its crew", never "…, Investor service, . 1 on its crew"; likewise with no area."""
    idea = f.idea(db, cast["kavya"])
    other = f.idea(
        db, cast["ravi"], title="Rejection SMS codes confuse investors", shared_at=f.at(2, 15), **columns
    )
    _link(db, idea, other)
    sim = reads.reviewer_idea(db, idea["idea_id"], cast["meera"]["id"], NOW)["similar"][0]
    assert sim["meta"] == f"{other['idea_id']}, {bits}. 1 on its crew"


def test_S_R2_similar_the_heading_and_the_committee_row_skip_a_missing_city_or_area(
    db: Conn, cast: dict[str, Any]
) -> None:
    """The same bug on S-R2's heading and S-R4's Idea column: an idea with no city reads "by Kavya Menon, Investor
    service." and the committee's row "IDEA-…, Kavya Menon, Investor service"; with no area "IDEA-…, Kavya Menon,
    Hyderabad"."""
    no_city = f.idea(db, cast["kavya"], city=None)
    heading = reads.reviewer_idea(db, no_city["idea_id"], cast["meera"]["id"], NOW)["idea"]["heading"]
    assert heading == "Shared Saturday 14 November by Kavya Menon, Investor service."
    no_area = f.idea(db, cast["kavya"], area=None)
    for idea in (no_city, no_area):
        decide.send(db, idea["idea_id"], cast["meera"]["id"], {"choice": "pick", "reason": REASON}, NOW)
    rows = {
        r["idea"]["id"]: r["idea"]["meta"]
        for r in committee.listing(db, cast["rohan"]["id"], at=NOW)["items"]
    }
    assert rows[no_city["idea_id"]] == f"{no_city['idea_id']}, Kavya Menon, Investor service"
    assert rows[no_area["idea_id"]] == f"{no_area['idea_id']}, Kavya Menon, Hyderabad"


def test_S_R2_similar_joined_keeps_only_the_bits_that_exist() -> None:
    assert (
        joined("IDEA-2026-001412", "Ravi Nair", "Investor service", None)
        == "IDEA-2026-001412, Ravi Nair, Investor service"
    )
    assert (
        joined("IDEA-2026-001412", "Ravi Nair", "", "Hyderabad") == "IDEA-2026-001412, Ravi Nair, Hyderabad"
    )
    assert joined("IDEA-2026-001412", "Ravi Nair", "  ", None) == "IDEA-2026-001412, Ravi Nair"
