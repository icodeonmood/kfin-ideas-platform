"""DEC-096: after a recording is heard and its spoken numbers joined, every value the level-1 patterns block is
left out of the text, so investor identifiers are never stored, even encrypted. Synthetic values only."""

from __future__ import annotations

import generators as g

from voice.numbers import normalise
from voice.service import leave_out_blocked


def test_a_pan_is_left_out_and_counted() -> None:
    pan = g.pan(g.default_rng(11))
    text, count = leave_out_blocked(f"The investor's PAN {pan} was keyed twice.")
    assert pan not in text
    assert "[PAN left out]" in text
    assert count == 1


def test_a_spoken_mobile_number_is_joined_then_left_out() -> None:
    digits = "".join(c for c in g.mobile(g.default_rng(5)) if c.isdigit())[-10:]
    words = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
    heard = "call him on " + " ".join(words[int(c)] for c in digits) + " after lunch"
    text, count = leave_out_blocked(normalise(heard))
    assert digits not in text
    assert count == 1
    assert text.startswith("call him on [") and text.endswith("left out] after lunch")


def test_warn_only_values_stay_for_the_person_to_judge() -> None:
    email = g.kfin_email(g.default_rng(2), ["kfintech.com"])
    text, count = leave_out_blocked(f"Ask {email} for the sample report.")
    assert email in text and count == 0


def test_plain_text_is_untouched() -> None:
    words = "Branch staff type every change of bank form twice because the scan is hard to read."
    assert leave_out_blocked(words) == (words, 0)
