"""L-SIMILAR and A-API.idea-preview, the parts that need no database (BLD-C090 onwards): masking, the one-sentence
quote, names and the worth line."""

from __future__ import annotations

from decimal import Decimal

from similar import matching as m
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


# ---- L-SIMILAR matching helpers (BLD-C092) -------------------------------------------------------------------


def _hit(title: str, summary: str, cosine: float = 0.0, keyword: bool = True) -> m.Hit:
    return m.Hit(
        "u1", "IDEA-2026-000001", title, summary, "Investor service", "with_review_desk", 0.1, cosine, keyword
    )


def test_bld_c092_words_and_material_change() -> None:
    """L-SIMILAR.rules/4: what counts as a material change, compared as hashes of words."""
    assert m.words("The SMS for a failed SIP debit only says it failed.") == [
        "sms",
        "failed",
        "sip",
        "debit",
        "says",
    ]
    a = m.word_hashes("The SMS for a failed SIP debit only says it failed")
    assert a == m.word_hashes("failed SIP debit SMS says")  # order and repeats do not matter
    assert all(len(h) == 12 and "sms" not in h for h in a)  # hashes, never the words
    b = m.word_hashes("The SMS for a failed SIP debit only says it failed, again")
    assert not m.material_change(a, b, 0.2)
    c = m.word_hashes("Rejection letters show codes like R07 that investors cannot read")
    assert m.material_change(a, c, 0.2)
    assert not m.material_change([], [], 0.2)


def test_bld_c092_code_labels_need_meaning_or_a_good_share_of_words() -> None:
    """L-SIMILAR.rules/2: by meaning first; shared words alone only when they are a good part of the other idea."""
    mine = "SIP failure SMS gives no reason. When a SIP debit fails the SMS says only that it failed."
    r1 = _hit(
        "Investors get no reason when a SIP debit fails",
        "A failed SIP debit reaches the investor without a reason.",
    )
    shared = m.shared_words(mine, r1)
    assert shared[:4] == ["reason", "SIP", "debit", "fails"]  # the other idea's title first, its own capitals
    assert m.code_strength(r1, shared, 0.45) == "close"  # most of R1's words: the same failed SIP debit
    r2 = _hit(
        "One clear message after a failed SIP debit",
        "Investors call once when the SIP fails and again before the next one.",
    )
    assert m.code_strength(r2, m.shared_words(mine, r2), 0.45) == "related"
    assert m.code_strength(_hit(r2.title, r2.summary, cosine=0.85), [], 0.45) == "close"
    assert m.code_strength(_hit(r1.title, r1.summary, cosine=0.5, keyword=False), [], 0.45) == "related"
    t7 = _hit(
        "Plain words for transaction rejection codes",
        "Rejection letters show codes that investors cannot read.",
    )
    assert (
        m.code_strength(t7, m.shared_words(mine + " investors", t7), 0.45) is None
    )  # one common word: no match
    same = _hit("SIP failure SMS gives no reason", "When a SIP debit fails the SMS says only that it failed.")
    assert m.code_strength(same, m.shared_words(mine, same), 0.45) == "close"


def test_bld_c092_code_reasons_name_what_is_shared() -> None:
    """L-SIMILAR.rules/2: the one-line reason names what is shared, in plain words."""
    assert m.code_reason("close", ["SMS", "calls"], "", False) == "Close match: same SMS, same calls"
    assert m.code_reason("close", [], "", False) == "Close match: the same problem"
    assert m.code_reason("related", ["calls"], "", False) == "Related: also about calls"
    assert m.code_reason("related", ["SIP", "debit", "x"], "", False) == "Related: also about SIP and debit"
    assert m.code_reason("related", [], "Operations", True) == "Related: also in Operations"
    assert m.code_reason("related", [], "Operations", False) == "Related: a similar problem"


def test_bld_c097_the_judge_reads_the_masked_title_and_summary_only() -> None:
    """L-SIMILAR.rules/2, DEC-104: what the judge reads of a draft is its masked title and short summary, trimmed
    as the candidates are; the person's messages are not an input to it."""
    idea = {
        "title": "SIP SMS for PAN AAAPZ9999Z",
        "summary": "Investors   call the branch\n to ask why.",
        "neutral_summary": "Old summary.",
    }
    title, summary = m.judge_text(idea)
    assert "AAAPZ9999Z" not in title and title.startswith("SIP SMS for PAN")
    assert summary == "Investors call the branch to ask why."
    assert m.judge_text({"title": None, "summary": None, "neutral_summary": "Old summary."}) == (
        "",
        "Old summary.",
    )
    long_title, long_summary = m.judge_text({"title": "word " * 100, "summary": "word " * 200})
    assert len(long_title) <= m.TITLE_CHARS and len(long_summary) <= m.SUMMARY_CHARS
    assert m.judge_text({"title": "", "summary": ""}) == ("", "")
