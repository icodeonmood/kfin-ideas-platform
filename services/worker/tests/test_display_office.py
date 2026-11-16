"""The office screen's Ones (S-OFFICE, L-DISPLAY.office): induction order, a name unless the person hid it from the
Wall (DEC-104, `person_settings.show_name_on_wall`), money only once Finance confirmed it, and `ones.public` off hides
all of it. Synthetic people only."""

from __future__ import annotations

import secrets
from typing import Any

import pytest
from psycopg.types.json import Jsonb

from core import killswitch
from display.office import office

pytestmark = pytest.mark.stack


def _person(db: Any, name: str, first_name: str | None = None) -> str:
    tag = secrets.token_hex(3)
    row = db.execute(
        "INSERT INTO users (emp_id_hash, name, first_name, email, source, lob_id) "
        "VALUES (%s, %s, %s, %s, 'hr', 'LOB-mf') RETURNING id",
        (f"test:{tag}", name, first_name, f"o.{tag}@kfintech.example"),
    ).fetchone()
    return str(row["id"])


def _one(db: Any, user_id: str, *, way_in: str = "sponsored", tier: int = 1, measures: Any = None) -> int:
    row = db.execute(
        "INSERT INTO ones (induction_no, user_id, number, way_in, tier, measures, swap_until) VALUES ("
        "(SELECT coalesce(max(induction_no), 0) + 1 FROM ones), %s, "
        "(SELECT min(n) FROM generate_series(800, 999) n WHERE n NOT IN "
        "(SELECT number FROM ones WHERE number IS NOT NULL)), %s, %s, %s, now() + interval '30 days') "
        "RETURNING number",
        (user_id, way_in, tier, Jsonb(measures or {})),
    ).fetchone()
    return int(row["number"])


def test_names_follow_the_wall_setting_money_waits_for_finance_and_the_order_is_induction(db: Any) -> None:
    killswitch.clear_cache()
    shown = _person(db, "Asha Synthetic Test", first_name="Asha")
    hidden = _person(db, "Vikram Synthetic Test")
    plain = _person(db, "Neha Synthetic Test")
    db.execute("INSERT INTO person_settings (user_id, show_name_on_wall) VALUES (%s, false)", (hidden,))
    first = _one(db, shown, way_in="founding", tier=4, measures={
        "time": {"value": 620, "unit": "hours a month"},
        "money": {"value": 450000, "unit": "rupees a year", "finance_confirmed": False}})  # fmt: skip
    second = _one(db, hidden, tier=2)
    third = _one(
        db, plain, measures={"money": {"value": 90000, "unit": "rupees a year", "finance_confirmed": True}}
    )
    try:
        out = office(db)
        assert out["paused"] is False
        mine = [o for o in out["ones"] if o["number"] in (first, second, third)]
        assert [o["number"] for o in mine] == [first, second, third]
        a, v, n = mine
        assert (a["name"], a["first_name"], a["founding"], a["tier_name"]) == (
            "Asha Synthetic Test",
            "Asha",
            True,
            "Blaze",
        )
        assert a["measures"] == {"time": {"value": 620, "unit": "hours a month"}}
        assert (v["name"], v["first_name"], v["founding"]) == (None, None, False)
        assert (n["name"], n["first_name"]) == (
            "Neha Synthetic Test",
            "Neha",
        )  # no setting row: the name shows
        assert n["measures"]["money"]["value"] == 90000
        assert a["brief"] is None  # no approved brief, nothing to show
    finally:
        db.execute("DELETE FROM ones WHERE number = ANY(%s)", ([first, second, third],))


def test_ones_public_off_hides_the_office_screen(db: Any) -> None:
    killswitch.set_switch(db, "ones.public", "off", reason="testing the office screen rests", actor="test")
    killswitch.clear_cache()
    try:
        assert office(db) == {"paused": True, "ones": []}
    finally:
        killswitch.set_switch(
            db, "ones.public", "on", reason="testing done, Ones visible again", actor="test"
        )
        killswitch.clear_cache()
