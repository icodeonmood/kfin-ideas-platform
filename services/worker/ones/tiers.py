"""Spark tiers (DEC-075, DEC-080, DEC-081): seven tiers coloured the way a flame heats up. Only Ones have a tier;
the spark is lit at Tier 1 (Spark, orange) on induction. The tier colour is the One's spark, badge and dashboard
accent, always shown on Zed."""

from __future__ import annotations

TIERS: dict[int, tuple[str, str]] = {
    1: ("Spark", "#FF5B14"),
    2: ("Glow", "#FF8A1F"),
    3: ("Flame", "#FFC21F"),
    4: ("Blaze", "#FFE58A"),
    5: ("White heat", "#F4F6FA"),
    6: ("Blue flame", "#9DBEFF"),
    7: ("Star", "#6E9BFF"),
}


def tier_name(tier: int) -> str:
    return TIERS[tier][0]


def tier_colour(tier: int) -> str:
    return TIERS[tier][1]
