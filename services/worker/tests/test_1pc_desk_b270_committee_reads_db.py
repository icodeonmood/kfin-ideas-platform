"""BLD-B270, S-R2, S-R1: the `committee` role reads the desk (`view_review_queue`, `desk.store.READERS`), but the
desk's actions are the review desk's. On an idea still with the desk, S-R2's `can_act` (Decide on this idea, Ask
about this, Change what it’s worth, Merge, more time and the reminder) holds only for `REVIEWERS`, and an S-R1 row
never offers a committee member "Remind {name}". `core_committee` holds `view_review_queue`, `veto_desk_decision` and
`hide_for_desk` today, not `work_review_queue`, and is not in the worker's `REVIEWERS`: it reads without the actions
too. Synthetic people only.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from core.db import Conn
from desk import reads
from desk.store import REVIEWERS, Refused, require_role
from tests import desk_fixtures as f
from tests.desk_fixtures import clean_up_desk_rows  # noqa: F401 (autouse: removes what the helpers made)

NOW = f.at(16, 13, 20)


@pytest.fixture
def repo(company_repo: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    from core.config import get_settings

    monkeypatch.setenv("COMPANY_REPO_PATH", str(company_repo))
    get_settings.cache_clear()
    yield company_repo
    monkeypatch.undo()
    get_settings.cache_clear()


@pytest.fixture
def world(db: Conn, repo: Path) -> dict[str, Any]:
    meera = f.person(db, "Meera Iyer", roles=("reviewer",))
    rohan = f.person(db, "Rohan Mehta", roles=("committee",))  # the Ones Committee only
    sunita = f.person(db, "Sunita Bhatt", roles=("core_committee",))
    kavya, divya = f.person(db, "Kavya Menon"), f.person(db, "Divya Shah", city="Chennai")
    fresh = f.idea(db, kavya)  # with the desk, nothing asked yet
    late = f.idea(db, divya, title="Branch queue times are not tracked anywhere", city="Chennai")
    s = db.execute(  # one question, sent by Meera, overdue and not seen: S-R1 offers "Remind Divya"
        "INSERT INTO question_sets (idea_uuid, by_user_id, state, time_to_answer, sent_at, due_at) "
        "VALUES (%s, %s, 'sent', '3d', %s, %s) RETURNING id",
        (late["id"], meera["id"], f.at(13, 8, 20), f.at(16, 8, 20)),
    ).fetchone()
    assert s is not None
    db.execute(
        "INSERT INTO questions (set_id, seq, part, text_encrypted) VALUES (%s, 1, 'summary', %s)",
        (s["id"], b"sealed"),
    )
    db.execute("UPDATE ideas SET status = 'needs_you' WHERE id = %s", (late["id"],))
    return {"meera": meera, "rohan": rohan, "sunita": sunita, "fresh": fresh, "late": late}


@pytest.mark.parametrize(("who", "acts"), [("meera", True), ("rohan", False), ("sunita", False)])
def test_bld_b270_s_r2_a_committee_only_member_reads_an_idea_on_the_desk_without_its_actions(
    db: Conn, world: dict[str, Any], who: str, acts: bool
) -> None:
    """BLD-B270, S-R2: a committee-only member reads an idea on the desk without its actions. The reviewer acts; the
    core committee follows its role today (no `work_review_queue`, not in `REVIEWERS`) and reads without them."""
    for key, state in (("fresh", "reviewing"), ("late", "sent")):
        page = reads.reviewer_idea(db, world[key]["idea_id"], world[who]["id"], NOW)
        assert page["idea"]["status"] in reads.ON_DESK_STATUSES and page["own"] is False
        assert page["panel"]["state"] == state
        assert page["can_act"] is acts, (who, key)
    if not acts:
        with pytest.raises(Refused) as caught:  # what the worker answers any desk write from them
            require_role(db, world[who]["id"], REVIEWERS)
        assert caught.value.status == 403


@pytest.mark.parametrize(("who", "action", "kind"), [
    ("meera", "Remind Divya", "remind"), ("rohan", "Open", "open"), ("sunita", "Open", "open"),
])  # fmt: skip
def test_bld_b270_s_r1_a_row_offers_the_reminder_only_to_the_review_desk(
    db: Conn, world: dict[str, Any], who: str, action: str, kind: str
) -> None:
    """BLD-B270, S-R1: "Remind {name}" writes, so a reader outside the review desk gets the row's "Open" instead.
    The row itself, its clock and its questions line are the same for everyone who reads the desk."""
    rows = {r["idea_id"]: r for r in reads.desk(db, world[who]["id"], at=NOW)["items"]}
    late = rows[world["late"]["idea_id"]]
    assert (late["action"], late["action_kind"]) == (action, kind)
    assert (late["questions"], late["time_left"]) == ("Not seen yet", "Overdue by 5 hours")
    assert all(r["action_kind"] != "remind" for r in rows.values()) or who == "meera"


@pytest.mark.parametrize(("who", "shown"), [("meera", True), ("rohan", False), ("sunita", False)])
def test_bld_b270_s_r2_panel_the_worth_line_that_says_decide_or_revise_is_only_for_the_review_desk(
    db: Conn, world: dict[str, Any], who: str, shown: bool
) -> None:
    """BLD-B270 follow-up, S-R2.panel: "Clear enough? Decide now. If it’s worth more than … revise what it’s worth
    first." tells the reader to act, so a reader who can't act (a committee member, on an idea still with the desk)
    is sent no worth line at all; the tiles stay. No new words: the reviewer's line is the board's, as before."""
    page = reads.reviewer_idea(db, world["fresh"]["idea_id"], world[who]["id"], NOW)
    assert page["can_act"] is shown
    assert page["worth"]["tiles"] is not None
    if shown:
        assert page["worth"]["line"] == (
            "Clear enough? Decide now. If it’s worth more than Kavya could put into numbers, revise what it’s worth "
            "first. Kavya sees your figures next to theirs."
        )
    else:
        assert page["worth"]["line"] is None
