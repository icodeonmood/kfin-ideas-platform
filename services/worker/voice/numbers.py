"""Spoken numbers to digits (DEC-096), before anything else sees a transcript.

A speech engine may write "nine eight seven six five…" or "A B C D E one two three four F" where a typist would
write digits. The level-1 patterns (§4.2 step 2) look for digits, so a spoken mobile number, PAN or folio would
slip through. This module collapses a run of spelled-out characters into one token:

- a unit is a single letter, a single digit (ASCII or Devanagari), or a digit word in English ("zero", "oh",
  "one" … "nine") or Hindi, romanised or in Devanagari ("shunya", "ek", "do", "teen" … "nau"; "शून्य", "एक" …).
  A spoken letter O stays a letter (PANs have them); "no" is never read as nine;
- "double" and "triple" (and "dabal", "tripal") repeat the next digit;
- a run of 4 or more units with at least 2 digits becomes one token, so "we do it" or "oh, I see" never change.

Devanagari digits (०–९) always become ASCII digits. Multi-digit words ("ninety eight") are left alone: engines
write those as digits already. Pure: no logging, no I/O.
"""

from __future__ import annotations

import re

DIGIT_WORDS: dict[str, str] = {
    # English
    "zero": "0", "oh": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9",
    # Hindi, romanised
    "shunya": "0", "shoonya": "0", "sunya": "0", "ek": "1", "do": "2", "teen": "3", "tin": "3", "char": "4",
    "chaar": "4", "paanch": "5", "panch": "5", "chhe": "6", "chhah": "6", "che": "6", "chah": "6", "saat": "7",
    "sat": "7", "aath": "8", "ath": "8", "nau": "9",
    # Hindi, Devanagari
    "शून्य": "0", "एक": "1", "दो": "2", "तीन": "3", "चार": "4", "पांच": "5", "पाँच": "5", "छह": "6",
    "छः": "6", "छे": "6", "सात": "7", "आठ": "8", "नौ": "9",
}  # fmt: skip
REPEAT = {"double": 2, "dabal": 2, "triple": 3, "tripal": 3}
DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
MIN_UNITS = 4
MIN_DIGITS = 2

_TOKEN = re.compile(r"\S+")
_EDGE = re.compile(r"^([^\wऀ-ॿ]*)(.*?)([^\wऀ-ॿ]*)$", re.UNICODE)


def _unit(word: str) -> tuple[str, bool] | None:
    """(characters, is_digit) for one spoken unit, or None if the word is not one."""
    low = word.lower()
    if low in DIGIT_WORDS:
        return DIGIT_WORDS[low], True
    if len(word) == 1 and word.isdigit():
        return word, True
    if len(word) == 1 and word.isascii() and word.isalpha():
        return word.upper(), False
    return None


def normalise(text: str) -> str:
    """The transcript with runs of spoken characters joined into digits and capitals."""
    text = text.translate(DEVANAGARI_DIGITS)
    tokens = [(m.start(), m.end(), m.group()) for m in _TOKEN.finditer(text)]
    out: list[str] = []
    cursor = 0
    i = 0
    while i < len(tokens):
        run, j = _run(tokens, i)
        if run is not None:
            start, end = tokens[i][0], tokens[j - 1][1]
            lead = _EDGE.match(tokens[i][2]).group(1)  # type: ignore[union-attr]
            trail = _EDGE.match(tokens[j - 1][2]).group(3)  # type: ignore[union-attr]
            out.append(text[cursor:start] + lead + run + trail)
            cursor = end
            i = j
        else:
            i += 1
    out.append(text[cursor:])
    return "".join(out)


def _run(tokens: list[tuple[int, int, str]], i: int) -> tuple[str | None, int]:
    """The joined run starting at token i (or None) and the index after it."""
    chars: list[str] = []
    units = digits = 0
    j = i
    repeat = 1
    while j < len(tokens):
        lead, core, trail = _EDGE.match(tokens[j][2]).groups()  # type: ignore[union-attr]
        if lead and j > i:
            break  # punctuation before a word starts a new phrase
        if core.lower() in REPEAT:
            if j + 1 >= len(tokens) or trail:
                break
            repeat = REPEAT[core.lower()]
            j += 1
            continue
        unit = _unit(core)
        if unit is None or (repeat > 1 and not unit[1]):
            break
        chars.append(unit[0] * repeat)
        units += repeat
        digits += repeat if unit[1] else 0
        repeat = 1
        j += 1
        if trail and trail not in "-":
            break  # a comma or full stop ends the run
    if repeat > 1:
        j -= 1  # a dangling "double" belongs to the text
    if units >= MIN_UNITS and digits >= MIN_DIGITS:
        return "".join(chars), j
    return None, i + 1
