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
    """Whatever span edges the name recogniser draws, the name in the folio's sentence hides and the other not."""
    text = f"Ramesh Gupta called again. Customer Suresh Iyer sent folio {FOLIO} by post."
    found = kinds(text)
    names = [v for k, v in found if k == "name"]
    assert any("Suresh" in v or "Iyer" in v for v in names)
    assert all("Ramesh" not in v and "Gupta" not in v for _, v in found)
    assert ("folio", FOLIO) in found


def test_l_hide_detect_values_match_as_whole_words_in_any_case() -> None:
    """Review fix 3 (BLD-C066): "kiran rao" goes with "Kiran Rao", a longer word stays, a mask is never re-masked."""
    text = "Ask kiran  rao, then Kiran Rao again, not Kiran Raona"
    assert detect.value_places(text, "Kiran Rao") == [(4, 14), (21, 30)]
    masked, n = detect.mask_in(text, "Kiran Rao", "Name ••••ao")
    assert n == 2 and masked == "Ask Name ••••ao, then Name ••••ao again, not Kiran Raona"
    assert detect.mask_in("Name ••••ao and Name Lal", "Name")[1] == 1  # the mask's own word is left alone
    assert detect.same_value("Kiran Rao", "KIRAN RAO") and not detect.same_value("Kiran Rao", "Kiran Raona")


def test_l_hide_rules_3_a_short_value_shows_no_tail() -> None:
    """Review fix 12 (BLD-C069): a mask never shows most of a short value."""
    assert detect.mask("name", "Om") == "Name ••••"
    assert detect.mask("name", "Ravi") == "Name ••••"
    assert detect.mask("name", "Kiran") == "Name ••••an"
    assert detect.mask_tokens("Ask Name •••• now") == [(4, 13)]


def test_l_hide_rules_2_offsets_between_utf16_and_code_points() -> None:
    """Review fix 8 (BLD-C068): an emoji is one code point and two UTF-16 units."""
    text = f"Late 😀 for folio {FOLIO}"
    at = text.index(FOLIO)
    units = detect.to_utf16(text, at)
    assert units == at + 1 and detect.from_utf16(text, units) == at
    assert (
        detect.from_utf16(text, detect.to_utf16(text, text.index("😀")) + 1) is None
    )  # inside its two units
    assert detect.from_utf16(text, detect.to_utf16(text, len(text))) == len(text)
    assert detect.from_utf16(text, 10_000) is None


def test_l_hide_api_errors_have_the_packs_shape_and_no_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """Review fix 13: a refusal is {error: {code, message}}; anything else is a fixed `hide_failed`, never text."""
    import json

    from hide import api

    def refuse(conn: Any) -> None:
        raise HideError(403, "forbidden")

    def crash(conn: Any) -> None:
        raise RuntimeError(f"folio {FOLIO} broke")

    class FakeConn:
        def __enter__(self) -> FakeConn:
            return self

        def __exit__(self, *exc: object) -> None:
            return None

        def transaction(self) -> FakeConn:
            return self

    monkeypatch.setattr(api, "connect", lambda **_: FakeConn())
    refused = api._call(refuse)
    assert refused.status_code == 403
    assert json.loads(bytes(refused.body)) == {"error": {"code": "forbidden", "message": ""}}
    failed = api._call(crash)
    assert failed.status_code == 500 and FOLIO not in bytes(failed.body).decode()
    assert json.loads(bytes(failed.body)) == {"error": {"code": "hide_failed", "message": ""}}


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


def test_l_hide_rules_7_stale_when_the_selected_words_are_no_longer_at_the_range() -> None:
    """F (lane B's `selected`, BLD-C066): the range is compared with the masked words the reviewer selected, in the
    same units after the UTF-16 conversion and without the spaces at either end; a range off the text with
    `selected` is stale too. Without `selected` nothing changes."""
    from hide.desk import MAX_SELECTION, _range

    seen = "Late 😀 for Kiran Rao and Folio ••••89"
    at = seen.index("Kiran Rao")
    u_start, u_end = detect.to_utf16(seen, at), detect.to_utf16(seen, at + len("Kiran Rao"))
    assert u_start == at + 1  # the browser's count after the emoji
    assert _range(seen, u_start, u_end, "utf16", "Kiran Rao") == (at, at + len("Kiran Rao"))
    assert _range(seen, u_start, u_end, "utf16", " Kiran Rao\n") == (at, at + len("Kiran Rao"))
    assert _range(seen, u_start, u_end, "utf16", None) == (at, at + len("Kiran Rao"))
    for start, end, selected in (
        (u_start + 1, u_end + 1, "Kiran Rao"),  # the text moved by one under the page
        (u_start, u_end, "Kiran Raona"),
        (detect.to_utf16(seen, seen.index("😀")) + 1, u_end, "Kiran Rao"),  # splits the emoji now
        (u_start, 10_000, "Kiran Rao"),  # past the end of the text now
    ):
        with pytest.raises(HideError) as stale:
            _range(seen, start, end, "utf16", selected)
        assert (stale.value.status, stale.value.code) == (409, "stale")
    with pytest.raises(HideError) as outside:
        _range(seen, u_start, 10_000, "utf16", None)
    assert outside.value.code == "range_invalid"
    with pytest.raises(HideError) as cp_outside:
        _range(seen, at, 10_000, "cp", None)
    assert cp_outside.value.code == "range_invalid"
    long = "x" * (MAX_SELECTION + 1)
    with pytest.raises(HideError) as too_long:
        _range(long, 0, len(long), "cp", long)
    assert (too_long.value.status, too_long.value.code) == (422, "selection_too_long")


def test_l_hide_rules_7_selected_is_checked_before_the_database() -> None:
    """F: `selected` must be a string of at most 10,000 UTF-16 units (twice the longest text, V-FIELDS.submit/2);
    the refusal comes before any database work and never echoes the words."""
    from hide.desk import SELECTED_MAX, desk_hide

    base: dict[str, Any] = {"source_kind": "message", "source_id": "m1", "start": 0, "end": 5, "by": "u1"}
    with pytest.raises(HideError) as not_text:
        desk_hide(None, "idea", **base, selected=42)  # type: ignore[arg-type]
    assert not_text.value.code == "range_invalid"
    with pytest.raises(HideError) as too_long:
        desk_hide(None, "idea", **base, selected="😀" * (SELECTED_MAX // 2 + 1))  # type: ignore[arg-type]
    assert (too_long.value.status, too_long.value.code) == (422, "selection_too_long")
    assert "😀" not in str(too_long.value)


def test_l_hide_rules_7_a_refused_own_idea_is_audited_after_the_rollback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """G (BLD-C066): the route writes the refusal's audit row (IDs and the action only) once the transaction that
    refused has rolled back, and answers 403 `forbidden` in the A-API shape."""
    import json

    from hide import api, core

    written: list[tuple[Any, ...]] = []
    rolled_back: list[bool] = []

    class FakeConn:
        def __enter__(self) -> FakeConn:
            return self

        def __exit__(self, *exc: object) -> None:
            if exc[0] is not None:
                rolled_back.append(True)
            return None

        def transaction(self) -> FakeConn:
            return self

    def own(conn: Any) -> None:
        raise HideError(
            403, "forbidden", audit=("u1", "hide.own_idea_refused", "i1", {"action": "desk_hide"})
        )

    def audit(conn: Any, *args: Any) -> None:
        assert rolled_back, "the audit row is written after the rollback"
        written.append(args)

    monkeypatch.setattr(api, "connect", lambda **_: FakeConn())
    monkeypatch.setattr(core, "audit", audit)
    refused = api._call(own)
    assert refused.status_code == 403
    assert json.loads(bytes(refused.body)) == {"error": {"code": "forbidden", "message": ""}}
    assert written == [("u1", "hide.own_idea_refused", "i1", {"action": "desk_hide"})]


def test_l_hide_detect_a_word_ends_after_its_marks_in_devanagari_and_latin() -> None:
    """A (BLD-C066): combining marks continue a word, so a made-up name hidden as "किरण सुधाकलन" is not masked inside
    "किरण सुधाकलनों" (which would leave "ों" after the mask); it is masked before a space, a danda or a comma. The
    same holds for an accent typed as a mark in Latin, and the old Latin cases stay."""
    name = "किरण सुधाकलन"
    text = f"{name}ों से बात हुई। फिर {name} ने कहा, {name}। {name},"
    places = detect.value_places(text, name)
    assert [text[s:e] for s, e in places] == [name] * 3
    assert all(not text[e:].startswith("ों") for _, e in places)
    masked, n = detect.mask_in(text, name, detect.mask("name", name))
    assert n == 3 and masked.startswith(f"{name}ों से") and masked.count("Name ••••") == 3
    assert detect.value_places("किरणों", "किरण") == [] and detect.value_places("किरण ने", "किरण") == [(0, 4)]
    assert detect.same_value(name, name) and not detect.same_value("किरण", "किरणों")
    assert detect.value_places("José and Jose went", "Jose") == [(10, 14)]
    assert detect.value_places("Ask kiran  rao, not Kiran Raona", "Kiran Rao") == [(4, 14)]
    assert detect.value_places("Folio 1234567/89, again 1234567/89.", "1234567/89") == [(6, 16), (24, 34)]
