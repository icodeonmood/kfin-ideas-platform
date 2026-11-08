"""Level-1 pattern check against generated values (the full shared vector set arrives in B3)."""

import generators as g
import pytest

from pii.patterns import luhn_valid, scan, verhoeff_valid

KFIN = ["kfintech.com"]


def _ids(text: str) -> set[str]:
    return {m.pattern_id for m in scan(text, kfin_domains=KFIN) if m.action == "block"}


@pytest.mark.parametrize("seed", range(25))
def test_generated_identifiers_block(seed: int) -> None:
    rng = g.default_rng(seed)
    assert "pan" in _ids(f"Investor PAN {g.pan(rng)} called today")
    assert "aadhaar" in _ids(f"Aadhaar {g.aadhaar(rng)} was in the remarks")
    assert "mobile" in _ids(f"Call back on {g.mobile(rng)} please")
    assert "email" in _ids(f"mailed {g.ext_email(rng)} yesterday")
    assert "card" in _ids(f"card {g.card(rng)} declined")
    assert "bank_account" in _ids(f"a/c {g.account(rng)} bounced")
    assert "folio" in _ids(f"folio {g.folio(rng)} has a stuck SIP")
    assert "pran" in _ids(f"PRAN {g.pran(rng)} not updated")
    assert "dob" in _ids(f"DOB {g.dob(rng)} mismatch")


def test_checksums_from_generators_are_valid() -> None:
    rng = g.default_rng()
    for _ in range(50):
        assert verhoeff_valid(g.aadhaar(rng).replace(" ", "").replace("-", ""))
        assert luhn_valid(g.card(rng).replace(" ", ""))


def test_allowed_and_warn_only() -> None:
    rng = g.default_rng(7)
    assert _ids(f"Aadhaar {g.aadhaar_masked(rng)} is masked, which is fine") == set()
    warns = scan(f"write to {g.kfin_email(rng, KFIN)}", kfin_domains=KFIN)
    assert [m.action for m in warns] == ["warn"]
    assert {m.action for m in scan(f"distributor {g.arn(rng)}", kfin_domains=KFIN)} == {"warn"}


def test_near_misses_do_not_block() -> None:
    # 10-digit numbers starting 1-5, scheme codes, ISINs and dates without birth context.
    for text in (
        "We processed 1234567890 units last year",
        "Scheme code 120503 and ISIN INF200K01RJ1 are fine",
        "The cut-off is 15/03/2026 for this quarter",
        "Invoice 5023 from the vendor",
    ):
        assert _ids(text) == set(), text


@pytest.mark.parametrize("seed", range(10))
def test_mobile_written_as_91_plus_ten_digits(seed: int) -> None:
    rng = g.default_rng(100 + seed)
    ten = "".join(rng.choice("6789") if i == 0 else rng.choice("0123456789") for i in range(10))
    assert "mobile" in _ids(f"call 91{ten} today")
    assert "mobile" in _ids(f"call +91{ten} today")
