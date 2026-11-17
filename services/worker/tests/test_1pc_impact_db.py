"""What shipped ideas changed, read side (L-IMPACT/3, /4, /6, L-WALL.impact, S-WALL.impact, S-ONE "Impact so far"):
totals from entered figures, money only once Finance confirmed it, the latest figure per measure, live fixes with
their measured state, and both stored forms of a measurement."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from typing import Any

import pytest

from core import killswitch
from core.db import Conn
from tests import wall_fixtures as f
from wall import impact
from wall.common import indian, rupees

pytestmark = pytest.mark.stack


@pytest.fixture
def impact_db(db: Conn) -> Iterator[Conn]:
    killswitch.clear_cache()
    yield db


def test_L_IMPACT_reads_both_stored_forms_of_a_figure() -> None:
    seed_form = impact.figure("time", {"value": "620", "line": "hours a month"})
    assert seed_form is not None and seed_form.amount == 620 and seed_form.display == "620 hours a month"
    money = impact.figure("money", {"value": "₹18 lakh", "line": "a year"})
    assert money is not None and money.amount == 1_800_000 and money.display == "₹18 lakh a year"
    canonical = impact.figure("money", {"amount": 150000, "unit": "rupees a month"})
    assert canonical is not None and impact.rupees_a_year(canonical) == 1_800_000
    assert canonical.display == "₹1.5 lakh a month"
    scale = impact.figure("scale", {"amount": 58600, "unit": "distributors", "line": "Using it every day"})
    assert scale is not None and scale.display == "58,600 distributors" and scale.line == "Using it every day"
    old_ones = impact.figures_from_measures({"time": {"value": 40, "unit": "days a year"},
                                             "money": {"value": 900000, "unit": "rupees a year"}})  # fmt: skip
    assert "money" not in old_ones  # not confirmed by Finance
    assert round(impact.hours_a_month(old_ones["time"])) == 27
    assert impact.figure("time", "620") is None and impact.figure("time", {"value": ""}) is None


def test_S_WALL_impact_numbers_stay_on_one_line_in_Indian_form() -> None:
    assert indian(58600) == "58,600" and indian(124000) == "1,24,000" and indian(930) == "930"
    assert rupees(2_400_000) == ("₹24", "lakh") and rupees(12_000_000) == ("₹1.2", "crore")
    assert rupees(45000) == ("₹45,000", "")


def _shipped(db: Conn, title: str, team: str | None = None) -> dict[str, Any]:
    sharer = f.person(db, f"Sharer of {title}")
    row = f.idea(db, sharer, title=title, status="shipped")
    if team:
        db.execute("INSERT INTO build_teams (idea_uuid, name) VALUES (%s, %s)", (row["id"], team))
    return row


def test_L_IMPACT_6_wall_totals_sum_the_latest_confirmed_figures(impact_db: Conn) -> None:
    db = impact_db
    a = _shipped(db, "Bank details checked before the first debit", "Investor services")
    b = _shipped(db, "Distributors see why a registration is stuck", "Distributor platforms")
    c = _shipped(db, "A reminder before a mandate expires", "Distributor platforms")
    f.measurement(db, a, "day_30", {"time": {"amount": 500, "unit": "hours a month"},
                                    "money": {"amount": 1_800_000, "unit": "rupees a year"},
                                    "scale": {"amount": 41, "unit": "branches"}}, finance=True)  # fmt: skip
    f.measurement(db, a, "day_90", {"time": {"amount": 620, "unit": "hours a month"},
                                    "sentence": "620 hours a month saved; bounced first debits down by a third"})  # fmt: skip
    f.measurement(db, b, "day_30", {"time": {"value": "310", "line": "hours a month"},
                                    "money": {"value": "₹6 lakh", "line": "a year"},
                                    "scale": {"value": "58,600", "line": "distributors reached"}})  # fmt: skip
    f.measurement(db, c, "day_30", None, due_at=dt.datetime(2026, 11, 18, 12, 0, tzinfo=f.IST))
    t = impact.totals(db)
    # 620 (a's 90-day time wins over its 30-day 500) + 310; money: only a's, which Finance confirmed.
    assert t == {"hours_month": 930, "money_year": 1_800_000, "fixes_measured": 2,
                 "reached": {"count": 58600, "noun": "distributors"}}  # fmt: skip
    tiles = impact.tiles(t)
    assert [(x["value"], x["suffix"], x["label"]) for x in tiles] == [
        ("930", "", "Hours saved a month"),
        ("₹18", "lakh", "Saved a year, Finance confirmed"),
        ("2", "", "Fixes shipped and measured"),
        ("58,600", "", "Distributors reached by a shipped fix"),
    ]


def test_L_WALL_impact_2_live_fixes_with_their_measured_state(impact_db: Conn) -> None:
    db = impact_db
    a = _shipped(db, "Bank details checked before the first debit", "Investor services")
    b = _shipped(db, "Nominee changes finish in one branch visit", "Investor service operations")
    c = _shipped(db, "A reminder before a mandate expires", "Distributor platforms")
    f.measurement(db, a, "day_30", {"time": {"amount": 500, "unit": "hours a month"}})
    f.measurement(db, a, "day_90", {"time": {"amount": 620, "unit": "hours a month"},
                                    "sentence": "620 hours a month saved; bounced first debits down by a third"})  # fmt: skip
    f.measurement(db, b, "day_30", {"effort": {"amount": 2, "unit": "fewer visits"},
                                    "sentence": "Repeat visits for nominee changes down by two thirds"})  # fmt: skip
    f.measurement(db, c, "day_30", None, due_at=dt.datetime(2026, 11, 18, 12, 0, tzinfo=f.IST))
    live = impact.live_fixes(db, f.NOW)
    assert [(x["what"], x["measured"], x["measured_label"], x["team"]) for x in live] == [
        ("Bank details checked before the first debit", "90d", "90 days", "Investor services"),
        ("Nominee changes finish in one branch visit", "30d", "30 days", "Investor service operations"),
        ("A reminder before a mandate expires", "pending", "Due 18 Nov", "Distributor platforms"),
    ]
    assert live[0]["change"] == "620 hours a month saved; bounced first debits down by a third"
    assert live[2]["change"] == "Being measured" and live[2]["due"].startswith("2026-11-18")


def test_L_IMPACT_3_unconfirmed_money_never_shows(impact_db: Conn) -> None:
    db = impact_db
    a = _shipped(db, "Payout checks at every branch")
    f.measurement(db, a, "day_30", {"money": {"amount": 600000, "unit": "rupees a year"},
                                    "time": {"amount": 70, "unit": "hours a month", "line": "Fewer returns"}})  # fmt: skip
    shown = impact.idea_impact(db, a["id"])
    assert "money" not in shown and shown["time"] == {"value": "70 hours a month", "line": "Fewer returns"}
    db.execute(
        "UPDATE delivery_measurements SET finance_confirmed_at = now() WHERE idea_uuid = %s", (a["id"],)
    )
    shown = impact.idea_impact(db, a["id"])
    assert shown["money"] == {
        "value": "₹6 lakh a year",
        "line": "Finance confirmed",
        "finance_confirmed": True,
    }
