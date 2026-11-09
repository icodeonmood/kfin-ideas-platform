"""The Ones module (DEC-034 to DEC-087): jersey numbers, the propose / approve / carry-out flow, tier changes with
their messages and glow-up, impact briefs, the Showcase brief, public views, the leaderboard, the manager's view,
announcements and their messages. Synthetic people only."""

from __future__ import annotations

import datetime as dt
import secrets
from collections.abc import Iterator
from typing import Any

import pytest

from comms import render, route, templates
from core import killswitch
from gateway import limits
from gateway.routes import FAKE_SCRIPT
from ones import numbers, service, views
from ones.text import OnesRefused
from tests import helpers

pytestmark = pytest.mark.stack
NOW = dt.datetime(2026, 12, 14, 10, 0, tzinfo=dt.UTC)
CITATION = "Rebuilt the dividend reconciliation checks so every AMC stops reprocessing by hand"
TITLE = "Dividend reconciliation checks for every AMC"


@pytest.fixture
def ones_db(db: Any, company_repo: Any, test_database: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    killswitch.clear_cache()
    limits.reset()
    FAKE_SCRIPT.clear()
    settings = helpers.settings_for(company_repo, test_database)
    for module in (route, render, templates):
        monkeypatch.setattr(module, "get_settings", lambda: settings)
    templates._load.cache_clear()
    db.execute("DELETE FROM jobs")
    yield db
    killswitch.clear_cache()


def person(
    db: Any, *roles: str, name: str | None = None, consent: bool = False, manager: str | None = None
) -> str:
    tag = secrets.token_hex(3)
    row = db.execute(
        "INSERT INTO users (emp_id_hash, name, email, source, manager_user_id, lob_id) "
        "VALUES (%s, %s, %s, 'hr', %s, 'LOB-mf') RETURNING id",
        (f"test:{tag}", name or f"Synthetic Person {tag}", f"p.{tag}@kfintech.example", manager),
    ).fetchone()
    uid = str(row["id"])
    db.execute(
        "INSERT INTO contributor_map (contributor_code, user_id) VALUES (%s, %s)",
        (f"CTR-{secrets.token_hex(3)}", uid),
    )
    for role in roles:
        db.execute("INSERT INTO role_grants (user_id, role) VALUES (%s, %s)", (uid, role))
    if consent:
        db.execute("INSERT INTO comms_prefs (user_id, public_name_consent) VALUES (%s, true)", (uid,))
    return uid


def email(db: Any, uid: str) -> str:
    return str(db.execute("SELECT email FROM users WHERE id = %s", (uid,)).fetchone()["email"])


@pytest.fixture
def cast(ones_db: Any) -> dict[str, str]:
    db = ones_db
    return {
        "member": person(db, "core_committee"),
        "chair": person(db, "core_committee", "core_chair"),
        "ceo": person(db, "ceo", name="Demo CEO"),
        "admin": person(db, "admin"),
        "employee": person(db),
    }


def induct(
    db: Any, cast: dict[str, str], subject: str, *, way_in: str = "sponsored", now: dt.datetime = NOW
) -> dict[str, Any]:
    p = service.propose(
        db, cast["member"], {"kind": "include", "way_in": way_in, "email": email(db, subject), "title": TITLE,
                             "reason": CITATION}, now=now)  # fmt: skip
    service.decide(db, cast["chair"], p["id"], {"verdict": "approve", "how": "chair"}, now=now)
    return service.carry_out(db, cast["admin"], p["id"], now=now)


def refused(code: str, fn: Any, *args: Any, **kw: Any) -> None:
    with pytest.raises(OnesRefused) as exc:
        fn(*args, **kw)
    assert exc.value.code == code, exc.value.code


# --- Numbers ---------------------------------------------------------------------------------------------------------


def test_numbers_come_in_order_rest_after_retirement_and_swap_only_in_the_first_30_days(
    ones_db: Any, cast: Any
) -> None:
    db = ones_db
    a, b, c = person(db), person(db), person(db)
    first = induct(db, cast, a)["number"]
    second = induct(db, cast, b)["number"]
    assert second == first + 1  # the next number after the last one the system allocated

    removal = service.propose(db, cast["member"], {"kind": "remove", "one_id": induct(db, cast, c)["one_id"],
                                                  "reason": "Membership lapsed after twelve months"}, now=NOW)  # fmt: skip
    third = db.execute("SELECT number FROM ones WHERE user_id = %s", (c,)).fetchone()["number"]
    service.decide(db, cast["member"], removal["id"], {"verdict": "approve", "how": "majority",
                                                        "meeting_on": NOW.date().isoformat()}, now=NOW)  # fmt: skip
    service.carry_out(db, cast["admin"], removal["id"], now=NOW)
    assert not numbers.is_free(db, third, 0, NOW + dt.timedelta(days=30))  # resting for six months
    assert numbers.is_free(db, third, 0, NOW + numbers.REST + dt.timedelta(days=1))
    assert {"number": third, "until": (NOW + numbers.REST).isoformat()} in numbers.resting(db, NOW)

    refused("number_taken", service.swap_number, db, a, third, now=NOW)  # resting
    refused("number_taken", service.swap_number, db, a, second, now=NOW)  # worn by someone else
    free = next(n for n in range(500, 999) if numbers.is_free(db, n, 0, NOW))
    assert service.swap_number(db, a, free, now=NOW + dt.timedelta(days=29)) == {"number": free}
    assert not numbers.is_free(db, first, 0, NOW + dt.timedelta(days=29))  # their old number now rests
    refused("swap_window_closed", service.swap_number, db, a, free + 1, now=NOW + dt.timedelta(days=31))
    refused("not_a_one", service.swap_number, db, cast["employee"], free + 1, now=NOW)
    # Membership is checked before the body (BLD-108).
    refused("not_a_one", service.swap_number, db, cast["employee"], None, now=NOW)
    actions = [
        r["action"]
        for r in db.execute("SELECT action FROM audit_log WHERE entity LIKE 'one%' ORDER BY id").fetchall()
    ]
    assert "ones.number_changed" in actions and "ones.carried_out" in actions


def test_after_999_the_system_gives_the_lowest_free_number(ones_db: Any, cast: Any) -> None:
    db = ones_db
    db.execute("INSERT INTO id_counters (kind, period, last_value) VALUES ('ONE-NO', '', 999) "
               "ON CONFLICT (kind, period) DO UPDATE SET last_value = 999")  # fmt: skip
    got = induct(db, cast, person(db))["number"]
    assert got == next(n for n in range(1, 1000) if numbers.is_free(db, n, -1, NOW) or n == got)


def test_a_legend_number_is_retired_for_good_at_most_once_a_year(ones_db: Any, cast: Any) -> None:
    db = ones_db
    a, b = person(db), person(db)
    one_a = induct(db, cast, a)
    one_b = induct(db, cast, b)
    for one in (one_a, one_b):
        p = service.propose(db, cast["member"], {"kind": "legend", "one_id": one["one_id"],
                                                "reason": "Biggest measured impact of the year"}, now=NOW)  # fmt: skip
        service.decide(db, cast["chair"], p["id"], {"verdict": "approve", "how": "chair"}, now=NOW)
        if one is one_a:
            service.carry_out(db, cast["admin"], p["id"], now=NOW)
        else:
            refused("legend_this_year", service.carry_out, db, cast["admin"], p["id"], now=NOW)
    assert not numbers.is_free(db, one_a["number"], 0, NOW + dt.timedelta(days=4000))


# --- The flow and who may do what ------------------------------------------------------------------------------------


def test_only_the_right_people_propose_approve_and_carry_out(ones_db: Any, cast: Any) -> None:
    db = ones_db
    subject = person(db)
    body = {
        "kind": "include",
        "way_in": "founding",
        "email": email(db, subject),
        "title": TITLE,
        "reason": CITATION,
    }
    refused("forbidden", service.propose, db, cast["employee"], body, now=NOW)
    refused("forbidden", service.propose, db, cast["admin"], body, now=NOW)
    refused("forbidden", service.propose, db, cast["ceo"], {**body, "kind": "remove", "one_id": 1}, now=NOW)
    refused(
        "own_proposal",
        service.propose,
        db,
        cast["member"],
        {**body, "email": email(db, cast["member"])},
        now=NOW,
    )
    p = service.propose(db, cast["ceo"], body, now=NOW)  # the CEO sponsors
    refused("already_proposed", service.propose, db, cast["member"], body, now=NOW)

    refused("not_approved", service.carry_out, db, cast["admin"], p["id"], now=NOW)
    refused(
        "chair_only",
        service.decide,
        db,
        cast["member"],
        p["id"],
        {"verdict": "approve", "how": "chair"},
        now=NOW,
    )
    refused("meeting_date_required", service.decide, db, cast["member"], p["id"],
            {"verdict": "approve", "how": "majority"}, now=NOW)  # fmt: skip
    refused("meeting_date_not_valid", service.decide, db, cast["member"], p["id"],
            {"verdict": "approve", "how": "majority", "meeting_on": "2027-01-01"}, now=NOW)  # fmt: skip
    service.decide(db, cast["chair"], p["id"], {"verdict": "approve", "how": "chair"}, now=NOW)
    refused(
        "not_open",
        service.decide,
        db,
        cast["chair"],
        p["id"],
        {"verdict": "decline", "how": "chair"},
        now=NOW,
    )
    refused("forbidden", service.carry_out, db, cast["chair"], p["id"], now=NOW)
    out = service.carry_out(db, cast["admin"], p["id"], now=NOW)
    one = db.execute("SELECT * FROM ones WHERE id = %s", (out["one_id"],)).fetchone()
    assert one["way_in"] == "founding" and one["tier"] == 1 and one["status"] == "active"
    assert one["swap_until"] == NOW + numbers.SWAP_WINDOW

    # The chair never approves their own proposal alone; a recorded majority can.
    own = service.propose(db, cast["chair"], {**body, "email": email(db, person(db))}, now=NOW)
    refused(
        "own_proposal",
        service.decide,
        db,
        cast["chair"],
        own["id"],
        {"verdict": "approve", "how": "chair"},
        now=NOW,
    )
    service.decide(db, cast["chair"], own["id"], {"verdict": "approve", "how": "majority",
                                                  "meeting_on": NOW.date().isoformat()}, now=NOW)  # fmt: skip
    decided = db.execute(
        "SELECT approval, meeting_on FROM one_proposals WHERE id = %s", (own["id"],)
    ).fetchone()
    assert decided["approval"] == "majority" and decided["meeting_on"] == NOW.date()

    # Every step is on record, with codes and IDs only.
    rows = db.execute("SELECT action, after::text AS after FROM audit_log WHERE entity = %s ORDER BY id DESC LIMIT 3",
                      (f"one_proposal:{p['id']}",)).fetchall()  # fmt: skip
    assert [r["action"] for r in reversed(rows)] == ["ones.proposed", "ones.approved", "ones.carried_out"]
    assert all(CITATION not in r["after"] and TITLE not in r["after"] for r in rows)
    job = db.execute(
        "SELECT payload FROM jobs WHERE type = 'comms.route' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert job["payload"]["event"] == "ones.inducted"


def test_free_text_is_checked_before_it_is_stored(ones_db: Any, cast: Any) -> None:
    db = ones_db
    body = {"kind": "include", "way_in": "sponsored", "email": email(db, person(db)), "title": TITLE}
    refused(
        "personal_data",
        service.propose,
        db,
        cast["member"],
        {**body, "reason": "Fixed the record for PAN ABCPK1234F last week"},
        now=NOW,
    )
    refused("text_too_short", service.propose, db, cast["member"], {**body, "reason": "Great"}, now=NOW)
    one = induct(db, cast, person(db))
    subject = db.execute("SELECT user_id FROM ones WHERE id = %s", (one["one_id"],)).fetchone()["user_id"]
    refused("text_too_long", service.propose_brief, db, str(subject), "If this works " + "word " * 40)
    sealed = db.execute("SELECT reason_encrypted FROM one_proposals ORDER BY id DESC LIMIT 1").fetchone()
    assert CITATION.encode() not in bytes(sealed["reason_encrypted"])


def test_an_impact_brief_shows_once_the_committee_approves_it(ones_db: Any, cast: Any) -> None:
    db = ones_db
    subject = person(db, consent=True, name="Ananya Rao")
    induct(db, cast, subject)
    brief = "If this works: new investors never fill a nominee form twice."
    p = service.propose_brief(db, subject, brief, now=NOW)
    assert views.my_one(db, subject, now=NOW)["brief_pending"]
    assert views.public(db)["ones"][0]["brief"] is None
    assert (
        service.decide(db, cast["chair"], p["id"], {"verdict": "approve", "how": "chair"}, now=NOW)["state"]
        == "carried_out"
    )
    card = next(c for c in views.public(db)["ones"] if c["name"] == "Ananya Rao")
    assert card["brief"] == brief and card["tier_name"] == "Spark" and card["line"] == TITLE


def test_a_tier_change_needs_the_committees_message_and_plays_a_glow_up_once(ones_db: Any, cast: Any) -> None:
    db = ones_db
    subject, peer = person(db), person(db, name="Synthetic Colleague")
    one = induct(db, cast, subject)
    p = service.propose(db, cast["member"], {"kind": "tier_up", "one_id": one["one_id"], "tier_to": 3,
                                            "reason": "Shipped and measured at ninety days"}, now=NOW)  # fmt: skip
    refused("tier_not_valid", service.propose, db, cast["member"], {"kind": "tier_down", "one_id": one["one_id"],
            "tier_to": 2, "reason": "Not a lower tier than the current one"}, now=NOW)  # fmt: skip
    service.decide(db, cast["chair"], p["id"], {"verdict": "approve", "how": "chair"}, now=NOW)
    refused("committee_message_required", service.carry_out, db, cast["admin"], p["id"], now=NOW)

    refused(
        "forbidden",
        service.add_message,
        db,
        cast["employee"],
        p["id"],
        {"from": "committee", "text": "Well done on all of it"},
    )
    refused(
        "not_invited",
        service.add_message,
        db,
        peer,
        p["id"],
        {"from": "peer", "text": "Proud to have built this with you"},
    )
    service.add_message(
        db,
        cast["member"],
        p["id"],
        {"from": "committee", "text": "Your fix changed how every AMC works with us."},
    )
    service.add_message(
        db, cast["ceo"], p["id"], {"from": "ceo", "text": "This is what the 1% Club is for. Thank you."}
    )
    service.invite_peer(db, cast["member"], p["id"], email(db, peer))
    service.add_message(db, peer, p["id"], {"from": "peer", "text": "Proud to have built this with you."})
    refused(
        "already_written",
        service.add_message,
        db,
        peer,
        p["id"],
        {"from": "peer", "text": "And once more, thank you."},
    )

    service.carry_out(db, cast["admin"], p["id"], now=NOW)
    mine = views.my_one(db, subject, now=NOW)
    assert mine["tier"] == 3 and mine["tier_name"] == "Flame"
    glow = mine["glow_up"]
    assert glow["from"]["tier"] == 1 and glow["to"]["tier_colour"] == "#FFC21F" and glow["up"]
    assert [m["from"] for m in glow["messages"]] == ["committee", "ceo", "peer"]
    assert (
        glow["messages"][0]["name"] == "The 1% Club core committee"
        and glow["messages"][1]["name"] == "Demo CEO"
    )
    assert any(m["what"] == "Reached Flame" for m in glow["story"]["milestones"])
    assert service.glow_up_seen(db, subject, glow["id"]) and views.my_one(db, subject)["glow_up"] is None
    assert not service.glow_up_seen(db, subject, glow["id"])  # plays once

    job = db.execute(
        "SELECT payload FROM jobs WHERE type = 'comms.route' AND payload->>'event' = 'ones.tier_changed'"
    ).fetchone()
    data = render.variables(db, subject, "ones.tier_changed", job["payload"]["refs"])
    subject_line, body, _ = templates.render("one-tier-changed", data)
    assert subject_line == "Your spark is hotter: Flame" and "from Spark to **Flame**" in body
    assert "Your fix changed how every AMC works with us." in body


def test_people_hear_about_their_own_changes_and_everyone_hears_about_new_ones(
    ones_db: Any, cast: Any
) -> None:
    db = ones_db
    named = person(db, consent=True, name="Lakshmi Iyer")
    quiet = person(db, name="Prefers Not Shown")
    one_named, one_quiet = induct(db, cast, named), induct(db, cast, quiet)
    db.execute("DELETE FROM jobs")
    refused("forbidden", service.announce, db, cast["member"], now=NOW)
    assert service.announce(db, cast["admin"], now=NOW) == {"announced": 2}
    refused("nothing_to_announce", service.announce, db, cast["admin"], now=NOW)

    job = db.execute("SELECT payload FROM jobs WHERE type = 'comms.route'").fetchone()
    assert route.route(db, "ones.announced", job["payload"]["refs"], now=NOW) >= 2
    data = render.variables(db, cast["employee"], "ones.announced", job["payload"]["refs"])
    _, body, _ = templates.render("ones-announced", data)
    assert f"No. {one_named['number']}, Lakshmi Iyer." in body
    assert f"One No. {one_quiet['number']}." in body and "Prefers Not Shown" not in body

    data = render.variables(
        db, named, "ones.inducted", {"current_owner_ids": [named], "one_id": one_named["one_id"]}
    )
    subject_line, body, _ = templates.render("one-inducted", data)
    assert subject_line == f"You're No. {one_named['number']}." and "Tier 1, Spark" in body


# --- Views -----------------------------------------------------------------------------------------------------------


def test_the_public_view_respects_consent_finance_and_the_switch(ones_db: Any, cast: Any) -> None:
    db = ones_db
    named, quiet = person(db, consent=True, name="Ananya Rao"), person(db, name="Farhan Qureshi")
    one_named = induct(db, cast, named, way_in="founding")
    induct(db, cast, quiet)
    service.set_measures(db, cast["admin"], one_named["one_id"], {
        "time": {"value": 120, "unit": "hours a month"},
        "money": {"value": 450000, "unit": "rupees a year", "finance_confirmed": False},
        "scale": {"value": 30000, "unit": "folios a month"}})  # fmt: skip
    refused(
        "time_not_valid",
        service.set_measures,
        db,
        cast["admin"],
        one_named["one_id"],
        {"time": {"value": 1, "unit": "lots"}},
    )
    cards = views.public(db)["ones"]
    assert {c["name"] for c in cards} == {"Ananya Rao", None}
    founding = next(c for c in cards if c["name"] == "Ananya Rao")
    assert (
        founding["founding"]
        and "money" not in founding["measures"]
        and founding["measures"]["time"]["value"] == 120
    )
    service.set_measures(db, cast["admin"], one_named["one_id"], {
        "money": {"value": 450000, "unit": "rupees a year", "finance_confirmed": True}})  # fmt: skip
    assert (
        next(c for c in views.public(db)["ones"] if c["name"] == "Ananya Rao")["measures"]["money"]["value"]
        == 450000
    )

    sky = views.constellation(db)
    assert sky["mode"] == "static" and len(sky["sparks"]) == 2
    refused("forbidden", service.set_screen_mode, db, cast["member"], "ambient")
    service.set_screen_mode(db, cast["admin"], "ambient")
    assert views.constellation(db)["mode"] == "ambient"

    killswitch.set_switch(db, "ones.public", "off", reason="testing the switch hides the Ones", actor="test")
    killswitch.clear_cache()
    try:
        assert views.public(db) == {"paused": True, "ones": []} and views.constellation(db)["paused"]
    finally:
        killswitch.set_switch(
            db, "ones.public", "on", reason="testing done, Ones visible again", actor="test"
        )
        killswitch.clear_cache()


def test_the_leaderboard_is_for_ones_and_ranks_by_tier_then_impact(ones_db: Any, cast: Any) -> None:
    db = ones_db
    a, b = person(db, name="Tier One Synthetic"), person(db, name="Tier Four Synthetic", consent=True)
    quiet = person(db, name="Tier Two Quiet Synthetic")
    induct(db, cast, a)
    one_b, one_q = induct(db, cast, b), induct(db, cast, quiet)
    db.execute("UPDATE ones SET tier = 4 WHERE id = %s", (one_b["one_id"],))
    db.execute("UPDATE ones SET tier = 2 WHERE id = %s", (one_q["one_id"],))
    assert views.leaderboard(db, cast["employee"]) is None
    board = views.leaderboard(db, a)
    # Tier first; a name shows only with consent (the quiet One is a number), and you always see your own.
    assert [p["name"] for p in board["people"]][:3] == ["Tier Four Synthetic", None, "Tier One Synthetic"]
    assert board["people"][1]["number"] == one_q["number"]
    assert board["people"][2]["you"] and board["teams"][0]["ones"] >= 3
    assert "Tier Two Quiet Synthetic" not in str(board)


def test_a_manager_sees_counts_for_their_own_team_only(ones_db: Any, cast: Any) -> None:
    db = ones_db
    manager = person(db, name="Synthetic Manager")
    report = person(db, name="Synthetic Report", manager=manager)
    person(db, name="Someone Else")
    induct(db, cast, report)
    seen = views.team(db, manager)
    assert [p["name"] for p in seen["people"]] == ["Synthetic Report"]
    assert seen["people"][0]["one"]["tier_name"] == "Spark" and seen["ones"] == 1
    assert views.team(db, cast["employee"])["people"] == []


def test_the_showcase_brief_fills_from_the_record_and_keeps_the_ones_words(ones_db: Any, cast: Any) -> None:
    db = ones_db
    subject = person(db)
    one = induct(db, cast, subject)
    refused("not_a_one", service.save_showcase, db, cast["employee"], {"help": "A sponsor in operations"})
    refused("personal_data", service.save_showcase, db, subject, {"team": "Call me on 9876543210"})
    service.save_showcase(
        db, subject, {"timelines": "Pilot in January, all AMCs by March", "help": "A sponsor in operations"}
    )
    brief = views.showcase(db, one["one_id"])
    parts = {p["key"]: p for p in brief["parts"]}
    assert list(parts) == list(service.SHOWCASE_PARTS)
    assert parts["idea"]["from_record"] == TITLE and parts["timelines"]["own"].startswith("Pilot in January")
    assert views.console(db)["ones"][0]["showcase_updated"] is not None


def test_the_ones_night_marks_one_award_per_category_a_year(ones_db: Any, cast: Any) -> None:
    db = ones_db
    one = induct(db, cast, person(db))
    service.award(db, cast["admin"], one["one_id"], {"category": "time", "year": 2026}, now=NOW)
    refused(
        "award_given",
        service.award,
        db,
        cast["admin"],
        one["one_id"],
        {"category": "time", "year": 2026},
        now=NOW,
    )
    refused("forbidden", service.award, db, cast["chair"], one["one_id"], {"category": "money"}, now=NOW)
    assert views.console(db)["awards"][0]["category"] == "time"


def test_the_committee_flow_can_propose_the_owner_of_an_accepted_idea(ones_db: Any, cast: Any) -> None:
    db = ones_db
    owner = person(db)
    code = db.execute("SELECT contributor_code FROM contributor_map WHERE user_id = %s", (owner,)).fetchone()
    idea_id = helpers.insert_idea(db, contributor=code["contributor_code"], stage="picked")
    pid = service.induct_from_decision(db, idea_id, cast["chair"], NOW.date(), now=NOW)
    assert (
        pid is not None
        and service.induct_from_decision(db, idea_id, cast["chair"], NOW.date(), now=NOW) is None
    )
    out = service.carry_out(db, cast["admin"], pid, now=NOW)
    assert db.execute("SELECT way_in, idea_id FROM ones WHERE id = %s", (out["one_id"],)).fetchone() == {
        "way_in": "accepted_idea", "idea_id": idea_id}  # fmt: skip
