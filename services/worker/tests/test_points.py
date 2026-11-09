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
    assert ("submission", 1.0) in mine
    assert not any(e == "strong_canvas" for e, _ in mine)  # only a reviewer's confirmation awards it
    assert ("shortlisted", 5.0) in mine and ("accepted", 10.0) in mine  # picked counts as shortlisted first
    assert not any(e == "shipped_or_resolved" for e, _ in mine)
    before = len(mine)
    ledger.sync(db)  # idempotent
    assert len(rows(db, code)) == before
    db.execute("UPDATE ideas SET stage = 'shipped' WHERE idea_id = %s", (idea,))
    ledger.sync(db)
    assert ("shipped_or_resolved", 25.0) in rows(db, code)
    view = ledger.mine(db, uid)
    assert view["total"] == 41.0 and view["recent"][0]["what"] == "Shipped"


def test_monthly_caps_and_nothing_for_drafts(pdb: Any) -> None:
    db = pdb
    _, code = person(db)
    when = dt.datetime(2026, 12, 3, 10, 0, tzinfo=dt.UTC)
    for _ in range(7):
        idea = helpers.insert_idea(db, contributor=code, stage="scanned")
        db.execute("UPDATE ideas SET submitted_at = %s WHERE idea_id = %s", (when, idea))
    helpers.insert_idea(db, contributor=code, stage="draft")
    ledger.sync(db)
    assert [e for e, _ in rows(db, code)].count("submission") == 5  # cap of 5 points at 1 point each


def test_a_person_sees_only_their_own_points_and_the_ledger_is_append_only(pdb: Any) -> None:
    db = pdb
    a, a_code = person(db)
    b, _ = person(db)
    helpers.insert_idea(db, contributor=a_code, stage="scanned")
    ledger.sync(db)
    assert ledger.mine(db, a)["total"] >= 1 and ledger.mine(db, b)["total"] == 0
    with pytest.raises(Exception, match="append-only"):
        db.execute("UPDATE points_ledger SET points = 100 WHERE contributor_code = %s", (a_code,))


def test_a_strong_canvas_comes_through_the_ledger_and_caps_count_points(pdb: Any) -> None:
    """BLD-134: `monthly_cap` is points per rule per person per month. A strong canvas is 2 points with a cap of 4,
    so two a month; the same idea never counts twice."""
    db = pdb
    _, code = person(db)
    when = dt.datetime(2026, 12, 3, 10, 0, tzinfo=dt.UTC)
    ideas = [helpers.insert_idea(db, contributor=code, stage="reviewed") for _ in range(3)]
    assert ledger.award(db, code, "strong_canvas", ideas[0], when)
    assert not ledger.award(db, code, "strong_canvas", ideas[0], when)  # once per idea
    assert ledger.award(db, code, "strong_canvas", ideas[1], when)
    assert not ledger.award(db, code, "strong_canvas", ideas[2], when)  # 4 points used this month
    assert ledger.award(db, code, "strong_canvas", ideas[2], dt.datetime(2027, 1, 4, 10, 0, tzinfo=dt.UTC))
    assert [e for e, _ in rows(db, code)].count("strong_canvas") == 3


def test_milestones_are_dated_when_they_happened(pdb: Any) -> None:
    db = pdb
    _, code = person(db)
    idea = helpers.insert_idea(db, contributor=code, stage="scanned")
    db.execute("UPDATE ideas SET submitted_at = '2026-10-01T10:00:00Z' WHERE idea_id = %s", (idea,))
    db.execute("UPDATE ideas SET stage = 'picked' WHERE idea_id = %s", (idea,))
    db.execute(
        "UPDATE idea_stage_history SET at = '2026-10-05T10:00:00Z' WHERE to_stage = 'picked' "
        "AND idea_uuid = (SELECT id FROM ideas WHERE idea_id = %s)",
        (idea,),
    )
    ledger.sync(db)
    at = db.execute(
        "SELECT created_at FROM points_ledger WHERE contributor_code = %s AND event = 'accepted'", (code,)
    ).fetchone()["created_at"]
    assert at == dt.datetime(2026, 10, 5, 10, 0, tzinfo=dt.UTC)


def test_no_milestones_for_members_who_left_and_no_point_before_the_checks(pdb: Any) -> None:
    db = pdb
    _, stayed = person(db)
    _, left = person(db)
    _, waiting = person(db)
    taken = {r["id"] for r in db.execute("SELECT id FROM clusters").fetchall()}
    cl = next(f"CL-{n}" for n in range(9100, 9999) if f"CL-{n}" not in taken)
    db.execute("INSERT INTO clusters (id, stage, distinct_contributors) VALUES (%s, 'picked', 2)", (cl,))
    a = helpers.insert_idea(db, contributor=stayed, stage="in_cluster")
    b = helpers.insert_idea(db, contributor=left, stage="withdrawn")
    db.execute("UPDATE ideas SET cluster_id = %s WHERE idea_id = ANY(%s)", (cl, [a, b]))
    helpers.insert_idea(db, contributor=waiting, stage="scanning")
    helpers.insert_idea(db, contributor=waiting, stage="blocked")
    ledger.sync(db)
    assert ("accepted", 10.0) in rows(db, stayed)
    assert not any(e in ("accepted", "shortlisted", "accepted_into_cluster") for e, _ in rows(db, left))
    assert rows(db, waiting) == []


def _cluster(db: Any, stage: str = "picked") -> str:
    taken = {r["id"] for r in db.execute("SELECT id FROM clusters").fetchall()}
    cl = next(f"CL-{n}" for n in range(9100, 9999) if f"CL-{n}" not in taken)
    db.execute("INSERT INTO clusters (id, stage, distinct_contributors) VALUES (%s, %s, 2)", (cl, stage))
    return cl


def test_presenters_get_points_once_when_the_session_is_held(pdb: Any) -> None:
    """BLD-147: each presenter of a held session gets `presented`, dated when it was held; a no-show earns nothing."""
    db = pdb
    _, one = person(db)
    _, two = person(db)
    _, absent = person(db)
    held_at = dt.datetime(2026, 12, 10, 11, 0, tzinfo=dt.UTC)
    taken = {r["id"] for r in db.execute("SELECT id FROM presentations").fetchall()}
    ids = [f"PRS-2026-{n:04d}" for n in range(9000, 9999) if f"PRS-2026-{n:04d}" not in taken][:2]
    db.execute(
        "INSERT INTO presentations (id, cluster_id, presenters, state, held_at) VALUES (%s, %s, %s, 'held', %s)",
        (ids[0], _cluster(db), [one, two, "not-a-code"], held_at),
    )
    db.execute(
        "INSERT INTO presentations (id, cluster_id, presenters, state) VALUES (%s, %s, %s, 'no_show')",
        (ids[1], _cluster(db), [absent]),
    )
    ledger.sync(db)
    ledger.sync(db)  # idempotent
    for code in (one, two):
        got = db.execute(
            "SELECT points, created_at FROM points_ledger WHERE contributor_code = %s AND event = 'presented'",
            (code,),
        ).fetchall()
        assert len(got) == 1 and float(got[0]["points"]) == 3.0 and got[0]["created_at"] == held_at
    assert not any(e == "presented" for e, _ in rows(db, absent))


def test_working_group_members_get_points_when_the_group_ships(pdb: Any) -> None:
    """BLD-147: every member of a working group gets `working_group_member_shipped` once its group delivery ships;
    nothing while it is still being built."""
    db = pdb
    _, lead = person(db)
    _, member = person(db)
    cl = _cluster(db)
    taken = {r["id"] for r in db.execute("SELECT id FROM working_groups").fetchall()}
    wg = next(f"WG-{n:04d}" for n in range(9000, 9999) if f"WG-{n:04d}" not in taken)
    db.execute(
        "INSERT INTO working_groups (id, cluster_id, members, state) VALUES (%s, %s, %s::jsonb, 'active')",
        (wg, cl, f'[{{"contributor_code": "{lead}", "role": "lead"}}, {{"contributor_code": "{member}"}}]'),
    )
    did = db.execute(
        "INSERT INTO deliveries (subject_type, subject_id, state) VALUES ('cluster', %s, 'in_delivery') RETURNING id",
        (cl,),
    ).fetchone()["id"]
    ledger.sync(db)
    assert not any(e == "working_group_member_shipped" for e, _ in rows(db, lead))
    shipped = dt.datetime(2027, 1, 20, 9, 0, tzinfo=dt.UTC)
    db.execute("UPDATE deliveries SET state = 'shipped', shipped_at = %s WHERE id = %s", (shipped, did))
    ledger.sync(db)
    ledger.sync(db)
    for code in (lead, member):
        got = db.execute(
            "SELECT points, ref_id, created_at FROM points_ledger WHERE contributor_code = %s "
            "AND event = 'working_group_member_shipped'",
            (code,),
        ).fetchall()
        assert len(got) == 1 and float(got[0]["points"]) == 15.0
        assert got[0]["ref_id"] == wg and got[0]["created_at"] == shipped


def test_the_ledger_cannot_be_truncated(pdb: Any) -> None:
    with pytest.raises(Exception, match="append-only"):
        pdb.execute("TRUNCATE points_ledger")


def test_an_overturned_decline_restores_the_withheld_milestones_once(pdb: Any) -> None:
    """BLD-148 (`appeal_overturned: restore_forfeited`): while a group is declined its members earn no group
    milestones; when an appeal overturns the decline the group goes back above the line (lane B moves the group and
    its member ideas to `shortlisted`), and the next sync awards what the decline withheld, once, dated when the group
    got there."""
    db = pdb
    _, member = person(db)
    cl = _cluster(db, stage="declined")
    idea = helpers.insert_idea(db, contributor=member, stage="declined")
    db.execute("UPDATE ideas SET cluster_id = %s WHERE idea_id = %s", (cl, idea))
    ledger.sync(db)
    assert not any(e in ("shortlisted", "accepted_into_cluster") for e, _ in rows(db, member))

    # What the overturn does to the group (committee.appeals._apply for a preliminary decision).
    db.execute("UPDATE clusters SET stage = 'shortlisted' WHERE id = %s", (cl,))
    db.execute("UPDATE ideas SET stage = 'shortlisted' WHERE cluster_id = %s", (cl,))
    back = db.execute(
        "SELECT max(h.at) AS at FROM idea_stage_history h JOIN ideas i ON i.id = h.idea_uuid "
        "WHERE i.idea_id = %s AND h.to_stage = 'shortlisted'",
        (idea,),
    ).fetchone()["at"]
    ledger.sync(db)
    ledger.sync(db)  # idempotent
    got = db.execute(
        "SELECT event, points, created_at FROM points_ledger WHERE contributor_code = %s AND event = 'shortlisted'",
        (member,),
    ).fetchall()
    assert len(got) == 1 and float(got[0]["points"]) == 5.0 and got[0]["created_at"] == back
    assert [e for e, _ in rows(db, member)].count("accepted_into_cluster") == 1
    assert not any(e == "accepted" for e, _ in rows(db, member))  # picked only if the chair later picks it
