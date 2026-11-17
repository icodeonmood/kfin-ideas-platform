"""Profile and settings from the database (S-H6, A-API.me, V-FIELDS.one/5, DEC-104, DEC-105, P-PRODUCT.privacy):
the person's own points, tier and line; every switch saves at once and returns its new state; a refusal names the
switch so it flips back; Teams stays off; the Wall switch reaches the Wall at once."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from core import killswitch
from core.db import Conn
from tests import wall_fixtures as f
from wall import kindling, profile
from wall.common import Refused

pytestmark = pytest.mark.stack


@pytest.fixture
def profile_db(db: Conn) -> Iterator[Conn]:
    killswitch.clear_cache()
    kindling.clear_cache()
    yield db
    f.leave_clean(db)
    kindling.clear_cache()
    killswitch.clear_cache()


def test_S_H6_layout_profile_carries_points_tier_line_and_defaults(profile_db: Conn) -> None:
    db = profile_db
    who = f.person(db, "Ritika Sood", area="Investor service", city="Hyderabad", tier=2, roles=("reviewer",))
    db.execute("INSERT INTO points_ledger (contributor_code, event, points, ref_id) VALUES (%s, 'shared', 340, 'x')",
               (who["code"],))  # fmt: skip
    out = profile.profile(db, who["id"])
    p = out["person"]
    assert p["points"] == 340 and p["tier"] == 2 and p["roles"] == ["employee", "reviewer"]
    assert p["settings"] == {"show_name_on_wall": True, "shortcut_p": True, "sidebar_folded": False,
                             "teams": False, "email": True, "reminders": True}  # fmt: skip
    assert out["line"] == "Investor service, Hyderabad. Tier 2, Glow." and out["tier_label"] == "Tier 2, Glow"
    assert out["avatar"] == {"initials": "RS", "tier": 2} and out["one_dashboard"] is None
    assert out["available"] == {"teams": False} and "one" not in p


def test_S_H6_refer_as_reads_unset_until_lane_Cs_route_lands(profile_db: Conn) -> None:
    """DEC-108, BLD-E010: Profile asks "How should we refer to you?" and saves through lane C's `/api/me/refer-as`.
    Until that route is on main the profile carries lane C's default, "unset" (neutral wording, BLD-E008)."""
    who = f.person(profile_db, "Ritika Sood")
    assert profile.profile(profile_db, who["id"])["refer_as"] == "unset"


def test_S_H6_rules_4_a_One_sees_their_One_tier_and_the_link_to_their_dashboard(profile_db: Conn) -> None:
    db = profile_db
    who = f.person(db, "Ritika Sood", tier=1)
    f.one(
        db, who, number=17, tier=4, way_in="founding", brief="Bank details are caught before the first debit."
    )
    out = profile.profile(db, who["id"])
    assert out["person"]["tier"] == 4 and out["one_dashboard"] == "/one"
    assert out["person"]["one"]["number"] == 17 and out["person"]["one"]["flag"] == "founding"
    assert out["person"]["one"]["brief"] == "Bank details are caught before the first debit."


def test_P_PRODUCT_privacy_points_never_leave_the_person(profile_db: Conn) -> None:
    """Points are in the person's own profile only: never on a Wall row, a One's card, a post or another's profile."""
    from wall import ones

    db = profile_db
    a, b = f.person(db, "Ritika Sood"), f.person(db, "Harsh Vora")
    db.execute("INSERT INTO points_ledger (contributor_code, event, points, ref_id) VALUES (%s, 'shared', 77, 'x')",
               (a["code"],))  # fmt: skip
    oid = f.one(db, a, number=3)
    idea = f.idea(db, a, title="Payout checks at every branch")
    f.post(db, oid, idea, "Payout checks are live at every branch.")
    assert profile.profile(db, b["id"])["person"]["points"] == 0  # b's own, never a's
    public = [
        kindling.just_in(db, now=f.NOW),
        kindling.kindling(db),
        ones.one_cards(db),
        ones.posts(db, b["id"], f.NOW),
    ]
    assert "points" not in repr(public)


def test_S_H6_rules_1_each_switch_saves_at_once_and_returns_every_switch(profile_db: Conn) -> None:
    db = profile_db
    who = f.person(db, "Ritika Sood")
    out = profile.save_settings(db, who["id"], {"email": False})
    assert out["settings"]["email"] is False and out["settings"]["reminders"] is True
    out = profile.save_settings(db, who["id"], {"sidebar_folded": True, "shortcut_p": False})
    assert out["settings"] == {"show_name_on_wall": True, "shortcut_p": False, "sidebar_folded": True,
                               "teams": False, "email": False, "reminders": True}  # fmt: skip
    assert profile.save_settings(db, who["id"], {})["settings"] == out["settings"]
    logged = db.execute("SELECT after FROM audit_log WHERE action = 'profile.settings_changed' AND actor = %s "
                        "ORDER BY id", (f"user:{who['id']}",)).fetchall()  # fmt: skip
    assert [r["after"] for r in logged] == [{"email": False}, {"shortcut_p": False, "sidebar_folded": True}]


def test_V_FIELDS_one_5_a_refused_save_names_the_switch_with_the_pack_message(profile_db: Conn) -> None:
    db = profile_db
    who = f.person(db, "Ritika Sood")
    for body in ({"email": "yes"}, {"points": True}, ["email"]):
        with pytest.raises(Refused) as exc:
            profile.save_settings(db, who["id"], body)
        assert exc.value.message == "Couldn't save that. Try again."
    with pytest.raises(Refused) as exc:
        profile.save_settings(db, who["id"], {"email": "yes"})
    assert exc.value.field == "email"


def test_DEC_105_Teams_stays_off_until_its_switch_is_on(profile_db: Conn) -> None:
    db = profile_db
    who = f.person(db, "Ritika Sood")
    with pytest.raises(Refused) as exc:
        profile.save_settings(db, who["id"], {"teams": True})
    assert (exc.value.code, exc.value.field) == ("teams_off", "teams")
    db.execute("INSERT INTO kill_switches (name, state) VALUES ('comms.teams', 'on') ON CONFLICT (name) DO UPDATE "
               "SET state = 'on'")  # fmt: skip
    killswitch.clear_cache()
    try:
        assert profile.profile(db, who["id"])["available"] == {"teams": True}
        assert profile.save_settings(db, who["id"], {"teams": False})["settings"]["teams"] is False
    finally:
        db.execute("DELETE FROM kill_switches WHERE name = 'comms.teams'")
        killswitch.clear_cache()


def test_DEC_104_the_Wall_switch_applies_to_every_idea_at_once(profile_db: Conn) -> None:
    db = profile_db
    who = f.person(db, "Ritika Sood")
    f.idea(db, who, title="An older idea", shared_at=f.ago(days=3))
    f.idea(db, who, title="A newer idea", shared_at=f.ago(hours=3))
    assert all(r["sharer"] for r in kindling.just_in(db, now=f.NOW)["items"])
    profile.save_settings(db, who["id"], {"show_name_on_wall": False})
    assert all(r["sharer"] is None for r in kindling.just_in(db, now=f.NOW)["items"])
    consent = db.execute(
        "SELECT public_name_consent FROM comms_prefs WHERE user_id = %s", (who["id"],)
    ).fetchone()
    assert consent["public_name_consent"] is False  # old pages agree until they retire


def test_A_API_me_a_profile_is_only_ever_its_own(profile_db: Conn) -> None:
    db = profile_db
    with pytest.raises(Refused) as exc:
        profile.profile(db, "00000000-0000-0000-0000-000000000000")
    assert exc.value.status == 404
    gone = f.person(db, "Former Colleague")
    db.execute("UPDATE users SET active = false WHERE id = %s", (gone["id"],))
    with pytest.raises(Refused):
        profile.save_settings(db, gone["id"], {"email": False})
