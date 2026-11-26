"""A customer's name typed in lower case is tagged from r7 (DEC-142; lane C, BLD-C251): a known given name followed by
a known surname, both from pii/names/, in any case. One word alone never counts. Both paths: `pii.detect` (tags before
any model call, non-negotiable 2) and `hide.detect.people_in` (a name beside another detail, L-HIDE.detect, DEC-103).
Pure unit tests, no database. Every name and number here is synthetic."""

from __future__ import annotations

import pytest

from hide import detect as hide
from pii import detect

PAN_SENTENCE = "ravi kumar ka PAN ABCPE1234F hai"


def people(text: str, d: detect.Directory | None = None) -> list[str]:
    found = detect.detect(text, d or detect.Directory().compile(), kfin_domains=[])
    return [f.value for f in found if f.type == "PERSON"]


def hidden(text: str) -> list[tuple[str, str]]:
    return [(f.kind, f.value) for f in hide.find(None, text, gatekeeper=False)]


@pytest.mark.parametrize(
    ("text", "names"),
    [
        ("my client ravi kumar called twice about the form", ["ravi kumar"]),
        ("spoke to anita sharma and ravi kumar today", ["anita sharma", "ravi kumar"]),
        ("ravi shankar kumar sent it", ["ravi shankar kumar"]),  # a middle name
        ("ravi prasad sent it", ["ravi prasad"]),  # prasad is a given name and a surname
        ("Ravi kumar called", ["Ravi kumar"]),  # one span, not "Ravi" alone
    ],
)
def test_bld_c251_a_known_given_name_and_surname_in_lower_case_is_a_person(
    text: str, names: list[str]
) -> None:
    assert people(text) == names


def test_bld_c251_hinglish_in_latin_script() -> None:
    text = "devika raghunathan ne bataya ki form do baar type hota hai"
    assert not any(ch.isupper() for ch in text)
    assert people(text) == ["devika raghunathan"]
    assert people("kal amit sharma ji se baat hui") == ["amit sharma"]


@pytest.mark.parametrize(
    "text",
    [
        "ravi said the form was late",  # a given name alone
        "kumar sent it again",  # a surname alone
        "asha hai ki form aayega",  # everyday words that are also names
        "kiran ne prakash ko bataya",  # two given names, no surname
        "ravi, kumar and the others",  # never across a comma
        "send it to ravi.kumar@kfintech.example",  # an address is not a name
    ],
)
def test_bld_c251_a_single_word_or_a_broken_pair_stays_untagged(text: str) -> None:
    assert people(text) == []


def test_bld_c251_the_pan_sentence_tags_the_name_and_hides_it_beside_the_pan() -> None:
    """The sentence from the part-1 brief note: before, the PAN hid and "ravi kumar" stayed visible to the desk."""
    found = detect.detect(PAN_SENTENCE, detect.Directory().compile(), kfin_domains=[])
    assert ("PERSON", "ravi kumar") in [(f.type, f.value) for f in found]
    assert "ABCPE1234F" in [f.value for f in found]
    assert ("name", "ravi kumar") in hidden(PAN_SENTENCE)


def test_bld_c251_a_lower_case_name_hides_beside_a_detail_with_no_capital_letter_at_all() -> None:
    text = "ravi kumar ka phone 9876543210 hai. amit sharma ne baad mein bataya."
    assert not any(ch.isupper() for ch in text)
    found = hidden(text)
    assert ("name", "ravi kumar") in found and any(k == "phone" for k, _ in found)
    assert all("amit" not in v for _, v in found)  # another sentence: not hidden
    assert hide.people_in(None, "the form was late again") == []  # nothing to read, nothing loaded


def test_bld_c251_a_colleague_is_still_a_colleague() -> None:
    """A colleague in the people directory keeps the employee tag, and hiding never hides a colleague."""
    d = detect.Directory(employee_names={"ravi kumar": "u-synthetic-1"}).compile()
    found = detect.detect("my client ravi kumar called", d, kfin_domains=[])
    assert [(f.type, f.value) for f in found] == [("KFIN_EMPLOYEE", "ravi kumar")]
    assert hide.people_in(None, PAN_SENTENCE, d) == []


def test_bld_c251_a_glossary_term_is_never_a_person() -> None:
    d = detect.Directory(never_person={"ravi kumar"}).compile()
    assert people("my client ravi kumar called", d) == []


def test_bld_c251_may_hold_names() -> None:
    assert detect.may_hold_names("ravi kumar called")
    assert detect.may_hold_names("Called about the form")
    assert not detect.may_hold_names("ravi called about the form")
