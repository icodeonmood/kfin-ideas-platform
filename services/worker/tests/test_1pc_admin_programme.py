"""The programme team's admin path, worker side (lane A; journey J-ONE steps 1, 2, 3 and 6):
L-DECIDE.after (build team, shipped), L-IMPACT (measurements, Finance, the due list), L-ONES.rules/1-3 through
lane E's entry points (induction, Founding Ones and removal, DEC-106) with lane A's tiers, "Take off the Wall"
(SHIP_PLAN §6.3) through lane E's one Wall filter, and L-AUDIT.flags. Synthetic people only (non-negotiable 11);
every test leaves the database as it found it (crunch rule 14)."""

from __future__ import annotations

import datetime as dt
import secrets
import uuid
from typing import Any

import pytest

from core.db import Conn
from programme import build, flags, impact, ones, view, wall
from programme.common import Refused
from tests import wall_fixtures
from wall import impact as wall_impact
from wall import kindling

pytestmark = pytest.mark.stack

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
NOW = dt.datetime(2026, 11, 18, 11, 0, tzinfo=IST)
_n = iter(range(1, 10**6))


@pytest.fixture
def posted(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Every notify.post call the admin path makes (the inbox body lands separately, BLD-A180). Only J-ONE step 1
    tells anyone (BLD-A211); measurements, inductions and tier rises post nothing at launch (BLD-A186)."""
    import notify

    calls: list[dict[str, Any]] = []

    def fake(conn: Conn, kind: Any, recipients: Any, **kw: Any) -> None:
        notify.post(conn, kind, recipients, **kw)  # the validating stub: E-ENUMS.inbox kinds, IDs-only refs
        calls.append({"kind": kind, "to": sorted(recipients), **kw})

    monkeypatch.setattr(build, "post", fake)
    assert not hasattr(impact, "post") and not hasattr(ones, "post")
    return calls


def person(db: Conn, name: str, *roles: str) -> dict[str, str]:
    """A synthetic person who signed in (not an HR row, so the seed's HR import is never refused)."""
    uid, code = str(uuid.uuid4()), f"CTR-{secrets.token_hex(3)}"
    email = f"{name.split()[0].lower()}.{next(_n)}@kfintech.example"
    db.execute(
        "INSERT INTO users (id, emp_id_hash, name, email, first_name, source) VALUES (%s, %s, %s, %s, %s, 'sign_in')",
        (uid, f"hash-{uid}", name, email, name.split()[0]),
    )
    db.execute("INSERT INTO contributor_map (contributor_code, user_id) VALUES (%s, %s)", (code, uid))
    for role in roles:
        db.execute("INSERT INTO role_grants (user_id, role) VALUES (%s, %s)", (uid, role))
    return {"id": uid, "code": code, "email": email, "name": name}


def an_idea(
    db: Conn, sharer: dict[str, str], status: str = "picked", title: str = "Mandate checks"
) -> dict[str, Any]:
    ref = f"IDEA-2026-{800000 + next(_n):06d}"
    row = db.execute(
        "INSERT INTO ideas (idea_id, contributor_code, status, title, summary, shared_at) "
        "VALUES (%s, %s, %s, %s, %s, %s) RETURNING *",
        (ref, sharer["code"], status, title, f"Short summary: {title.lower()}.", NOW - dt.timedelta(days=40)),
    ).fetchone()
    assert row is not None
    return dict(row)


_AUDIT_FROM = [0]  # audit_log is append-only and outlives each test; read only this test's rows
# The One-number and induction counters live in id_counters, which no truncate touches: put them back as found, so a
# later test's "next free number" is what it expects (crunch rule 14).
_COUNTERS = ["ONE-NO", "ONE"]


@pytest.fixture
def cast(db: Conn) -> Any:
    kindling.clear_cache()
    _AUDIT_FROM[0] = int(db.execute("SELECT coalesce(max(id), 0) AS n FROM audit_log").fetchone()["n"])
    counters = db.execute(
        "SELECT kind, period, last_value FROM id_counters WHERE kind = ANY(%s)", (_COUNTERS,)
    ).fetchall()
    yield {
        "admin": person(db, "Ishaan Varma", "admin"),
        "finance": person(db, "Meher Saxena", "admin"),
        "reviewer": person(db, "Tanvi Joshi", "reviewer"),
        "sharer": person(db, "Arjun Pillai"),
        "merged": person(db, "Devika Rao"),
        "lead": person(db, "Kabir Sethi"),
        "member": person(db, "Nandini Iyer"),
        "nobody": person(db, "Rhea Kulkarni"),
    }
    # People, ideas and all that hangs off them (Ones, measurements); audit_log stays, as it must.
    wall_fixtures.leave_clean(db)
    db.execute("DELETE FROM id_counters WHERE kind = ANY(%s)", (_COUNTERS,))
    for c in counters:
        db.execute(
            "INSERT INTO id_counters (kind, period, last_value) VALUES (%s, %s, %s)",
            (c["kind"], c["period"], c["last_value"]),
        )
    db.execute("DELETE FROM flag_assignments")
    db.execute("UPDATE flags SET state = 'on', alternative_percent = 0")  # as the cut-over seeds them
    kindling.clear_cache()


def audit_actions(db: Conn, entity: str) -> list[str]:
    return [
        r["action"]
        for r in db.execute(
            "SELECT action FROM audit_log WHERE entity = %s AND id > %s ORDER BY id", (entity, _AUDIT_FROM[0])
        )
    ]


def shipped_idea(db: Conn, cast: dict[str, dict[str, str]], posted: list[dict[str, Any]]) -> dict[str, Any]:
    idea = an_idea(db, cast["sharer"])
    build.choose_team(db, cast["admin"]["id"], idea["idea_id"],
                      {"name": "Mandates crew", "lead_email": cast["lead"]["email"],
                       "member_emails": cast["member"]["email"]})  # fmt: skip
    build.mark_shipped(db, cast["admin"]["id"], idea["idea_id"], now=NOW - dt.timedelta(days=31))
    return idea


# --- J-ONE step 1: L-DECIDE.after ---------------------------------------------------------------------------------


def test_j_one_1_l_decide_after_team_chosen_moves_a_picked_idea_to_being_built(
    db: Conn, cast: Any, posted: Any
) -> None:
    idea = an_idea(db, cast["sharer"])
    out = build.choose_team(db, cast["admin"]["id"], idea["idea_id"],
                            {"name": "Mandates crew", "lead_email": cast["lead"]["email"],
                             "member_emails": f"{cast['member']['email']}, {cast['lead']['email']}"})  # fmt: skip
    assert out["status"] == "being_built" and out["members"] == 2
    row = db.execute("SELECT status FROM ideas WHERE id = %s", (idea["id"],)).fetchone()
    assert row["status"] == "being_built"
    team = db.execute(
        "SELECT name, lead_user_id, chosen_by FROM build_teams WHERE idea_uuid = %s", (idea["id"],)
    ).fetchone()
    assert team is not None
    assert dict(team) == {"name": "Mandates crew", "lead_user_id": uuid.UUID(cast["lead"]["id"]),
                                     "chosen_by": uuid.UUID(cast["admin"]["id"])}  # fmt: skip
    grants = db.execute(
        "SELECT user_id FROM role_grants WHERE role = 'build_team' AND scope_id = %s", (idea["idea_id"],)
    ).fetchall()
    assert sorted(str(g["user_id"]) for g in grants) == sorted([cast["lead"]["id"], cast["member"]["id"]])
    assert audit_actions(db, f"idea:{idea['idea_id']}") == ["idea.build_team_chosen"]
    # L-INBOX.kinds "Stage moved": the sharer and crew, from the system, the stage in refs; the team gets no item.
    assert [(c["kind"], c["to"], c["refs"], c.get("sender", "system")) for c in posted] == [
        ("stage_moved", [cast["sharer"]["id"]], {"to": "being_built"}, "system")
    ]

    with pytest.raises(Refused) as again:
        build.choose_team(db, cast["admin"]["id"], idea["idea_id"],
                          {"name": "Second crew", "lead_email": cast["lead"]["email"]})  # fmt: skip
    assert again.value.code == "not_picked"


def test_j_one_1_l_decide_after_only_admins_and_only_the_right_states(
    db: Conn, cast: Any, posted: Any
) -> None:
    idea = an_idea(db, cast["sharer"])
    with pytest.raises(Refused) as no:
        build.choose_team(db, cast["reviewer"]["id"], idea["idea_id"],
                          {"name": "Crew", "lead_email": cast["lead"]["email"]})  # fmt: skip
    assert no.value.status == 403
    with pytest.raises(Refused) as early:
        build.mark_shipped(db, cast["admin"]["id"], idea["idea_id"])
    assert early.value.code == "not_being_built"
    with pytest.raises(Refused) as unknown:
        build.choose_team(db, cast["admin"]["id"], idea["idea_id"],
                          {"name": "Crew", "lead_email": "nobody@kfintech.example"})  # fmt: skip
    assert (unknown.value.code, unknown.value.field) == ("no_such_person", "lead")
    with pytest.raises(Refused) as details:
        build.choose_team(db, cast["admin"]["id"], idea["idea_id"],
                          {"name": "Folio 1234567890 crew", "lead_email": cast["lead"]["email"]})  # fmt: skip
    assert details.value.code in ("personal_data", "name_length")


def test_j_one_1_l_decide_after_shipped_schedules_l_impact_1_checks(db: Conn, cast: Any, posted: Any) -> None:
    idea = shipped_idea(db, cast, posted)
    assert (
        db.execute("SELECT status FROM ideas WHERE id = %s", (idea["id"],)).fetchone()["status"] == "shipped"
    )
    marks = db.execute(
        "SELECT mark, due_at FROM delivery_measurements WHERE idea_uuid = %s ORDER BY mark", (idea["id"],)
    ).fetchall()
    shipped_at = NOW - dt.timedelta(days=31)
    assert [(m["mark"], m["due_at"]) for m in marks] == [
        ("day_30", shipped_at + dt.timedelta(days=30)), ("day_90", shipped_at + dt.timedelta(days=90)),
    ]  # fmt: skip
    assert audit_actions(db, f"idea:{idea['idea_id']}") == ["idea.build_team_chosen", "idea.shipped"]
    shipped = next(c for c in posted if c["refs"] == {"to": "shipped"})
    assert (shipped["kind"], shipped["to"]) == ("stage_moved", [cast["sharer"]["id"]])  # not the build team


# --- J-ONE step 2 and step 3: L-IMPACT, L-ONES.rules/1-3 -------------------------------------------------------------

HOURS_ONLY = {
    "time": {"amount": 120, "line": "Fewer bounced-debit cases"},
    "sentence": "120 hours a month saved.",
}


def test_j_one_2_3_l_impact_2_a_measurement_without_money_counts_and_lane_e_inducts(
    db: Conn, cast: Any, posted: Any
) -> None:
    idea = shipped_idea(db, cast, posted)
    out = impact.enter(db, cast["admin"]["id"], idea["idea_id"], "day_30", HOURS_ONLY, now=NOW)
    assert out["waits_for_finance"] is False
    assert [o["user_id"] for o in out["inducted"]] == [cast["sharer"]["id"]]
    one = db.execute("SELECT * FROM ones WHERE user_id = %s", (cast["sharer"]["id"],)).fetchone()
    assert (
        one["status"] == "active" and one["way_in"] == "accepted_idea" and one["idea_id"] == idea["idea_id"]
    )
    assert one["number"] == out["inducted"][0]["number"] and 1 <= one["number"] <= 999
    assert (
        one["tier"] == 2 and out["inducted"][0]["tier"] == 2
    )  # 120 hours a month: Tier 2, Glow (rules/tiers.md)
    assert one["swap_until"] - one["inducted_at"] == dt.timedelta(
        days=30
    )  # promises: ones.number_change_days
    assert one["measures"]["time"] == {"value": 120, "unit": "hours a month"}  # the office screen reads these
    results = db.execute(
        "SELECT results FROM delivery_measurements WHERE idea_uuid = %s AND mark = 'day_30'", (idea["id"],)
    ).fetchone()["results"]
    assert results["time"] == {"amount": 120, "unit": "hours a month", "line": "Fewer bounced-debit cases"}
    assert audit_actions(db, f"one:{one['id']}") == ["ones.inducted", "ones.tier_set"]
    # No Inbox item for the measurement or the new One at launch (BLD-A211, BLD-A186): only J-ONE step 1's two.
    assert [c["refs"] for c in posted] == [{"to": "being_built"}, {"to": "shipped"}]
    # No moment for a new One's first tier: the glow-up is for a rise they can see (S-ONE, L-ONES.rules/3).
    assert (
        db.execute("SELECT count(*) AS n FROM one_glow_ups WHERE one_id = %s", (one["id"],)).fetchone()["n"]
        == 0
    )
    # Idempotent: entering again inducts no one twice.
    again = impact.enter(db, cast["admin"]["id"], idea["idea_id"], "day_30", HOURS_ONLY, now=NOW)
    assert again["inducted"] == []


def test_j_one_2_l_impact_3_money_waits_for_a_second_person_and_then_inducts(
    db: Conn, cast: Any, posted: Any
) -> None:
    idea = shipped_idea(db, cast, posted)
    body = {"money": {"amount": 1_800_000}}
    out = impact.enter(db, cast["admin"]["id"], idea["idea_id"], "day_30", body, now=NOW)
    assert out["waits_for_finance"] is True and out["inducted"] == []  # unconfirmed money counts for nothing
    assert wall_impact.totals(db)["money_year"] == 0  # and shows nowhere on the Wall (L-IMPACT/3)
    with pytest.raises(Refused) as own:
        impact.finance_confirm(db, cast["admin"]["id"], idea["idea_id"], "day_30", now=NOW)
    assert own.value.code == "own_entry"
    confirmed = impact.finance_confirm(db, cast["finance"]["id"], idea["idea_id"], "day_30", now=NOW)
    assert [o["user_id"] for o in confirmed["inducted"]] == [cast["sharer"]["id"]]
    assert wall_impact.totals(db)["money_year"] == 1_800_000
    one = db.execute("SELECT tier, measures FROM ones WHERE user_id = %s", (cast["sharer"]["id"],)).fetchone()
    assert one["tier"] == 3  # ₹18 lakh a year: Tier 3, Flame
    assert one["measures"]["money"] == {
        "value": 1_800_000,
        "unit": "rupees a year",
        "finance_confirmed": True,
    }
    assert audit_actions(db, f"idea:{idea['idea_id']}")[-2:] == [
        "impact.measurement_entered", "impact.finance_confirmed",
    ]  # fmt: skip
    with pytest.raises(Refused) as twice:
        impact.finance_confirm(db, cast["finance"]["id"], idea["idea_id"], "day_30", now=NOW)
    assert twice.value.code == "already_confirmed"
    # A changed money figure needs Finance again; the same figure keeps the confirmation.
    impact.enter(db, cast["admin"]["id"], idea["idea_id"], "day_30", body, now=NOW)
    kept = db.execute("SELECT finance_confirmed_at FROM delivery_measurements WHERE idea_uuid = %s AND mark = "
                      "'day_30'", (idea["id"],)).fetchone()  # fmt: skip
    assert kept["finance_confirmed_at"] is not None
    impact.enter(
        db, cast["admin"]["id"], idea["idea_id"], "day_30", {"money": {"amount": 2_000_000}}, now=NOW
    )
    cleared = db.execute("SELECT finance_confirmed_at FROM delivery_measurements WHERE idea_uuid = %s AND mark = "
                         "'day_30'", (idea["id"],)).fetchone()  # fmt: skip
    assert cleared["finance_confirmed_at"] is None


def test_j_one_2_l_impact_2_validation_needs_a_measured_difference(db: Conn, cast: Any, posted: Any) -> None:
    idea = shipped_idea(db, cast, posted)
    for body, code in (
        ({}, "no_figures"),
        ({"time": {"amount": 0}}, "no_difference"),
        ({"time": {"amount": -3}}, "amount_not_valid"),
        ({"scale": {"amount": 41, "unit": "planets"}}, "scale_unit"),
        ({"time": {"amount": 5}, "sentence": "Customer PAN ABCPK1234D was slow"}, "personal_data"),
    ):
        with pytest.raises(Refused) as err:
            impact.enter(db, cast["admin"]["id"], idea["idea_id"], "day_30", body, now=NOW)
        assert err.value.code == code, body
    with pytest.raises(Refused) as order:
        impact.enter(db, cast["admin"]["id"], idea["idea_id"], "day_90", HOURS_ONLY, now=NOW)
    assert order.value.code == "day_30_first"
    picked = an_idea(db, cast["nobody"])
    with pytest.raises(Refused) as not_shipped:
        impact.enter(db, cast["admin"]["id"], picked["idea_id"], "day_30", HOURS_ONLY, now=NOW)
    assert not_shipped.value.code == "not_shipped"


def test_j_one_3_l_ones_rules_1_merged_sharers_are_credited_and_removed_ones_stay_out(
    db: Conn, cast: Any, posted: Any
) -> None:
    idea = shipped_idea(db, cast, posted)
    merged = an_idea(db, cast["merged"], status="merged")
    db.execute(
        "INSERT INTO merges (lead_idea_uuid, merged_idea_uuid, via, by_user_id) VALUES (%s, %s, 'review_desk', %s)",
        (idea["id"], merged["id"], cast["reviewer"]["id"]),
    )
    # The sharer was a One once and an admin removed them: the admin's call stands.
    ones.mark_founding(db, cast["admin"]["id"], {"email": cast["sharer"]["email"]})
    oid = db.execute("SELECT id FROM ones WHERE user_id = %s", (cast["sharer"]["id"],)).fetchone()["id"]
    ones.remove_one(db, cast["admin"]["id"], oid)
    out = impact.enter(db, cast["admin"]["id"], idea["idea_id"], "day_30", HOURS_ONLY, now=NOW)
    assert [o["user_id"] for o in out["inducted"]] == [cast["merged"]["id"]]
    assert db.execute("SELECT status FROM ones WHERE id = %s", (oid,)).fetchone()["status"] == "retired"


def test_j_one_6_l_ones_rules_3_at_90_days_a_tier_rises_with_a_glow_up(
    db: Conn, cast: Any, posted: Any
) -> None:
    idea = shipped_idea(db, cast, posted)
    impact.enter(db, cast["admin"]["id"], idea["idea_id"], "day_30", HOURS_ONLY, now=NOW)
    one = db.execute("SELECT id, tier FROM ones WHERE user_id = %s", (cast["sharer"]["id"],)).fetchone()
    assert one["tier"] == 2
    later = NOW + dt.timedelta(days=60)
    out = impact.enter(db, cast["admin"]["id"], idea["idea_id"], "day_90",
                       {"time": {"amount": 620}, "effort": {"amount": 3, "line": "Per new mandate"},
                        "scale": {"amount": 41, "unit": "branches", "line": "Using it every day"}}, now=later)  # fmt: skip
    assert out["tier_rises"] == [
        {"user_id": cast["sharer"]["id"], "one_id": one["id"], "tier_from": 2, "tier_to": 4}
    ]
    glow = db.execute("SELECT tier_from, tier_to, proposal_id, measurement_id, seen_at FROM one_glow_ups "
                      "WHERE one_id = %s", (one["id"],)).fetchone()  # fmt: skip
    assert (glow["tier_from"], glow["tier_to"], glow["proposal_id"], glow["seen_at"]) == (2, 4, None, None)
    assert glow["measurement_id"] is not None
    tiers = db.execute("SELECT o.tier, u.tier AS person_tier FROM ones o JOIN users u ON u.id = o.user_id "
                       "WHERE o.id = %s", (one["id"],)).fetchone()  # fmt: skip
    assert (tiers["tier"], tiers["person_tier"]) == (4, 4)
    assert audit_actions(db, f"one:{one['id']}") == ["ones.inducted", "ones.tier_set", "ones.tier_rose"]
    # J-ONE step 6's hand-off: lane E's dashboard plays the moment from this glow-up (S-ONE, L-ONES.rules/3).
    from wall import ones as lane_e

    moment = lane_e.dashboard(db, cast["sharer"]["id"], later)["tier_moment"]
    assert moment is not None and moment["line"] == "From Tier 2, Glow to Tier 4, Blaze"
    # A lower figure later never lowers a tier on its own.
    impact.enter(db, cast["admin"]["id"], idea["idea_id"], "day_90", {"time": {"amount": 10}}, now=later)
    assert db.execute("SELECT tier FROM ones WHERE id = %s", (one["id"],)).fetchone()["tier"] == 4


def test_j_one_3_dec_106_founding_and_removal_go_through_lane_e_and_are_audited(
    db: Conn, cast: Any, posted: Any
) -> None:
    with pytest.raises(Refused) as not_admin:
        ones.mark_founding(db, cast["reviewer"]["id"], {"email": cast["nobody"]["email"]})
    assert not_admin.value.status == 403
    with pytest.raises(Refused) as unknown:
        ones.mark_founding(db, cast["admin"]["id"], {"email": "nobody.here@kfintech.example"})
    assert (unknown.value.code, unknown.value.field) == ("no_such_person", "email")
    made = ones.mark_founding(db, cast["admin"]["id"], {"email": cast["nobody"]["email"]})
    row = db.execute("SELECT * FROM ones WHERE id = %s", (made["one_id"],)).fetchone()
    assert row["way_in"] == "founding" and row["number"] == made["number"]
    listed = ones.list_ones(db)
    assert [(o["number"], o["founding"]) for o in listed] == [(made["number"], True)]
    with pytest.raises(Refused) as twice:
        ones.mark_founding(db, cast["admin"]["id"], {"email": cast["nobody"]["email"]})
    assert twice.value.code == "already_founding"
    with pytest.raises(Refused) as not_a_one:
        ones.remove_one(db, cast["admin"]["id"], 999_999)
    assert not_a_one.value.code == "not_found" and not_a_one.value.message
    with pytest.raises(Refused) as reviewer:
        ones.remove_one(db, cast["reviewer"]["id"], made["one_id"])
    assert reviewer.value.status == 403
    ones.remove_one(db, cast["admin"]["id"], made["one_id"])
    row = db.execute("SELECT status, number FROM ones WHERE id = %s", (made["one_id"],)).fetchone()
    assert (row["status"], row["number"]) == ("retired", None)
    resting = db.execute("SELECT rests_until FROM one_number_history WHERE one_id = %s", (made["one_id"],))
    assert resting.fetchone()["rests_until"] is not None
    actors = db.execute("SELECT action, actor FROM audit_log WHERE entity = %s AND id > %s ORDER BY id",
                        (f"one:{made['one_id']}", _AUDIT_FROM[0])).fetchall()  # fmt: skip
    assert [(r["action"], r["actor"]) for r in actors] == [
        ("ones.founding_marked", f"user:{cast['admin']['id']}"), ("ones.removed", f"user:{cast['admin']['id']}"),
    ]  # fmt: skip
    assert ones.list_ones(db) == []
    # Marking a removed One as Founding brings them back to the same record (lane E's rule).
    back = ones.mark_founding(db, cast["admin"]["id"], {"email": cast["nobody"]["email"]})
    assert back["one_id"] == made["one_id"]
    assert posted == []  # no Inbox item for a new One at launch (BLD-A186)


def test_j_one_2_l_impact_1_the_due_list_is_the_clock(db: Conn, cast: Any, posted: Any) -> None:
    idea = shipped_idea(db, cast, posted)
    due = impact.due(db, NOW)
    assert [(d["idea_ref"], d["mark"], d["overdue"]) for d in due] == [
        (idea["idea_id"], "day_30", True), (idea["idea_id"], "day_90", False),
    ]  # fmt: skip
    assert due[0]["due_label"].startswith("Due ")
    # Lane E's live-fixes table reads the same due date while nothing is entered (L-WALL.impact/2).
    live = next(f for f in wall_impact.live_fixes(db, NOW) if f["id"] == idea["idea_id"])
    assert (live["measured"], live["due"]) == ("pending", due[0]["due_at"])
    impact.enter(db, cast["admin"]["id"], idea["idea_id"], "day_30", HOURS_ONLY, now=NOW)
    assert [d["mark"] for d in impact.due(db, NOW)] == ["day_90"]


# --- Take off the Wall (DEC-106) ----------------------------------------------------------------------------------


def test_dec_106_take_off_the_wall_hides_the_idea_from_wall_readers_and_restores(db: Conn, cast: Any) -> None:
    idea = an_idea(db, cast["sharer"], status="with_review_desk")
    assert db.execute("SELECT idea_off_wall(%s) AS off", (idea["id"],)).fetchone()["off"] is False
    with pytest.raises(Refused) as no:
        wall.take_off(db, cast["nobody"]["id"], idea["idea_id"], {"reason": "Holds a rude remark"})
    assert no.value.status == 403
    with pytest.raises(Refused) as own:
        wall.take_off(db, cast["sharer"]["id"], idea["idea_id"], {"reason": "Holds a rude remark"})
    assert own.value.status == 403
    with pytest.raises(Refused) as short:
        wall.take_off(db, cast["reviewer"]["id"], idea["idea_id"], {"reason": "rude"})
    assert short.value.code == "reason_length"
    wall.take_off(db, cast["reviewer"]["id"], idea["idea_id"], {"reason": "Holds a rude remark"})
    assert db.execute("SELECT idea_off_wall(%s) AS off", (idea["id"],)).fetchone()["off"] is True
    with pytest.raises(Refused) as twice:
        wall.take_off(db, cast["admin"]["id"], idea["idea_id"], {"reason": "Holds a rude remark"})
    assert twice.value.code == "already_off"
    listed = wall.removals(db)
    assert [(r["idea_ref"], r["by"], r["reason"]) for r in listed] == [
        (idea["idea_id"], "Tanvi Joshi", "Holds a rude remark")
    ]
    wall.restore(db, cast["admin"]["id"], idea["idea_id"], {"reason": "Checked with the sharer, fine"})
    assert db.execute("SELECT idea_off_wall(%s) AS off", (idea["id"],)).fetchone()["off"] is False
    assert audit_actions(db, f"idea:{idea['idea_id']}") == ["wall.taken_off", "wall.restored"]
    reasons = db.execute(
        "SELECT reason FROM audit_log WHERE entity = %s AND id > %s ORDER BY id",
        (f"idea:{idea['idea_id']}", _AUDIT_FROM[0]),
    )
    assert [r["reason"] for r in reasons] == ["Holds a rude remark", "Checked with the sharer, fine"]
    with pytest.raises(Refused) as not_off:
        wall.restore(db, cast["admin"]["id"], idea["idea_id"], {"reason": "Checked with the sharer, fine"})
    assert not_off.value.code == "not_off"


def test_dec_106_lane_e_wall_views_honour_take_off_the_wall(db: Conn, cast: Any, posted: Any) -> None:
    """The hand-off to lane E's Wall (S-WALL, L-WALL): its one filter, `on_wall_sql`, carries the removal, so Just
    in, Kindling and the live fixes all drop the idea at once and bring it back on restore."""
    from wall.common import on_wall_sql

    desk = an_idea(db, cast["merged"], status="with_review_desk", title="Branch queue tokens")
    shipped = shipped_idea(db, cast, posted)

    def visible() -> dict[str, bool]:
        on = {
            r["idea_id"]
            for r in db.execute(f"SELECT i.idea_id FROM ideas i WHERE {on_wall_sql('i')}").fetchall()  # noqa: S608
        }
        live = {f["id"] for f in wall_impact.live_fixes(db, NOW)}
        kind = {x["id"] for stage in kindling.kindling(db) for x in stage["items"]}
        just_in = {r["id"] for r in kindling.just_in(db, now=NOW)["items"]}
        return {
            "desk": desk["idea_id"] in on and desk["idea_id"] in just_in,
            "shipped": shipped["idea_id"] in on and shipped["idea_id"] in live and shipped["idea_id"] in kind,
        }

    assert visible() == {"desk": True, "shipped": True}
    wall.take_off(db, cast["reviewer"]["id"], desk["idea_id"], {"reason": "Names a customer's branch"})
    wall.take_off(db, cast["admin"]["id"], shipped["idea_id"], {"reason": "Waiting on a legal check"})
    assert visible() == {"desk": False, "shipped": False}
    wall.restore(db, cast["admin"]["id"], shipped["idea_id"], {"reason": "Legal cleared it this morning"})
    assert visible() == {"desk": False, "shipped": True}


def test_dec_106_take_off_the_wall_filters_the_old_wall_view(
    db: Conn, cast: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from views import wall as old_wall

    seen: list[tuple[Any, ...]] = []
    real = db.execute

    def spy(query: Any, params: Any = None, **kw: Any) -> Any:
        seen.append((str(query), params))
        return real(query, params, **kw)

    monkeypatch.setattr(db, "execute", spy)
    old_wall._ideas(db, ("scanned",), {}, 5)
    assert any("NOT idea_off_wall(id)" in q for q, _ in seen)


# --- The admin page's data ----------------------------------------------------------------------------------------


def test_l_audit_permissions_admin_view_shows_the_desk_only_take_off_the_wall(
    db: Conn, cast: Any, posted: Any
) -> None:
    shipped_idea(db, cast, posted)
    an_idea(db, cast["nobody"])
    desk = view.admin_view(db, cast["reviewer"]["id"], NOW)
    assert desk["can"] == {"programme": False, "wall": True} and set(desk) == {"can", "off_wall"}
    full = view.admin_view(db, cast["admin"]["id"], NOW)
    assert full["can"]["programme"] is True
    assert (
        len(full["picked"]) == 1
        and len(full["shipped"]) == 1
        and full["shipped"][0]["team"] == "Mandates crew"
    )
    assert [d["mark"] for d in full["due"]] == ["day_30", "day_90"]
    with pytest.raises(Refused):
        view.admin_view(db, cast["nobody"]["id"], NOW)


# --- L-AUDIT.flags ------------------------------------------------------------------------------------------------

# The same vector is checked in apps/web/tests/unit/flags.test.ts, so both sides place a person alike.
BUCKET_VECTOR = {
    ("s1", "00000000-0000-0000-0000-000000000001"): 62,
    ("s2", "00000000-0000-0000-0000-000000000002"): 62,
    ("s3", "11111111-2222-3333-4444-555555555555"): 86,
}


def test_l_audit_flags_bucket_is_deterministic_and_shared_with_the_web() -> None:
    for (key, user_id), expected in BUCKET_VECTOR.items():
        assert flags.bucket(key, user_id) == expected
    assert all(0 <= flags.bucket("s2", str(uuid.UUID(int=i))) < 100 for i in range(200))


def test_l_audit_flags_assignment_percentage_and_one_exposure(db: Conn, cast: Any) -> None:
    who = cast["sharer"]["id"]
    db.execute("UPDATE flags SET state = 'on', alternative_percent = 0")
    db.execute("DELETE FROM flag_assignments")
    assert flags.flag_variant(db, who, "s1", "S-04") == "default"
    db.execute("UPDATE flags SET alternative_percent = 100 WHERE key = 's1'")
    assert flags.flag_variant(db, who, "s1", "S-04") == "alternative"
    assert flags.flag_variant(db, who, "s1", "S-04") == "alternative"
    db.execute(
        "INSERT INTO flag_assignments (flag_key, user_id, variant, assigned_by) VALUES ('s1', %s, 'default', 'x')",
        (who,),
    )
    assert flags.flag_variant(db, who, "s1", "S-04") == "default"  # an admin's assignment wins
    db.execute("UPDATE flags SET state = 'off' WHERE key = 's1'")
    assert flags.flag_variant(db, who, "s1", "S-05") == "default"
    rows = db.execute(
        "SELECT variant, screen FROM flag_exposures WHERE user_id = %s ORDER BY id", (who,)
    ).fetchall()
    assert [(r["variant"], r["screen"]) for r in rows] == [
        ("default", "S-04"),
        ("alternative", "S-04"),
    ]  # fmt: skip  (once per person, screen and variant; an off flag logs nothing)
