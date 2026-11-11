"""Spark tiers (DEC-075, DEC-080, DEC-081; colours DEC-098): seven tiers, in the order a flame heats up. Only Ones
have a tier; the spark is lit at Tier 1 (Spark) on induction. A tier colour is light and fill only (the One's spark,
badge, swatch and dashboard accent), never small text: a One's number is drawn from a pale core to the tier colour,
because Tiers 6 and 7 fail as text on Zed (DEC-098). The Spark mark keeps #FF5B14 whatever the tier."""

from __future__ import annotations

TIERS: dict[int, tuple[str, str]] = {
    1: ("Spark", "#FF7F14"),
    2: ("Glow", "#FF4313"),
    3: ("Flame", "#FF2E6B"),
    4: ("Blaze", "#FF0000"),
    5: ("White heat", "#27D57F"),
    6: ("Blue flame", "#8C2FF1"),
    7: ("Star", "#1E46D9"),
}


def tier_name(tier: int) -> str:
    return TIERS[tier][0]


def tier_colour(tier: int) -> str:
    return TIERS[tier][1]
