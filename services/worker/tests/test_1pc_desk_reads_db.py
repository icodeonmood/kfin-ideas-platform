"""S-R1 read from the database: tabs, counts, the summary, rows, search, own ideas left out (L-REVIEW.queue)."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from core.db import Conn
from desk import decide, reads
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


def _set(db: Conn, idea: dict[str, Any], by: str, n: int, *, seen: dt.datetime | None, due: dt.datetime,
         answered: int = 0) -> None:  # fmt: skip
    s = db.execute(
        "INSERT INTO question_sets (idea_uuid, by_user_id, state, time_to_answer, sent_at, seen_at, due_at) "
        "VALUES (%s, %s, %s, '3d', %s, %s, %s) RETURNING id",
        (idea["id"], by, "seen" if seen else "sent", f.at(16, 11, 20), seen, due),
    ).fetchone()
    assert s is not None
    for k in range(1, n + 1):
        qrow = db.execute(
            "INSERT INTO questions (set_id, seq, part, text_encrypted) VALUES (%s, %s, 'summary', %s) RETURNING id",
            (s["id"], k, b"sealed"),
        ).fetchone()
        assert qrow is not None
        if k <= answered:
            db.execute(
                "INSERT INTO answers (question_id, by_code, added_to, sent_at) VALUES (%s, %s, 'summary', %s)",
                (qrow["id"], idea["contributor_code"], f.at(16, 12, 20)),
            )
    db.execute("UPDATE ideas SET status = 'needs_you' WHERE id = %s", (idea["id"],))


@pytest.fixture
def desk_world(db: Conn, repo: Path) -> dict[str, Any]:
    meera = f.person(db, "Meera Iyer", roles=("reviewer",))
    kavya, divya, arjun = f.person(db, "Kavya Menon"), f.person(db, "Divya Shah", city="Chennai"), f.person(
        db, "Arjun Rao", city="Pune", area="Operations")  # fmt: skip
    waiting = f.idea(db, kavya)
    late = f.idea(db, divya, title="Branch queue times are not tracked anywhere", city="Chennai",
                  decide_by=f.at(18, 18))  # fmt: skip
    fresh = f.idea(db, arjun, title="Same KYC details typed into three screens", area="Operations", city="Pune",
                   decide_by=f.at(22, 18))  # fmt: skip
    decided = f.idea(db, kavya, title="Plain words for transaction rejections")
    f.idea(db, meera, title="Meera's own idea")  # never on her own desk
    _set(db, waiting, meera["id"], 3, seen=f.at(16, 12, 5), due=f.at(19, 18))
    _set(db, late, meera["id"], 1, seen=None, due=f.at(16, 8, 20))
    decide.send(db, decided["idea_id"], meera["id"],
                {"choice": "pick", "reason": "A clear problem with a simple fix for the branch."}, f.at(12, 15))  # fmt: skip
    return {"meera": meera, "waiting": waiting, "late": late, "fresh": fresh, "decided": decided}


def test_S_R1_layout_1_to_3_counts_and_the_summary(db: Conn, desk_world: dict[str, Any]) -> None:
    got = reads.desk(db, desk_world["meera"]["id"], at=NOW)
    assert got["counts"] == {"to_review": 1, "waiting": 2, "answered": 0, "decided": 1}
    assert got["summary"] == "2 waiting on colleagues. One is overdue."
    assert [r["idea_id"] for r in got["items"]] == [
        desk_world["late"]["idea_id"],
        desk_world["waiting"]["idea_id"],
    ]
    assert [w["dot"] for w in got["waiting_on_sharers"]] == ["red", "blue"]


def test_S_R1_layout_4_rows_on_waiting_and_to_review(db: Conn, desk_world: dict[str, Any]) -> None:
    rows = {r["idea_id"]: r for r in reads.desk(db, desk_world["meera"]["id"], at=NOW)["items"]}
    late = rows[desk_world["late"]["idea_id"]]
    assert (late["who"], late["questions"], late["time_left"], late["action"]) == (
        "Divya Shah, Investor service, Chennai", "Not seen yet", "Overdue by 5 hours", "Remind Divya"
    )  # fmt: skip
    assert rows[desk_world["waiting"]["idea_id"]]["questions"] == "0 of 3 answered, seen 12:05 pm"
    fresh = reads.desk(db, desk_world["meera"]["id"], tab="to_review", at=NOW)["items"][0]
    assert (fresh["questions"], fresh["time_left"], fresh["decide_by"]) == (
        "No questions asked", "6 days to decide", "Sunday 22 November"
    )  # fmt: skip


def test_S_R1_layout_5_decided_this_week(db: Conn, desk_world: dict[str, Any]) -> None:
    row = reads.desk(db, desk_world["meera"]["id"], tab="decided", at=NOW)["items"][0]
    assert row["decision"] == "Picked, 12 November"
    assert row["committee"] == "Ones Committee can review it until Saturday 12 December"


def test_S_R1_search_narrows_rows_and_counts(db: Conn, desk_world: dict[str, Any]) -> None:
    got = reads.desk(db, desk_world["meera"]["id"], tab="to_review", q="kyc", at=NOW)
    assert got["counts"] == {"to_review": 1, "waiting": 0, "answered": 0, "decided": 0}
    got = reads.desk(db, desk_world["meera"]["id"], q="Divya", at=NOW)
    assert [r["idea_id"] for r in got["items"]] == [desk_world["late"]["idea_id"]]


def test_P_PRODUCT_roles_3_a_reviewers_own_idea_is_not_on_their_desk(
    db: Conn, desk_world: dict[str, Any]
) -> None:
    got = reads.desk(db, desk_world["meera"]["id"], q="own idea", at=NOW)
    assert got["counts"] == {"to_review": 0, "waiting": 0, "answered": 0, "decided": 0}
