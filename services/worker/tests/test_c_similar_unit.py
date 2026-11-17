"""L-SIMILAR and A-API.idea-preview, the parts that need no database (BLD-C090 onwards): masking, the one-sentence
quote, names and the worth line."""

from __future__ import annotations

from decimal import Decimal

from similar import preview as pv


def test_bld_c090_mask_text_hides_customer_details_and_tags() -> None:
    text = "An investor with folio 7700012389 and PAN AAAPZ9999Z called from 9876543210 about [[KFIN_EMPLOYEE_1]]."
    out = pv.mask_text(text)
    for raw in ("7700012389", "AAAPZ9999Z", "9876543210", "[[KFIN_EMPLOYEE_1]]"):
        assert raw not in out
    assert "folio ••••89" in out  # the label is not repeated after the word that names it
    assert "PAN ••••9Z" in out
    assert "Phone ••••10" in out
    assert "about someone." in out
    assert pv.mask_text(None) == ""
    assert pv.mask_text("Nothing to hide here.") == "Nothing to hide here."


def test_bld_c090_first_sentence_is_one_sentence_and_short() -> None:
    assert pv.first_sentence("Rejection SMS codes confuse investors. They call the branch.") == (
        "Rejection SMS codes confuse investors."
    )
    assert pv.first_sentence("  no full stop at all  ") == "no full stop at all"
    long = "word " * 100
    out = pv.first_sentence(long)
    assert len(out) <= pv.SENTENCE_MAX + 1 and out.endswith("…")
    assert pv.first_sentence("") == ""


def test_bld_c090_people_initials_and_hidden_names() -> None:
    assert pv.initials("Tanvi Deshmukh") == "TD"
    assert pv.initials("Harish Venkatesan Iyer") == "HI"
    assert pv.initials("Deepa") == "D"
    assert pv.initials("") == ""
    hidden = pv.hidden_person("CTR-0a1b2c")
    assert hidden["name"] == pv.HIDDEN_NAME and hidden["initials"] == ""
    assert hidden == pv.hidden_person("CTR-0a1b2c")  # stable
    assert hidden["id"] != pv.hidden_person("CTR-0a1b2d")["id"]
    assert "CTR" not in hidden["id"]


def test_bld_c090_worth_line_in_rupees_and_hours() -> None:
    assert pv.rupees(25000) == "₹25,000"
    assert pv.rupees(Decimal("2500000.00")) == "₹25,00,000"
    assert pv.rupees(999) == "₹999"
    assert pv.rupees(123456789) == "₹12,34,56,789"
    assert pv.worth_line(None) == "Not given"
    assert pv.worth_line({"hours_low": Decimal("70"), "hours_high": Decimal("150")}) == (
        "Saves 70 to 150 hours a month"
    )
    assert pv.worth_line({"hours_low": 120, "hours_high": 200, "cost_low": Decimal("40000.00")}) == (
        "Saves 120 to 200 hours a month and about ₹40,000 a month"
    )
    assert pv.worth_line({"revenue_low": 100000, "revenue_high": 150000}) == (
        "Earns ₹1,00,000 to ₹1,50,000 a month"
    )
    assert pv.worth_line({"hours_low": None, "cost_low": None}) == "Not given"
