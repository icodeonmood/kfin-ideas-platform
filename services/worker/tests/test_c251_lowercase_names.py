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
        ("RAVI KUMAR called", ["RAVI KUMAR"]),
        # From the review of a94add9f: a possessive, a quote, the curly apostrophe phones type, two middle names.
        ("my client ravi kumar's pan is late", ["ravi kumar"]),
        ("my client ravi kumar’s pan is late", ["ravi kumar"]),
        ("the customer 'ravi kumar' called", ["ravi kumar"]),
        ("anita d’souza and anita d'souza", ["anita d’souza", "anita d'souza"]),
        ("ravi shankar anand kumar sent it", ["ravi shankar anand kumar"]),
        # From the re-review: a name followed by an everyday word is still a name, never let through.
        ("ravi das baar baar call kar rahe hain", ["ravi das"]),
        ("mera client karan das. din mein do baar call kiya", ["karan das"]),
        # Two list words that mean something else are tagged too: the safe way to be wrong (BLD-C251).
        ("maine form submit kar diya das baje", ["diya das"]),
    ],
)
def test_bld_c251_a_known_given_name_and_surname_in_lower_case_is_a_person(
    text: str, names: list[str]
) -> None:
    assert people(text) == names


def test_bld_c251_a_name_followed_by_an_everyday_word_is_tagged_and_hidden_beside_the_pan() -> None:
    """The re-review of 443d3771: "das log in" must not undo the name. In mixed text with a capital letter the English
    NER model may tag more besides; never less."""
    text = "customer ravi das log in nahi kar pa raha, PAN ABCPE1234F"
    assert "ravi das" in people(text)
    assert ("name", "ravi das") in hidden(text)


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
        "ravi\nkumar",  # never across a new line
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
