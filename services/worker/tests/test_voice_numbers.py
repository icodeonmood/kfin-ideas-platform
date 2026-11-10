"""DEC-096: spoken numbers become digits before anything sees a transcript, so the level-1 patterns still block a
spoken PAN, mobile number or folio. Synthetic values only (eval/golden/generators.py)."""

from __future__ import annotations

import generators as g
import pytest

from pii.patterns import scan
from voice.numbers import normalise

WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
HINDI = ["shunya", "ek", "do", "teen", "char", "paanch", "chhe", "saat", "aath", "nau"]
DEVANAGARI = ["शून्य", "एक", "दो", "तीन", "चार", "पांच", "छह", "सात", "आठ", "नौ"]


def spell(value: str, words: list[str] = WORDS) -> str:
    """Say a value character by character, as a person reading it out would."""
    return " ".join(words[int(c)] if c.isdigit() else c for c in value)


def blocked(text: str) -> set[str]:
    return {m.label for m in scan(text) if m.action == "block"}


@pytest.mark.parametrize("seed", range(5))
def test_a_spoken_pan_is_joined_and_blocked(seed: int) -> None:
    pan = g.pan(g.default_rng(seed))
    text = normalise(f"my PAN is {spell(pan)} and the form was late")
    assert pan in text
    assert "PAN" in blocked(text)


@pytest.mark.parametrize("words", [WORDS, HINDI, DEVANAGARI])
def test_a_spoken_mobile_number_in_english_or_hindi_is_blocked(words: list[str]) -> None:
    digits = "".join(c for c in g.mobile(g.default_rng(3)) if c.isdigit())[-10:]
    text = normalise(f"call the investor on {spell(digits, words)} tomorrow")
    assert digits in text
    assert blocked(text)


def test_double_and_triple_repeat_the_next_digit() -> None:
    assert normalise("folio double five three triple seven one two") == "folio 55377712"


def test_devanagari_digits_become_ascii() -> None:
    assert normalise("Folio १२३४५६७८ was wrong") == "Folio 12345678 was wrong"


@pytest.mark.parametrize(
    "text",
    [
        "we do it every day",
        "oh, I see a lot of rework at the branch",
        "I am at a desk near the door",
        "Section A B C of the form",
        "it takes two or three days",
        "No. 17 shared this first",
        "we sat with the team for an hour",
    ],
)
def test_near_misses_never_change(text: str) -> None:
    assert normalise(text) == text


def test_a_spoken_letter_o_stays_a_letter() -> None:
    assert normalise("PAN A B C D O one two three four F") == "PAN ABCDO1234F"


def test_punctuation_ends_a_run_and_survives() -> None:
    assert normalise("codes: one two three four, then five six") == "codes: 1234, then five six"
