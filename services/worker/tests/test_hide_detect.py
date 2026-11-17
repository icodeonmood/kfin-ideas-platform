"""L-HIDE.detect and L-HIDE.rules/2, /3, /5 without the stack: what is hidden, how it is masked, the receipt, and
how a reviewer's selection in the masked copy maps back to the person's own words (lane C, BLD-C060, BLD-C061).
All values are synthetic and made up for the test (non-negotiable 11)."""

from __future__ import annotations

from typing import Any

import pytest

from hide import detect
from hide.core import HideError, layout, summary
from hide.desk import Sealed, _owner_range
from pii.detect import Directory

FOLIO, PAN, PHONE = "1234567/89", "ABCPK1234F", "9876543210"


def kinds(text: str, **kw: Any) -> list[tuple[str, str]]:
    return [(f.kind, f.value) for f in detect.find(None, text, gatekeeper=False, **kw)]


def test_l_hide_rules_3_mask_is_kind_four_dots_and_last_two() -> None:
    assert detect.mask("folio", FOLIO) == "Folio ••••89"
    assert detect.mask("pan", PAN) == "PAN ••••4F"
    assert detect.mask("phone", "+91 98765 43210") == "Phone ••••10"
    assert detect.mask("aadhaar", "2345 6789 0123") == "Aadhaar ••••23"


def test_l_hide_detect_folio_pan_phone_email_and_account() -> None:
    text = (
        f"The investor's folio {FOLIO} shows the wrong bank. PAN {PAN}, mobile {PHONE}, "
        "personal mail synthetic.person@example.org, bank account 001234567890123."
    )
    found = dict((k, v) for k, v in kinds(text, names=False))
    assert found["folio"] == FOLIO
    assert found["pan"] == PAN
    assert found["phone"] == PHONE
    assert found["email"] == "synthetic.person@example.org"
    assert found["account"] == "001234567890123"


def test_l_hide_detect_a_kfintech_work_address_stays_visible(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.config import get_settings

    monkeypatch.setattr(get_settings(), "kfin_email_domains", "kfintech.example")
    assert kinds("Write to ops.desk@kfintech.example for help", names=False) == []


def test_l_hide_detect_an_ifsc_hides_only_with_an_account_number() -> None:
    assert kinds("Branch code SBIN0001234 is wrong on the mandate form", names=False) == []
    found = kinds("Account no 001234567890123 at SBIN0001234 bounced", names=False)
    assert ("account", "SBIN0001234") in found and ("account", "001234567890123") in found


def test_l_hide_detect_a_upi_id_is_an_account_not_an_email() -> None:
    assert kinds("Refund went to synthetic.k@okbank instead", names=False) == [
        ("account", "synthetic.k@okbank")
    ]


def test_l_hide_detect_business_codes_are_not_hidden() -> None:
    assert kinds("Distributor ARN-123456 with EUIN E123456 asked about scheme codes", names=False) == []


def test_l_hide_detect_a_name_hides_only_in_the_same_sentence_as_another_detail() -> None:
    text = f"Ramesh Gupta called again. Customer Suresh Iyer sent folio {FOLIO} by post."
    found = kinds(text)
    assert ("name", "Suresh Iyer") in found
    assert all(v != "Ramesh Gupta" for _, v in found)


def test_l_hide_detect_a_colleagues_name_is_never_hidden() -> None:
    d = Directory(employee_names={"suresh iyer": "u-1"}).compile()
    found = kinds(f"Suresh Iyer from ops checked folio {FOLIO}.", directory=d)
    assert found == [("folio", FOLIO)]


def test_l_hide_detect_values_already_hidden_are_hidden_again_everywhere() -> None:
    found = detect.find(
        None, "Ask Ward 7 and Ward 7 again", known={"Ward 7": ("name", "reviewer")}, gatekeeper=False
    )
    assert [(f.start, f.end, f.found_by) for f in found] == [(4, 10, "reviewer"), (15, 21, "reviewer")]


def test_l_hide_rules_5_receipt_and_kinds_line() -> None:
    assert (
        detect.receipt(["Folio ••••89", "PAN ••••4F", "Phone ••••10"])
        == "Hid 3 personal details from everyone but you: Folio ••••89, PAN ••••4F, Phone ••••10."
    )
    assert detect.receipt(["Folio ••••89"]) == "Hid 1 personal detail from everyone but you: Folio ••••89."
    assert detect.receipt([]) is None
    assert detect.kinds_line(["folio", "pan", "phone", "pan"]) == "Folio number, PAN and phone number"


def test_l_hide_rules_7_a_selection_is_classified_by_pattern_else_name() -> None:
    assert detect.classify(PAN) == "pan"
    text = f"Investor folio {FOLIO} was merged"
    assert detect.classify(FOLIO, text, text.index(FOLIO)) == "folio"
    assert detect.classify("Meena Pillai of Ward 7") == "name"


def _row(i: int, s: int, e: int, kind: str, value: str, state: str = "hidden") -> dict[str, Any]:
    return {
        "id": f"d{i}",
        "span_start": s,
        "span_end": e,
        "kind": kind,
        "masked": detect.mask(kind, value),
        "state": state,
    }


def test_l_hide_rules_2_spans_are_in_the_owners_own_text_and_the_mask_is_the_other_copy() -> None:
    own = f"Folio {FOLIO} and PAN {PAN} need a fix"
    a, b = own.index(FOLIO), own.index(PAN)
    rows = [_row(1, a, a + len(FOLIO), "folio", FOLIO), _row(2, b, b + len(PAN), "pan", PAN, "shown")]
    masked, _ = layout(own, rows)
    assert masked == f"Folio Folio ••••89 and PAN {PAN} need a fix"
    out = summary(masked, rows)
    assert out.spans[0] == {"start": a, "end": a + len(FOLIO), "kind": "folio", "hid": "d1"}
    assert out.counts == {"folio": 1} and out.hidden_count == 1
    assert out.receipt == "Hid 1 personal detail from everyone but you: Folio ••••89."


def _sealed(own: str, rows: list[dict[str, Any]]) -> Sealed:
    return Sealed("message", "m1", "idea_messages", "u1", layout(own, rows)[0], own, True)


def test_l_hide_rules_7_a_range_in_the_masked_copy_maps_to_the_owners_words() -> None:
    own = f"Folio {FOLIO}: the agent Kiran Rao said wait"
    a = own.index(FOLIO)
    rows = [_row(1, a, a + len(FOLIO), "folio", FOLIO)]
    src = _sealed(own, rows)
    m = src.masked_now.index("Kiran Rao")
    s, e, shown = _owner_range(src, rows, m, m + len("Kiran Rao"))
    assert own[s:e] == "Kiran Rao" and shown is None


def test_l_hide_rules_7_a_range_on_a_mask_is_already_hidden_and_across_one_is_invalid() -> None:
    own = f"Folio {FOLIO} again"
    rows = [_row(1, 6, 6 + len(FOLIO), "folio", FOLIO)]
    src = _sealed(own, rows)
    m = src.masked_now.index("Folio ••••89")
    with pytest.raises(HideError) as inside:
        _owner_range(src, rows, m, m + 5)
    assert inside.value.code == "already_hidden"
    with pytest.raises(HideError) as across:
        _owner_range(src, rows, 0, m + 3)
    assert across.value.code == "range_invalid"


def test_l_hide_rules_7_a_shown_detail_selected_exactly_is_hidden_again() -> None:
    own = f"Scheme {PAN} again"
    rows = [_row(1, 7, 7 + len(PAN), "pan", PAN, "shown")]
    src = _sealed(own, rows)
    s, e, shown = _owner_range(src, rows, 7, 7 + len(PAN))
    assert (s, e) == (7, 17) and shown is not None and shown["id"] == "d1"
