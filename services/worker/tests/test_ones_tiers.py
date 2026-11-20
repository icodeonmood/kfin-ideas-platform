"""F-COLOR.tiers (BLD-D023): tiers 6 and 7 swap the pack's colours, so "Blue flame" is blue and "Star" is violet.
The names and the order stay. The worker's table and the web app's tokens.css hold the same seven key colours."""

from __future__ import annotations

import re
from pathlib import Path

from ones.tiers import TIERS, tier_colour, tier_name

TOKENS = Path(__file__).resolve().parents[3] / "apps" / "web" / "src" / "app" / "tokens.css"


def test_f_color_tiers_tier_6_is_blue_and_tier_7_is_violet() -> None:
    assert (tier_name(6), tier_colour(6)) == ("Blue flame", "#264DC9")
    assert (tier_name(7), tier_colour(7)) == ("Star", "#8841E1")


def test_f_color_tiers_names_and_order_are_unchanged() -> None:
    assert [TIERS[n][0] for n in range(1, 8)] == [
        "Spark",
        "Glow",
        "Flame",
        "Blaze",
        "White heat",
        "Blue flame",
        "Star",
    ]


def test_f_color_tiers_match_the_web_tokens() -> None:
    css = TOKENS.read_text(encoding="utf-8")
    web = {int(n): hex_ for n, hex_ in re.findall(r"--tier-(\d):(#[0-9A-F]{6});", css)}
    assert web == {n: colour for n, (_, colour) in TIERS.items()}
