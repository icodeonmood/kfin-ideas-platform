"""S-R2.panel, L-LISTEN/2 (BLD-B264): an empty Fix and an empty Attached read the board's words on the reviewer's
page, and the listen script reads the same words. Every other empty part reads "Not given.". Without a database.
Synthetic data only."""

from __future__ import annotations

from desk import listen, reads
from desk.questions import EMPTY_ATTACHED, EMPTY_FIX, PART_EMPTY, PARTS

TEXTS = {
    "summary": "Investors call the branch to ask why a redemption did not go through.",
    "often": "About 40 calls a day at the Hyderabad branch.",
    "who": "Investors, KFin teams.",
}


def _page_parts(texts: dict[str, str]) -> dict[str, dict[str, object]]:
    return {p["part"]: p for p in reads._parts({**dict.fromkeys(PARTS, ""), **texts}, {})}


def test_S_R2_panel_an_empty_fix_reads_no_fix_suggested_it_was_optional() -> None:
    """DeskIdea.md: the Fix part, left empty, reads "No fix suggested. It was optional."."""
    fix = _page_parts(TEXTS)["fix"]
    assert fix["text"] == "" and fix["empty"] == "No fix suggested. It was optional." == EMPTY_FIX


def test_S_R2_panel_an_empty_attached_reads_nothing_attached() -> None:
    """F-COPY.plurals/2: zero in words. The Attached part, with no file and nothing hidden, reads "Nothing
    attached."."""
    attached = _page_parts(TEXTS)["evidence"]
    assert attached["text"] == "" and attached["empty"] == "Nothing attached." == EMPTY_ATTACHED


def test_S_R2_panel_every_other_empty_part_reads_not_given() -> None:
    parts = _page_parts({})
    assert {p: parts[p]["empty"] for p in ("summary", "often", "who", "cost")} == dict.fromkeys(
        ("summary", "often", "who", "cost"), "Not given."
    )
    assert set(PART_EMPTY) == set(PARTS)


def test_S_R2_panel_a_part_with_text_still_carries_its_empty_words() -> None:
    """The web shows `empty` only when `text` is empty; a filled part keeps its own words."""
    parts = _page_parts({**TEXTS, "fix": "Send the reason with the code.", "evidence": "One file: log.pdf."})
    assert parts["fix"]["text"] == "Send the reason with the code."
    assert parts["evidence"]["text"] == "One file: log.pdf."


def test_L_LISTEN_2_the_script_reads_the_pages_words_for_an_empty_fix_and_attached() -> None:
    by = {p.part: p.text for p in listen.build(TEXTS).parts}
    page = {k: v["empty"] for k, v in _page_parts(TEXTS).items()}
    assert by["fix"] == page["fix"] == "No fix suggested. It was optional."
    assert by["evidence"] == page["evidence"] == "Nothing attached."
    assert by["often"] == "About 40 calls a day at the Hyderabad branch."
