"""L-WORTH and C-WORTH: figures in any Indian form, one normal form back, and the reviewer's revision beside the
sharer's (V-ACC.review/10 without the database; V-FIELDS.review/7–8)."""

from __future__ import annotations

import pytest

from desk import worth
from desk.worth import Range, Worth


@pytest.mark.parametrize(
    ("measure", "typed", "low", "high", "text"),
    [
        ("hours_month", "70 to 150 hours a month", 70, 150, "70 to 150 hours a month"),
        ("hours_month", "150-70", 70, 150, "70 to 150 hours a month"),
        ("hours_month", "about 40", 40, None, "about 40 hours a month"),
        ("hours_month", "1", 1, None, "1 hour a month"),
        ("hours_month", "forty hours", 40, None, "40 hours a month"),
        ("cost_month", "about ₹25,000 a month saved", 25000, None, "about ₹25,000 a month"),
        ("cost_month", "Rs. 1,20,000", 120000, None, "₹1,20,000 a month"),
        ("cost_month", "2.5 lakh", 250000, None, "₹2,50,000 a month"),
        ("revenue_month", "5L to 8L", 500000, 800000, "₹5,00,000 to ₹8,00,000 a month"),
        ("revenue_month", "1.2 crore", 12000000, None, "₹1,20,00,000 a month"),
    ],
)
def test_L_WORTH_1_and_6_figures_read_back_in_one_form(
    measure: worth.Measure, typed: str, low: float, high: float | None, text: str
) -> None:
    assert worth.parse(measure, typed) == Range(low, high, text)


@pytest.mark.parametrize("typed", ["lots", "1, 2 and 3 hours", "12/11/2026"])
def test_V_FIELDS_review_7_anything_else_asks_for_a_figure(typed: str) -> None:
    with pytest.raises(worth.WorthInvalid) as bad:
        worth.parse("hours_month", typed)
    assert (bad.value.error.field, bad.value.error.message) == ("hours_month", "Write a figure or a range.")


def test_V_FIELDS_review_7_every_measure_is_optional() -> None:
    assert worth.parse("cost_month", "  ") is None
    revised, errors = worth.read_revision({}, None, 280)
    assert errors == [] and revised == Worth()


def test_L_WORTH_6_rupees_in_summaries_use_lakh_and_crore() -> None:
    assert [worth.inr(n) for n in (500, 25000, 120000, 125000000)] == [
        "₹500", "₹25,000", "₹1,20,000", "₹12,50,00,000"
    ]  # fmt: skip
    assert [worth.inr_short(n) for n in (25000, 250000, 12000000)] == ["₹25,000", "₹2.5 lakh", "₹1.2 crore"]


def test_V_ACC_review_10_a_revised_tile_shows_the_new_figure_and_what_it_was() -> None:
    sharer = Worth(hours_month=worth.parse("hours_month", "70 to 150"), outside_tools="none")
    revised, errors = worth.read_revision(
        {"hours_month": "200 to 400", "outside_tools": "partly"},
        "The 40 calls are across three branches.",
        280,
    )
    assert errors == []
    by_measure = {t.measure: t for t in worth.tiles(sharer, revised)}
    assert by_measure["hours_month"].value == "200 to 400 hours a month"
    assert by_measure["hours_month"].was == "was 70 to 150 hours a month"
    assert by_measure["outside_tools"].value == "Partly less reliance"
    assert by_measure["cost_month"].value == "Not given" and by_measure["cost_month"].was is None
    # the sharer's figures are never overwritten; the revised ones count
    assert sharer.hours_month is not None and sharer.hours_month.low == 70
    assert worth.counted(sharer, revised) is revised


def test_C_WORTH_view_without_a_revision_shows_the_sharers_figures_and_empty_states() -> None:
    labels = [(t.label, t.value, t.was) for t in worth.tiles(Worth(), None)]
    assert labels == [
        ("Time saved", "Not given", None),
        ("Cost saved", "Not given", None),
        ("Revenue", "Not given", None),
        ("Outside tools", "No change", None),
    ]


def test_V_FIELDS_review_8_the_note_and_outside_tools_are_checked() -> None:
    _, errors = worth.read_revision({"outside_tools": "mostly", "cost_month": "lots"}, "x" * 281, 280)
    assert [e.code for e in errors] == ["worth_invalid", "outside_tools_invalid", "note_too_long"]


def test_worth_round_trips_as_json() -> None:
    w = Worth(cost_month=worth.parse("cost_month", "about 25k"), outside_tools="fully")
    assert Worth.from_json(w.as_json()) == w
    assert Worth.from_json(None) == Worth()
