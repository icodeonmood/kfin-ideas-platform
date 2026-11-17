"""J-ONE's hand-offs through lane E's worker side, on the 1% Club seed (BLD-E006): what the Wall, a One's dashboard
and Home's Ones fan hand the screens for J-ONE/2 to /6 (apps/web/journeys/J-ONE.spec.ts drives the pages). Each
step checks what it receives from the step before (a shipped, measured idea; an inducted One) and the exact copy
it hands on (reference/copy/Wall.md, OneDashboard.md, Home.md)."""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Iterator
from typing import Any

import pytest

from bootstrap import club_seed
from core import killswitch
from core.db import Conn
from wall import impact, kindling, ones

pytestmark = pytest.mark.stack

NOW = dt.datetime.now(dt.UTC)


@pytest.fixture
def seeded(db: Conn) -> Iterator[tuple[Conn, dict[str, Any]]]:
    killswitch.clear_cache()
    kindling.clear_cache()
    made = club_seed.load(db, now=NOW)
    yield db, made
    kindling.clear_cache()


def _user(db: Conn, name: str) -> str:
    row = db.execute("SELECT id FROM users WHERE name = %s", (name,)).fetchone()
    assert row is not None
    return str(row["id"])


def test_J_ONE_1_a_shipped_idea_reaches_Kindling_as_shipped(seeded: tuple[Conn, dict[str, Any]]) -> None:
    db, made = seeded
    shipped = next(s for s in kindling.kindling(db) if s["stage"] == "shipped")
    assert made["V1"].ref in {x["id"] for x in shipped["items"]} or shipped["count"] > 3
    assert shipped["count"] >= 4


def test_J_ONE_2_measured_figures_reach_the_Wall_money_only_once_Finance_confirms(
    seeded: tuple[Conn, dict[str, Any]],
) -> None:
    """L-IMPACT/3, /4, /6: V1 620 (30 days, money confirmed), S1 140 (90 days replaces 90), D1 110, I1 70 (its
    ₹6 lakh not confirmed): 940 hours, ₹18 lakh, 4 fixes measured, 58,600 distributors."""
    db, made = seeded
    out = impact.wall_impact(db, NOW)
    tiles = {t["key"]: (t["value"], t["suffix"], t["label"]) for t in out["tiles"]}
    assert tiles == {
        "hours_month": ("940", "", "Hours saved a month"),
        "money_year": ("₹18", "lakh", "Saved a year, Finance confirmed"),
        "fixes_measured": ("4", "", "Fixes shipped and measured"),
        "reached": ("58,600", "", "Distributors reached by a shipped fix"),
    }
    live = {r["id"]: r for r in out["live"]}
    v1, i1 = live[made["V1"].ref], live[made["I1"].ref]
    assert v1["change"] == "620 hours a month saved; bounced payouts down by a third"
    assert v1["measured_label"] == "30 days" and v1["team"] == "Payout checks team"
    assert live[made["S1"].ref]["measured_label"] == "90 days"
    assert i1["change"] == "Returned transfer requests down by a quarter"
    assert "6 lakh" not in repr(out)


def test_J_ONE_3_the_new_One_is_a_card_on_the_Wall_with_number_tier_and_brief(
    seeded: tuple[Conn, dict[str, Any]],
) -> None:
    db, _ = seeded
    cards = ones.one_cards(db)
    assert len(cards) == 7
    varun = next(c for c in cards if c["person"] and c["person"]["name"] == "Varun Chopra")
    assert (varun["number"], varun["tier_label"], varun["flag_label"]) == (11, "Tier 3, Flame", "One")
    assert varun["brief"] == "Stopped wrong bank details before a payout goes out."
    assert "points" not in repr(cards)


def test_J_ONE_4_the_new_Ones_dashboard_keeps_or_swaps_the_number_inside_30_days(
    seeded: tuple[Conn, dict[str, Any]],
) -> None:
    db, _ = seeded
    sid = _user(db, "Siddharth Menezes")
    dash = ones.dashboard(db, sid, NOW)
    assert dash["headline"] == "You're No. 21" and dash["one"]["tier_label"] == "Tier 1, Spark"
    window = dash["number_window"]
    assert window["open"] is True
    assert re.fullmatch(
        r"Keep No\. 21, or choose any free number from 1 to 999 until \d{1,2} [A-Z][a-z]{2} \d{4}\. "
        r"First come, first served\. After that, it's yours\.",
        window["keep_label"],
    )
    # The window is 30 days from becoming a One (Siddharth: 10 days ago, so 20 left).
    until = dt.datetime.fromisoformat(window["until"])
    assert dt.timedelta(days=19, hours=23) < until - NOW <= dt.timedelta(days=20)
    assert dash["brief"] == {"text": "Online forms that fill the city from the pin code.", "pending": False}
    # The brief on the dashboard is the one on the Wall.
    wall = next(c for c in ones.one_cards(db) if c["number"] == 21)
    assert wall["brief"] == dash["brief"]["text"]
    # Varun wears 11: taken, with the free numbers nearest it.
    with pytest.raises(Exception) as taken:
        ones.set_number(db, sid, 11, NOW)
    assert getattr(taken.value, "code", None) == "taken"
    assert ones.set_number(db, sid, 77, NOW)["number_window"]["number"] == 77
    assert ones.dashboard(db, sid, NOW)["headline"] == "You're No. 77"
    assert next(c for c in ones.one_cards(db) if c["person"] and c["person"]["id"] == sid)["number"] == 77


def test_J_ONE_5_a_Ones_post_is_a_card_in_Homes_The_Ones_for_everyone(
    seeded: tuple[Conn, dict[str, Any]],
) -> None:
    db, made = seeded
    naveen = _user(db, "Naveen Reddy")
    posts = ones.posts(db, naveen, NOW)
    varun = next(p for p in posts if p["one"]["person"] and p["one"]["person"]["name"] == "Varun Chopra")
    # "One No. 11, Tier 3, Flame" on the card (C-ONES-FAN.card)
    assert (varun["one"]["number"], varun["one"]["tier_label"]) == (11, "Tier 3, Flame")
    assert varun["text"] == "Payout checks are live at every branch. Bounced payouts are down by a third."
    assert varun["adopted_by"] == 3 and varun["figure"] == {"value": "620", "line": "hours a month saved"}
    assert varun["likes"] == 5 and varun["liked"] is True  # Naveen is one of the five
    assert varun["thread_to"] == f"/ideas/{made['V1'].ref}"


def test_L_IMPACT_3_a_posts_money_figure_shows_only_once_Finance_confirmed_it(
    seeded: tuple[Conn, dict[str, Any]],
) -> None:
    """Indira's post headlines ₹6 lakh for I1, which Finance has not confirmed: Home is public, so the figure is left
    off the card (the words stay). Varun's confirmed money would show; his post headlines hours."""
    db, _ = seeded
    posts = ones.posts(db, _user(db, "Naveen Reddy"), NOW)
    indira = next(p for p in posts if p["one"]["person"] and p["one"]["person"]["name"] == "Indira Natarajan")
    assert indira["figure"] == {"value": "", "line": ""}
    assert indira["text"] == "One checklist for share transfers is in every service centre now."
    assert "6 lakh" not in repr(posts)


def test_J_ONE_6_at_90_days_the_latest_figures_replace_the_30_day_ones(
    seeded: tuple[Conn, dict[str, Any]],
) -> None:
    db, _ = seeded
    dash = ones.dashboard(db, _user(db, "Siddharth Menezes"), NOW)
    assert dash["impact"]["time"] == {"value": "140 hours a month", "line": ""}
    # The figure is "2 fewer steps"; what it is per goes in the line under it (S-ONE: "3 fewer steps" / "Per new
    # mandate").
    assert dash["impact"]["effort"] == {"value": "2 fewer steps", "line": "Per online form"}
    assert "90 hours" not in repr(dash["impact"])
