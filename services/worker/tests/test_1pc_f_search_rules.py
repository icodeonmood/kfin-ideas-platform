"""L-SEARCH's pure rules (lane F, BLD-F039 to BLD-F041): terms, scoring and snippets, the filters with live counts,
the sentences and the no-result state, and the "ask" seam. No database. Made-up text only."""

from __future__ import annotations

from typing import Any

from search import interpret, rules

SPECS = (
    rules.Facet(
        "list",
        "List",
        multi=False,
        order=("yours", "teamed"),
        labels={"yours": "Yours", "teamed": "Teamed up"},
    ),
    rules.Facet("area", "Category", multi=True, sort_by_label=True),
)
ROWS: list[dict[str, Any]] = [
    {"id": "a", "list": "yours", "area": "Operations"},
    {"id": "b", "list": "yours", "area": "Investor service"},
    {"id": "c", "list": "teamed", "area": "Investor service"},
    {"id": "d", "list": "teamed", "area": None},
]


def test_L_SEARCH_2_terms_are_telling_words_stemmed_with_references_whole() -> None:
    assert rules.terms("Which of my ideas are about Rejections?") == ["reject"]
    assert rules.terms("  SMS   codes for IDEA-2026-001412 ") == ["idea-2026-001412", "sms", "code"]
    assert rules.terms("the of") == ["the", "of"]  # only stop words: keep them
    assert rules.terms("") == [] and rules.terms(None) == []
    assert len(" ".join(rules.terms("x" * 500))) <= rules.QUERY_MAX


def test_L_SEARCH_2_title_outranks_summary_outranks_words_and_reasons() -> None:
    title = rules.score({"title": "Rejection codes confuse investors"}, "rejection")
    summary = rules.score(
        {"title": "Branch calls", "summary": "Investors call about a rejection."}, "rejection"
    )
    words = rules.score({"title": "Branch calls", "words": "They ask why it was rejected."}, "rejection")
    reason = rules.score(
        {"title": "Branch calls", "reasons": "Rejections are owned by another team."}, "rejection"
    )
    assert title and summary and words and reason
    assert title.score > summary.score > words.score > reason.score
    assert words.matched_on == ("words",) and reason.matched_on == ("reasons",)


def test_L_SEARCH_2_half_the_terms_must_be_found_and_words_match_at_their_start() -> None:
    fields = {"title": "Nominee updates bounce between two teams", "summary": "A change goes back and forth."}
    assert rules.score(fields, "nominee teams") is not None
    assert rules.score(fields, "nominee courier tracking") is None  # 1 of 3
    assert rules.score(fields, "ominee") is None  # not at a word's start
    assert rules.score(fields, "") is None


def test_L_SEARCH_2_a_reference_matches_whole() -> None:
    m = rules.score({"title": "SIP mandate", "reference": "IDEA-2026-001412"}, "idea-2026-001412")
    assert m is not None and m.matched_on == ("reference",)
    assert rules.score({"title": "SIP mandate", "reference": "IDEA-2026-001413"}, "IDEA-2026-001412") is None


def test_L_SEARCH_3_the_snippet_shows_the_matching_words_cut_at_words() -> None:
    long = (
        "Every morning the branch team prints the list, then checks each line by hand against the courier sheet, "
        "and only then do they see that the redemption form never reached the processing centre at all."
    )
    m = rules.score({"title": "Courier forms", "summary": long}, "redemption")
    assert m is not None
    assert "redemption" in m.snippet and m.snippet.startswith("…") and len(m.snippet) <= rules.SNIPPET_MAX + 2
    # Title-only match: the row's second line is the start of the short summary.
    t = rules.score({"title": "Redemption forms", "summary": "Short."}, "redemption")
    assert t is not None and t.snippet == "Short."


def test_L_SEARCH_3_a_whole_phrase_in_the_title_adds_to_the_score() -> None:
    a = rules.score({"title": "Rejection SMS codes confuse investors"}, "rejection sms")
    b = rules.score({"title": "SMS about every rejection"}, "rejection sms")
    assert a and b and a.score > b.score


def test_L_SEARCH_5_filters_normalise_and_count_live_given_the_others() -> None:
    active = rules.normalise({"list": ["teamed", "yours"], "area": ["Investor service", " ", "Investor service"],
                              "nope": ["x"]}, SPECS)  # fmt: skip
    assert active == {"list": ["yours"], "area": ["Investor service"]}  # single-value keeps the last
    assert rules.normalise({"list": "elsewhere"}, SPECS) == {}
    groups = {g["key"]: g for g in rules.facets(ROWS, active, SPECS)}
    assert [(o["value"], o["count"], o["active"]) for o in groups["list"]["options"]] == [
        ("yours", 1, True),
        ("teamed", 1, False),
    ]
    # Area counts within "yours"; alphabetical; a picked value keeps its own count.
    assert [(o["value"], o["count"]) for o in groups["area"]["options"]] == [
        ("Investor service", 1),
        ("Operations", 1),
    ]
    assert [r["id"] for r in ROWS if rules.matches(r, active)] == ["b"]
    assert rules.chips(active, SPECS) == [
        {"key": "list", "value": "yours", "label": "Yours"},
        {"key": "area", "value": "Investor service", "label": "Investor service"},
    ]


def test_L_SEARCH_5_a_picked_value_no_row_has_still_shows_at_zero() -> None:
    groups = {g["key"]: g for g in rules.facets(ROWS, {"area": ["Legal"]}, SPECS)}
    assert ("Legal", 0, True) in [(o["value"], o["count"], o["active"]) for o in groups["area"]["options"]]


def test_L_SEARCH_3_and_7_sentences_and_the_empty_state() -> None:
    assert rules.sentence("SMS", 2, 1, "Rejection SMS codes confuse investors") == (
        "Found 3 ideas about “SMS”: 2 of yours and 1 you teamed up on. Closest: “Rejection SMS codes confuse investors”."
    )
    assert rules.sentence("SMS", 1, 0, "A").startswith("Found 1 idea about")
    assert rules.sentence("SMS", 0, 0, None) == "Nothing found for “SMS”."
    assert rules.matched_line(["summary", "title"]) == "Matched on titles and short summaries."
    assert rules.matched_line(["reasons", "words", "title"]) == (
        "Matched on titles, your own words and the review desk’s reasons."
    )
    assert rules.matched_line([]) == ""
    assert rules.empty("SMS")["action"] == {"label": "Show all ideas", "op": "clear"}
    assert rules.empty("")["title"] == "No ideas match these filters."


def test_L_SEARCH_4_ask_in_your_own_words_is_a_seam_that_answers_none() -> None:
    assert interpret("Which of my ideas need me this week?") is None
