"""Private points (DEC-078, BLD-130): the hourly sync records each award once, keeps monthly caps, follows
`rules/points.md`, and a person sees only their own. Synthetic people only."""

from __future__ import annotations

import datetime as dt
import secrets
from typing import Any

import pytest

from points import ledger
from tests import helpers

pytestmark = pytest.mark.stack


@pytest.fixture
def pdb(db: Any, company_repo: Any, test_database: str, monkeypatch: pytest.MonkeyPatch) -> Any:
    settings = helpers.settings_for(company_repo, test_database)
    monkeypatch.setattr(ledger, "get_settings", lambda: settings)
    return db


def person(db: Any) -> tuple[str, str]:
    tag = secrets.token_hex(3)
    uid = str(db.execute(
        "INSERT INTO users (emp_id_hash, name, email, source) VALUES (%s, %s, %s, 'hr') RETURNING id",
        (f"test:{tag}", f"Synthetic Person {tag}", f"p.{tag}@kfintech.example"),
    ).fetchone()["id"])  # fmt: skip
    code = f"CTR-{secrets.token_hex(3)}"
    db.execute("INSERT INTO contributor_map (contributor_code, user_id) VALUES (%s, %s)", (code, uid))
    return uid, code


def rows(db: Any, code: str) -> list[tuple[str, float]]:
    return [
        (str(r["event"]), float(r["points"]))
        for r in db.execute(
            "SELECT event, points FROM points_ledger WHERE contributor_code = %s ORDER BY id", (code,)
        ).fetchall()
    ]


def test_awards_are_recorded_once_and_follow_the_rules(pdb: Any) -> None:
    db = pdb
    uid, code = person(db)
    idea = helpers.insert_idea(db, contributor=code, stage="picked")
    db.execute("UPDATE ideas SET strength = 4 WHERE idea_id = %s", (idea,))
    ledger.sync(db)
    mine = rows(db, code)
    assert ("submission", 1.0) in mine and ("strong_canvas", 2.0) in mine
    assert ("shortlisted", 5.0) in mine and ("accepted", 10.0) in mine  # picked counts as shortlisted first
    assert not any(e == "shipped_or_resolved" for e, _ in mine)
    before = len(mine)
    ledger.sync(db)  # idempotent
    assert len(rows(db, code)) == before
    db.execute("UPDATE ideas SET stage = 'shipped' WHERE idea_id = %s", (idea,))
    ledger.sync(db)
    assert ("shipped_or_resolved", 25.0) in rows(db, code)
    view = ledger.mine(db, uid)
    assert view["total"] == 43.0 and view["recent"][0]["what"] == "Shipped"


def test_monthly_caps_and_nothing_for_drafts(pdb: Any) -> None:
    db = pdb
    _, code = person(db)
    when = dt.datetime(2026, 12, 3, 10, 0, tzinfo=dt.UTC)
    for _ in range(7):
        idea = helpers.insert_idea(db, contributor=code, stage="scanned")
        db.execute("UPDATE ideas SET submitted_at = %s WHERE idea_id = %s", (when, idea))
    helpers.insert_idea(db, contributor=code, stage="draft")
    ledger.sync(db)
    assert [e for e, _ in rows(db, code)].count("submission") == 5  # monthly cap from rules/points.md


def test_a_person_sees_only_their_own_points_and_the_ledger_is_append_only(pdb: Any) -> None:
    db = pdb
    a, a_code = person(db)
    b, _ = person(db)
    helpers.insert_idea(db, contributor=a_code, stage="scanned")
    ledger.sync(db)
    assert ledger.mine(db, a)["total"] >= 1 and ledger.mine(db, b)["total"] == 0
    with pytest.raises(Exception, match="append-only"):
        db.execute("UPDATE points_ledger SET points = 100 WHERE contributor_code = %s", (a_code,))
