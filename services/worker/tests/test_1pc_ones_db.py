"""The Ones from the database (L-ONES.rules/1–7, S-ONE, V-FIELDS.one, S-WALL.ones, C-ONES-FAN data, DEC-104, DEC-106):
automatic induction on measured, confirmed impact; the number window; the brief waiting for the programme team; the
glow-up; the cards everyone reads; posts and likes; the admin path; and that only a One reads and changes /one."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from core import killswitch
from core.db import Conn
from gateway import limits
from gateway.routes import FAKE_SCRIPT
from ones.text import seal
from tests import wall_fixtures as f
from wall import ones
from wall.common import Refused

pytestmark = pytest.mark.stack


@pytest.fixture
def ones_db(db: Conn, company_repo: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Conn]:
    from core.config import get_settings

    monkeypatch.setenv("COMPANY_REPO_PATH", str(company_repo))
    get_settings.cache_clear()
    killswitch.clear_cache()
    limits.reset()
    FAKE_SCRIPT.clear()
    yield db
    monkeypatch.undo()
    get_settings.cache_clear()


def refused(code: str, fn: Any, *args: Any, **kwargs: Any) -> Refused:
    with pytest.raises(Refused) as exc:
        fn(*args, **kwargs)
    assert exc.value.code == code, exc.value.code
    return exc.value


def _mark(db: Conn) -> int:
    """audit_log is append-only and outlives each test's truncate: read only what this test wrote."""
    return int(db.execute("SELECT coalesce(max(id), 0) AS n FROM audit_log").fetchone()["n"])


def _audit(db: Conn, action: str, since: int) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in db.execute(
            "SELECT * FROM audit_log WHERE action = %s AND id > %s ORDER BY id", (action, since)
        ).fetchall()
    ]


# --- L-ONES.rules/1: becoming a One ----------------------------------------------------------------------------------


def test_L_ONES_rules_1_inducts_everyone_credited_once_impact_is_measured_and_confirmed(
    ones_db: Conn,
) -> None:
    db = ones_db
    mark = _mark(db)
    admin = f.person(db, "Mehul Desai", roles=("admin",))
    sharer, merged_in, crew_only = (f.person(db, n) for n in ("Ritika Sood", "Harsh Vora", "Leela Nambiar"))
    idea = f.idea(db, sharer, title="Bank details checked before the first debit", status="being_built")
    other = f.idea(db, merged_in, title="Wrong bank details bounce the first debit", status="merged",
                   merged_into=idea["id"])  # fmt: skip
    db.execute(
        "INSERT INTO merges (lead_idea_uuid, merged_idea_uuid, via, by_user_id) VALUES (%s, %s, 'review_desk', %s)",
        (idea["id"], other["id"], admin["id"]),
    )
    f.crew(db, idea, crew_only)
    f.one(db, f.person(db, "Existing Holder"), number=1)

    assert ones.induct_for_idea(db, idea["id"], actor=admin["id"], now=f.NOW) == []  # not shipped yet
    db.execute("UPDATE ideas SET status = 'shipped' WHERE id = %s", (idea["id"],))
    f.measurement(db, idea, "day_30", None)  # due, not entered
    assert ones.induct_for_idea(db, idea["id"], actor=admin["id"], now=f.NOW) == []
    f.measurement(db, idea, "day_90", {"money": {"amount": 600000, "unit": "rupees a year"}})
    assert ones.induct_for_idea(db, idea["id"], actor=admin["id"], now=f.NOW) == []  # money waits for Finance
    db.execute("UPDATE delivery_measurements SET finance_confirmed_at = %s WHERE mark = 'day_90'", (f.NOW,))

    made = ones.induct_for_idea(db, idea["id"], actor=admin["id"], now=f.NOW)
    assert sorted(m["user_id"] for m in made) == sorted([sharer["id"], merged_in["id"]])  # credited, not crew
    assert sorted(m["number"] for m in made) == [2, 3]  # the next free numbers
    row = db.execute("SELECT * FROM ones WHERE user_id = %s", (sharer["id"],)).fetchone()
    assert row["way_in"] == "accepted_idea" and row["idea_id"] == idea["idea_id"] and row["tier"] == 1
    assert row["swap_until"] == f.NOW + dt.timedelta(days=30)  # P-PRODUCT.promises, from rules/promises.md
    assert len(_audit(db, "ones.inducted", mark)) == 2
    # Idempotent: calling again after the next measurement changes nothing.
    assert ones.induct_for_idea(db, idea["id"], actor=admin["id"], now=f.NOW) == []


def test_L_ONES_rules_1_a_One_an_admin_removed_is_not_brought_back_automatically(ones_db: Conn) -> None:
    db = ones_db
    admin = f.person(db, "Mehul Desai", roles=("admin",))
    sharer = f.person(db, "Ritika Sood")
    idea = f.idea(db, sharer, title="Online forms fill the city from the pin code", status="shipped")
    f.measurement(db, idea, "day_30", {"time": {"amount": 90, "unit": "hours a month"}})
    assert len(ones.induct_for_idea(db, idea["id"], actor=admin["id"], now=f.NOW)) == 1
    ones.remove_one(db, admin["id"], sharer["id"], now=f.NOW)
    assert ones.induct_for_idea(db, idea["id"], actor=admin["id"], now=f.NOW) == []
    assert (
        db.execute("SELECT status FROM ones WHERE user_id = %s", (sharer["id"],)).fetchone()["status"]
        == "retired"
    )


def test_DEC_106_admins_mark_Founding_Ones_and_remove_Ones_and_only_admins(ones_db: Conn) -> None:
    db = ones_db
    mark = _mark(db)
    admin = f.person(db, "Mehul Desai", roles=("admin",))
    someone, a_one = f.person(db, "Ritika Sood"), f.person(db, "Harsh Vora")
    f.one(db, a_one, number=4)
    refused("forbidden", ones.mark_founding, db, someone["id"], a_one["id"], now=f.NOW)
    refused("forbidden", ones.remove_one, db, someone["id"], a_one["id"], now=f.NOW)
    made = ones.mark_founding(db, admin["id"], someone["id"], now=f.NOW)
    kept = ones.mark_founding(db, admin["id"], a_one["id"], now=f.NOW)
    assert kept["number"] == 4  # a One keeps their number and gets the flag
    cards = {c["person"]["name"]: c for c in ones.one_cards(db)}
    assert cards["Ritika Sood"]["flag"] == "founding" and cards["Ritika Sood"]["number"] == made["number"]
    assert cards["Harsh Vora"]["flag_label"] == "Founding One"
    ones.remove_one(db, admin["id"], a_one["id"], now=f.NOW)
    assert "Harsh Vora" not in {c["person"]["name"] for c in ones.one_cards(db)}
    refused("not_found", ones.remove_one, db, admin["id"], a_one["id"], now=f.NOW)
    assert [a["action"] for a in db.execute(
        "SELECT action FROM audit_log WHERE action LIKE 'ones.%%' AND id > %s ORDER BY id", (mark,)).fetchall()] == [
        "ones.founding_marked", "ones.founding_marked", "ones.removed"]  # fmt: skip


# --- S-ONE: the One's own dashboard, the number and the brief ---------------------------------------------------------


def test_S_ONE_rules_1_only_a_One_reads_or_changes_their_dashboard(ones_db: Conn) -> None:
    db = ones_db
    someone = f.person(db, "Ritika Sood")
    for fn, args in ((ones.dashboard, ()), (ones.set_number, (5,)), (ones.propose_brief, ("x" * 30,)),
                     (ones.glow_up_seen, (1,))):  # fmt: skip
        refused("not_a_one", fn, db, someone["id"], *args)
    # Membership first: a non-One never learns what a valid body looks like (BLD-108).
    refused("not_a_one", ones.set_number, db, someone["id"], "not a number")


def test_S_ONE_dashboard_shows_the_number_window_idea_impact_and_brief(ones_db: Conn) -> None:
    db = ones_db
    who = f.person(db, "Ritika Sood", show_name=False)
    idea = f.idea(
        db, who, title="Flag likely-wrong bank details before the first SIP debit", status="shipped"
    )
    f.measurement(db, idea, "day_30", {"time": {"amount": 620, "unit": "hours a month", "line": "Fewer bounced-debit cases"},
                                       "money": {"amount": 1_800_000, "unit": "rupees a year"},
                                       "effort": {"amount": 3, "unit": "fewer steps", "line": "Per new mandate"},
                                       "scale": {"amount": 41, "unit": "branches", "line": "Using it every day"}},
                  finance=True)  # fmt: skip
    f.one(db, who, number=1, tier=4, way_in="founding", idea_ref=idea["idea_id"],
          inducted_at=dt.datetime(2026, 11, 1, 10, 0, tzinfo=f.IST),
          brief="Wrong bank details are caught before the first debit, not after it bounces.")  # fmt: skip
    out = ones.dashboard(db, who["id"], now=f.NOW)
    # Their own name shows to them even though they hid it from the Wall.
    assert out["one"]["person"]["name"] == "Ritika Sood" and out["one"]["tier_label"] == "Tier 4, Blaze"
    assert out["one"]["flag_label"] == "Founding One" and out["since_label"] == "1 Nov 2026"
    assert out["number_window"] == {
        "open": True, "until": "2026-12-01T04:30:00+00:00", "until_label": "1 Dec 2026", "number": 1,
        "keep_label": "Keep No. 1, or choose any free number from 1 to 999 until 1 Dec 2026. First come, first "
                      "served. After that, it's yours.",
    }  # fmt: skip
    assert out["headline"] == "You're No. 1"
    assert out["since_line"] == "Tier 4, Blaze. Founding One since 1 Nov 2026."
    assert out["idea"] == {"id": idea["idea_id"], "title": idea["title"], "status": "shipped"}
    assert out["impact"] == {
        "time": {"value": "620 hours a month", "line": "Fewer bounced-debit cases"},
        "money": {"value": "₹18 lakh a year", "line": "Finance confirmed", "finance_confirmed": True},
        "effort": {"value": "3 fewer steps", "line": "Per new mandate"},
        "scale": {"value": "41 branches", "line": "Using it every day"},
    }
    assert out["brief"] == {"text": "Wrong bank details are caught before the first debit, not after it bounces.",
                            "pending": False}  # fmt: skip
    assert out["tier_moment"] is None
    # ...and on the Wall the same One shows without a name (DEC-104).
    assert ones.one_cards(db)[0]["person"] is None


def test_L_ONES_rules_2_number_swap_free_taken_out_of_range_and_locked(ones_db: Conn) -> None:
    db = ones_db
    mark = _mark(db)
    who = f.person(db, "Ritika Sood")
    oid = f.one(db, who, number=1)
    for n in (2, 3, 4, 5, 7, 9, 10):
        f.one(db, f.person(db, f"Holder {n}"), number=n)
    for bad in (0, 1000, "abc", True, 3.5, None, "12a"):
        e = refused("out_of_range", ones.set_number, db, who["id"], bad, now=f.NOW)
        assert e.body() == {
            "error": {"code": "out_of_range", "message": "Pick a number from 1 to 999.", "field": "number"}
        }
    e = refused("taken", ones.set_number, db, who["id"], 7, now=f.NOW)
    assert e.body()["error"] == {"code": "taken", "message": "No. 7 is taken. Free numbers near it: 6, 8, 11.",
                                 "field": "number", "near": [6, 8, 11]}  # fmt: skip
    assert ones.set_number(db, who["id"], "17", now=f.NOW)["number_window"]["number"] == 17
    assert (
        ones.set_number(db, who["id"], 17, now=f.NOW)["number_window"]["number"] == 17
    )  # same again: no change
    assert len(_audit(db, "ones.number_changed", mark)) == 1
    assert ones.nearest_free(db, 2, oid, f.NOW) == [
        1,
        6,
        8,
    ]  # their old number rests for others, not for them
    # The window is 30 days from becoming a One (f.one: inducted two days before NOW): open a day before it ends,
    # closed a day after.
    assert (
        ones.set_number(db, who["id"], 18, now=f.NOW + dt.timedelta(days=27))["number_window"]["open"] is True
    )
    later = f.NOW + dt.timedelta(days=29)
    e = refused("window_closed", ones.set_number, db, who["id"], 19, now=later)
    assert e.message == "No. 18 is yours for good."
    # A closed window answers the same whatever was typed (V-FIELDS.one/3).
    assert refused("window_closed", ones.set_number, db, who["id"], "abc", now=later).field == "number"
    window = ones.dashboard(db, who["id"], now=later)["number_window"]
    assert window["open"] is False and window["locked_label"] == "No. 18 is yours for good."
    assert "keep_label" not in window


def test_L_ONES_rules_5_a_new_brief_waits_for_the_programme_team(ones_db: Conn) -> None:
    db = ones_db
    admin = f.person(db, "Mehul Desai", roles=("admin",))
    who = f.person(db, "Ritika Sood")
    oid = f.one(db, who, number=3, brief="Distributors now see why an SIP registration is stuck.")
    for bad in ("Too short.", "x" * 141, "Two sentences here. And another one after it.", 42):
        e = refused("brief_invalid", ones.propose_brief, db, who["id"], bad, now=f.NOW)
        assert e.message == "Keep it to one sentence, up to 140 characters." and e.field == "text"
    refused(
        "personal_data",
        ones.propose_brief,
        db,
        who["id"],
        "Call the investor on 9876543210 about it",
        now=f.NOW,
    )
    new = "Stuck SIP registrations now explain themselves on IRIS."
    assert ones.propose_brief(db, who["id"], new, now=f.NOW) == {
        "brief": {"text": "Distributors now see why an SIP registration is stuck.", "pending": True}}  # fmt: skip
    assert ones.one_cards(db)[0]["brief"] == "Distributors now see why an SIP registration is stuck."
    refused("forbidden", ones.approve_brief, db, who["id"], oid)  # never the One themself
    ones.approve_brief(db, admin["id"], oid, now=f.NOW)
    assert ones.one_cards(db)[0]["brief"] == new
    assert ones.dashboard(db, who["id"], now=f.NOW)["brief"] == {"text": new, "pending": False}
    ones.propose_brief(db, who["id"], "A brief the programme team will not take, sadly.", now=f.NOW)
    ones.decline_brief(db, admin["id"], oid)
    assert ones.dashboard(db, who["id"], now=f.NOW)["brief"] == {"text": new, "pending": False}
    stored = db.execute("SELECT brief_encrypted FROM ones WHERE id = %s", (oid,)).fetchone()[
        "brief_encrypted"
    ]
    assert new.encode() not in bytes(stored)  # encrypted at rest


def test_L_ONES_rules_3_the_glow_up_plays_once_with_the_committees_message(ones_db: Conn) -> None:
    db = ones_db
    chair = f.person(db, "Vikram Chawla", roles=("core_committee",))
    who = f.person(db, "Ritika Sood")
    f.idea(db, who, title="Shipped one", status="shipped")
    f.idea(db, who, title="Being built one", status="being_built")
    f.idea(db, who, title="With the desk", status="with_review_desk")
    oid = f.one(db, who, number=17, tier=2)
    p = db.execute("INSERT INTO one_proposals (kind, one_id, subject_user_id, tier_to, proposed_by, state) "
                   "VALUES ('tier_up', %s, %s, 2, %s, 'carried_out') RETURNING id",
                   (oid, who["id"], chair["id"])).fetchone()["id"]  # fmt: skip
    m = db.execute("INSERT INTO one_messages (proposal_id, author_user_id, author_role) VALUES (%s, %s, 'committee') "
                   "RETURNING id", (p, chair["id"])).fetchone()["id"]  # fmt: skip
    note = "Distributors stopped calling about stuck SIP registrations within a month."
    db.execute(
        "UPDATE one_messages SET text_encrypted = %s WHERE id = %s", (seal(note, f"one_message:{m}"), m)
    )
    g = db.execute("INSERT INTO one_glow_ups (one_id, proposal_id, tier_from, tier_to) VALUES (%s, %s, 1, 2) "
                   "RETURNING id", (oid, p)).fetchone()["id"]  # fmt: skip
    moment = ones.dashboard(db, who["id"], now=f.NOW)["tier_moment"]
    assert moment == {"id": g, "from": 1, "to": 2, "from_label": "Tier 1, Spark", "to_label": "Tier 2, Glow",
                      "title": "No. 17, your spark is hotter", "line": "From Tier 1, Spark to Tier 2, Glow",
                      "story": {"shared": 3, "picked": 1, "shipped": 1},
                      "messages": [{"text": note, "from_label": "From the core committee: Vikram Chawla"}]}  # fmt: skip
    assert ones.dashboard(db, who["id"], now=f.NOW)["tier_moment"] is not None  # reading changes nothing
    refused("not_found", ones.glow_up_seen, db, who["id"], g + 999)
    assert ones.glow_up_seen(db, who["id"], g) == {"seen": True}
    assert ones.dashboard(db, who["id"], now=f.NOW)["tier_moment"] is None


# --- S-WALL.ones and C-ONES-FAN: what everyone reads ------------------------------------------------------------------


def test_S_WALL_ones_cards_in_order_and_the_leaderboard_by_tier_then_hours(ones_db: Conn) -> None:
    db = ones_db
    a, b, c = (f.person(db, n) for n in ("Ritika Sood", "Harsh Vora", "Leela Nambiar"))
    f.one(
        db,
        a,
        number=1,
        tier=4,
        way_in="founding",
        inducted_at=f.ago(days=30),
        brief="First brief, for the Wall.",
    )
    f.one(db, b, number=17, tier=2, inducted_at=f.ago(days=3))
    f.one(db, c, number=9, tier=5, inducted_at=f.ago(days=2))
    wall = ones.one_cards(db)
    assert [x["number"] for x in wall] == [1, 17, 9]
    assert wall[0] == {"number": 1, "person": wall[0]["person"], "tier": 4, "tier_name": "Blaze",
                       "tier_label": "Tier 4, Blaze", "flag": "founding", "flag_label": "Founding One",
                       "brief": "First brief, for the Wall."}  # fmt: skip
    assert set(wall[0]["person"]) == {"id", "name", "first_name", "initials", "area", "city"}
    assert [x["number"] for x in ones.one_cards(db, "leaderboard")] == [9, 1, 17]
    refused("bad_order", ones.one_cards, db, "loudest")


def test_L_ONES_rules_7_posts_with_likes_comments_and_the_thread(ones_db: Conn) -> None:
    db = ones_db
    who, fan = f.person(db, "Ritika Sood"), f.person(db, "Harsh Vora")
    oid = f.one(db, who, number=11, tier=3)
    idea = f.idea(db, who, title="Payout checks", status="shipped")
    db.execute("INSERT INTO conversation_entries (idea_uuid, type, author_user_id, text_encrypted) "
               "VALUES (%s, 'message', %s, '\\x00')", (idea["id"], fan["id"]))  # fmt: skip
    pid = f.post(db, oid, idea, "Payout checks are live at every branch.", hours_ago=49)
    out = ones.posts(db, fan["id"], f.NOW)
    assert out == [{"id": pid, "one": out[0]["one"], "text": "Payout checks are live at every branch.", "ago": "2d",
                    "shipped": True, "figure": {"value": "620", "line": "hours a month saved"}, "likes": 0,
                    "liked": False, "comments": 1, "thread_to": f"/ideas/{idea['idea_id']}"}]  # fmt: skip
    assert out[0]["one"]["number"] == 11 and out[0]["one"]["tier_label"] == "Tier 3, Flame"
    assert ones.like(db, fan["id"], pid, True) == {"id": pid, "liked": True, "likes": 1}
    assert ones.like(db, fan["id"], pid, True)["likes"] == 1  # liking twice counts once
    assert ones.posts(db, fan["id"], f.NOW)[0]["liked"] is True
    assert ones.like(db, fan["id"], pid, False)["likes"] == 0
    refused("liked_required", ones.like, db, fan["id"], pid, "yes")
    refused("not_found", ones.like, db, fan["id"], "not-a-uuid", True)
    db.execute("UPDATE ones SET status = 'retired', number = NULL WHERE id = %s", (oid,))
    assert ones.posts(db, fan["id"], f.NOW) == []  # a removed One's posts leave Home
