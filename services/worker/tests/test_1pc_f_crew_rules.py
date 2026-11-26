"""L-CREW's rules without a database: the card's sentences (L-CREW/4), the reason lines (L-CREW/2), team sizes and
filters with live counts (L-CREW/5), and the deck order (L-CREW/3)."""

from __future__ import annotations

import dataclasses
import datetime as dt

from crew import deck
from crew.deck import Card
from crew.store import day_label
from similar.preview import hidden_person

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
NOW = dt.datetime(2026, 11, 17, 12, 0, tzinfo=IST)  # Tuesday


def test_L_CREW_4_in_their_words_is_one_sentence_cut_at_a_word() -> None:
    assert deck.first_sentence("Investors get a code, not a reason. Then they call us.") == (
        "Investors get a code, not a reason."
    )
    long = "word " * 60
    s = deck.first_sentence(long, limit=40)
    assert s.endswith("…") and len(s) <= 41 and "  " not in s
    assert deck.first_sentence(None) == ""


def test_L_CREW_4_looking_for_is_the_sharers_answer_then_their_picks_else_nothing() -> None:
    assert deck.looking_for(["Branch staff"], "Someone who takes these calls every day. And more.") == (
        "Someone who takes these calls every day."
    )
    assert (
        deck.looking_for(["Someone from tech", "Data or reports"], None)
        == "Someone from tech, data or reports"
    )
    assert deck.looking_for([], "   ") is None
    # A typed answer that trips a personal-data pattern never shows; the picks stand in (non-negotiable 4).
    assert deck.looking_for(["Branch staff"], "Call me on 9876543210 about it") == "Branch staff"


def test_L_CREW_5_team_sizes_count_the_lead() -> None:
    assert [deck.team_size(n) for n in (1, 2, 3, 4, 9)] == [
        "lead_only", "two_to_three", "two_to_three", "four_plus", "four_plus",
    ]  # fmt: skip


def test_L_CREW_2_touches_their_work_when_the_sharer_asks_for_their_line_of_work() -> None:
    assert deck.touches(["Someone in operations"], "Operations")
    assert deck.touches(["Someone from tech"], "Technology")
    assert deck.touches(["Investor service"], "Investor service")
    assert not deck.touches(["Customer service"], "Investor service")
    assert not deck.touches([], "Operations")
    assert not deck.touches(["Someone in operations"], None)


def test_L_CREW_2_reason_lines() -> None:
    sat = dt.datetime(2026, 11, 14, 10, 0, tzinfo=IST)
    assert (
        deck.close_reason("Close match: same R07 SMS", True, sat, NOW)
        == "Same R07 SMS as your idea from Saturday"
    )
    assert deck.close_reason("Related: the calls branches take", True, sat, NOW) == (
        "The calls branches take, like your idea from Saturday"
    )
    # A match found for someone else's newer idea speaks to them, so the card names this person's idea instead.
    assert (
        deck.close_reason("Related: the calls you describe", False, sat, NOW)
        == "Close to your idea from Saturday"
    )
    assert deck.close_reason("", True, sat, NOW) == "Close to your idea from Saturday"
    assert deck.area_reason("Investor service") == "Your area, Investor service"
    assert deck.office_reason("Hyderabad") == "Same office as you, Hyderabad"
    assert deck.touches_reason("Operations") == "They need someone in Operations"


def test_day_labels_in_india_time() -> None:
    assert day_label(NOW - dt.timedelta(hours=1), NOW) == "today"
    assert day_label(NOW - dt.timedelta(days=1), NOW) == "yesterday"
    assert day_label(dt.datetime(2026, 11, 14, 20, 0, tzinfo=dt.UTC), NOW) == "Sunday"  # 01:30 IST Sunday
    assert day_label(dt.datetime(2026, 11, 2, 10, 0, tzinfo=IST), NOW) == "2 November"


def _card(
    ref: str, city: str, area: str, status: str, crew: int, picks: tuple[str, ...], kind: str, days: float
) -> Card:
    lead = {
        "id": "u",
        "name": "Leela Sharma",
        "first_name": "Leela",
        "initials": "LS",
        "area": area,
        "city": city,
    }
    return Card(
        ref, ref, f"Idea {ref}", status, area, city, NOW - dt.timedelta(days=days), lead, (lead,), crew,
        "One sentence.", None, picks, kind, "Reason", (deck.REASONS.index(kind), 0, 0, 0),
    )  # fmt: skip


# The board's deck (Crew, default state) as data: five cards, the person in Hyderabad.
BOARD = [
    _card("IDEA-2026-000001", "Hyderabad", "Investor service", "with_review_desk", 4, ("Branch staff",), "close_to_yours", 3),
    _card("IDEA-2026-000002", "Mumbai", "Operations", "picked", 2, ("Investor service",), "close_to_yours", 2),
    _card("IDEA-2026-000003", "Chennai", "Investor service", "with_review_desk", 3, ("Branch staff",), "same_area", 1),
    _card("IDEA-2026-000004", "Pune", "Operations", "with_review_desk", 2, ("Investor service",), "touches_your_work", 4),
    _card("IDEA-2026-000005", "Hyderabad", "Operations", "checking", 1, ("Operations",), "same_office", 0.5),
]  # fmt: skip


def test_L_CREW_5_counts_are_live_given_the_other_filters_as_on_the_board() -> None:
    active = deck.normalise({"location": ["Hyderabad"]})
    groups = {
        g["key"]: {o["label"]: o["count"] for o in g["options"]} for g in deck.facet_groups(BOARD, active)
    }
    # Board "Filters open": Hyderabad 2, Mumbai 1, Chennai 1, Pune 1; Investor service 1, Operations 1; Shared 1,
    # With the review desk 1, Picked 0; Just the lead 1, 2 to 3 people 0, 4 or more 1.
    assert groups["location"] == {"Hyderabad": 2, "Mumbai": 1, "Chennai": 1, "Pune": 1}
    assert groups["category"] == {"Investor service": 1, "Operations": 1}
    assert groups["status"] == {"Shared": 1, "With the review desk": 1, "Picked": 0}
    assert groups["team_size"] == {"Just the lead": 1, "2 to 3 people": 0, "4 or more": 1}
    assert groups["looking_for"] == {"Branch staff": 1, "Investor service": 0, "Operations": 1}
    assert deck.chips(active) == [{"key": "location", "value": "Hyderabad", "label": "Hyderabad"}]
    shown = [c for c in BOARD if deck._matches(c, active)]
    assert len(shown) == 2  # "Show 2 ideas"


def test_L_CREW_5_unknown_filters_are_dropped_and_values_kept_once() -> None:
    active = deck.normalise({"location": [" Pune ", "Pune", ""], "status": ["bogus", "picked"], "colour": ["red"],
                             "team_size": ["huge", "four_plus"]})  # fmt: skip
    assert active == {"location": ["Pune"], "status": ["picked"], "team_size": ["four_plus"]}
    # A stale value from a shared link still shows as an option with 0, so its chip can be removed.
    stale = deck.normalise({"location": ["Shimla"]})
    loc = next(g for g in deck.facet_groups(BOARD, stale) if g["key"] == "location")
    assert loc["options"][-1] == {"value": "Shimla", "label": "Shimla", "count": 0, "active": True}


def test_L_CREW_3_order_is_strength_then_most_recent() -> None:
    order = [c.ref[-1] for c in sorted(reversed(BOARD), key=deck.order_key)]
    assert order == ["2", "1", "4", "3", "5"]


def test_L_CREW_4_card_json_is_a_crew_card_with_masked_text_only() -> None:
    body = BOARD[0].as_json()
    assert set(body) == {
        "id", "title", "status", "area", "city", "shared_at", "lead", "crew_faces", "crew_count",
        "in_their_words", "hue", "reason_kind", "reason",
    }  # fmt: skip
    assert "compare" not in body and body["hue"] in (1, 2)
    # Someone who hid their name, or has left, is "A colleague" with no user id (BLD-F042).
    hidden = hidden_person("CTR-0a1b2c")
    assert hidden["name"] == "A colleague" and hidden["id"].startswith("p") and hidden["initials"] == ""


# --- DEC-126 (WF-03b, BLD-F094): requested cards sort last; Home's short read keeps the latest one -------------
def _asked(card: Card, rid: str, hours_ago: float, kind: str = "teamup") -> Card:
    return dataclasses.replace(card, request=(rid, kind), requested_at=NOW - dt.timedelta(hours=hours_ago))


def test_DEC_126_L_CREW_3_requested_cards_come_last_oldest_request_first() -> None:
    board = [_asked(BOARD[1], "r-new", 1), *BOARD[2:], _asked(BOARD[0], "r-old", 30)]
    order = [c.ref[-1] for c in sorted(board, key=deck.order_key)]
    assert order == ["4", "3", "5", "1", "2"]


def test_DEC_126_L_CREW_4_a_requested_card_carries_its_request_id_and_kind_only() -> None:
    body = _asked(BOARD[0], "0b6f2c1e-7d1a-4c55-9a0e-3b8f1d2c4e5a", 2, "merge").as_json()
    assert body["request"] == {"id": "0b6f2c1e-7d1a-4c55-9a0e-3b8f1d2c4e5a", "kind": "merge"}
    assert "request" not in BOARD[0].as_json()


def test_DEC_126_L_CREW_10_a_short_read_ends_with_the_latest_requested_card() -> None:
    others = list(BOARD[2:])  # three cards nobody asked about
    old, new = _asked(BOARD[0], "r-old", 30), _asked(BOARD[1], "r-new", 1)
    whole = sorted([*others, old, new], key=deck.order_key)
    assert [c.ref for c in deck.limited(whole, 3)] == [whole[0].ref, whole[1].ref, new.ref]
    assert deck.limited(whole, None) == whole  # Find your crew: every card, requested ones last
    assert deck.limited(whole[:3], 3) == whole[:3]  # fits: whole, in order
    plain = sorted(BOARD, key=deck.order_key)
    assert deck.limited(plain, 3) == plain[:3]  # nobody asked: the first three
    mid, older = _asked(BOARD[2], "r-mid", 5), _asked(BOARD[3], "r-4", 8)
    only_asked = sorted([old, new, mid, older], key=deck.order_key)
    # BLD-F096: nobody else to show, so the three latest requests, oldest first, the newest last
    assert [c.ref for c in deck.limited(only_asked, 3)] == [older.ref, mid.ref, new.ref]
    fits_asked = sorted([BOARD[2], old, new], key=deck.order_key)
    assert deck.limited(fits_asked, 3) == fits_asked  # a deck of three keeps both requested cards


def test_DEC_126_L_CREW_10_BLD_F096_a_short_read_fills_to_the_limit_with_the_latest_requested_cards() -> None:
    """BLD-F096 (amends BLD-F094): one other card and three requested ones at `limit=3` read three cards, not two:
    the other card, then the two latest requested cards in deck order, the most recently requested last."""
    other = BOARD[4]
    oldest, mid, newest = _asked(BOARD[0], "r-1", 30), _asked(BOARD[1], "r-2", 5), _asked(BOARD[2], "r-3", 1)
    whole = sorted([newest, other, oldest, mid], key=deck.order_key)
    assert [c.ref for c in whole] == [other.ref, oldest.ref, mid.ref, newest.ref]
    short = deck.limited(whole, 3)
    assert [c.ref for c in short] == [other.ref, mid.ref, newest.ref]
    assert short[-1].request == ("r-3", "teamup")  # the most recent request stays last
    # every read holds min(limit, deck) cards
    for limit in range(1, 6):
        assert len(deck.limited(whole, limit)) == min(limit, len(whole)), limit
    assert [c.ref for c in deck.limited(whole, 1)] == [newest.ref]  # a read of one: the latest request
    assert [c.ref for c in deck.limited(whole, 2)] == [other.ref, newest.ref]
    assert deck.limited(whole, 4) == whole and deck.limited(whole, None) == whole
