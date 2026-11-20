"""Spark tiers (DEC-075, DEC-080, DEC-081; colours from the design pack, F-COLOR.tiers, DEC-102): seven tiers, in the
order a flame heats up. Only Ones have a tier. A tier colour is light and fill only (a ring round the avatar, a bar on
a One's card, a glow behind it), never text: Tiers 6 and 7 fail as text on the dark slab. Keep these in step with
--tier-N in apps/web/src/app/tokens.css. The Spark mark keeps #F46835 whatever the tier."""

from __future__ import annotations

TIERS: dict[int, tuple[str, str]] = {
    1: ("Spark", "#F5863B"),
    2: ("Glow", "#F35532"),
    3: ("Flame", "#F34770"),
    4: ("Blaze", "#F23729"),
    5: ("White heat", "#4DD187"),
    6: ("Blue flame", "#264DC9"),  # tiers 6 and 7 swap the pack's colours, so Blue flame is blue (BLD-D023)
    7: ("Star", "#8841E1"),
}


def tier_name(tier: int) -> str:
    return TIERS[tier][0]


def tier_colour(tier: int) -> str:
    return TIERS[tier][1]
