"""L-SEARCH against a migrated database (lane F, BLD-F039 to BLD-F041): the scope is the person's own list
(L-SEARCH/1), what is searched and what never is (L-SEARCH/2: their own words only for their own ideas, the review
desk's reason as they read it, never another person's words), the sentences (L-SEARCH/3), the filters with live
counts (L-SEARCH/5) and the no-result state (L-SEARCH/7). Synthetic people and made-up text only. CI runs these;
each test removes what it made."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from core.db import Conn
from crew.store import Refused
from search import search
from tests import lane_f_fixtures as f


@pytest.fixture
def db(db: Conn) -> Iterator[Conn]:
    yield db
    f.clean(db)


@pytest.fixture
def world(db: Conn) -> dict[str, Any]:
    leela = f.person(db, "Leela Sharma")
    omkar = f.person(db, "Omkar Joshi", city="Mumbai", area="Operations")
    desk = f.person(db, "Devika Rao", roles=("reviewer",))
    mine = f.idea(db, leela, "Rejection SMS shows a code, not a reason", area="Investor service",
                  summary="Investors get a code and call the branch to ask what it means.")  # fmt: skip
    f.message(db, mine, "Every morning the counter hears about R07 from walk-in investors.")
    old = f.idea(db, leela, "Courier slips go missing", status="not_picked", area="Operations",
                 summary="Forms sent to the processing centre have no tracking.")  # fmt: skip
    f.decision(
        db, old, desk, "not_picked", "Courier tracking is already being replaced by the scanning project."
    )
    draft = f.idea(db, leela, "Nominee forms bounce twice", shared_days=None)
    theirs = f.idea(db, omkar, "Redemption rejections need plain words", area="Operations", shared_days=4,
                    summary="Agents explain each rejection differently.")  # fmt: skip
    f.message(db, theirs, "Omkar's own words about R07 and the counter.")
    f.join(db, theirs, leela)
    stranger = f.idea(db, omkar, "Rejection letters are printed twice", area="Operations")
    return {"leela": leela, "omkar": omkar, "mine": mine, "old": old, "draft": draft, "theirs": theirs,
            "stranger": stranger}  # fmt: skip


def _ids(body: dict[str, Any]) -> list[str]:
    return [i["uuid"] for i in body["items"]]


def test_L_SEARCH_1_scope_is_the_persons_own_list_and_teamed_ideas(db: Conn, world: dict[str, Any]) -> None:
    w = world
    every = search(db, w["leela"]["id"], "")
    assert set(_ids(every)) == {str(w[k]["id"]) for k in ("mine", "old", "draft", "theirs")}
    assert str(w["stranger"]["id"]) not in _ids(search(db, w["leela"]["id"], "rejection"))
    lists = {i["uuid"]: i["list"] for i in every["items"]}
    assert lists[str(w["theirs"]["id"])] == "teamed" and lists[str(w["mine"]["id"])] == "yours"
    assert every["interpreted"] is None and "search" not in every


def test_L_SEARCH_2_own_words_for_own_ideas_only_and_the_reason_they_read(
    db: Conn, world: dict[str, Any]
) -> None:
    w = world
    body = search(db, w["leela"]["id"], "R07 counter")
    assert _ids(body) == [str(w["mine"]["id"])]  # Omkar's words on the teamed idea are never searched
    assert body["items"][0]["matched_on"] == ["words"] and "R07" in body["items"][0]["snippet"]
    by_reason = search(db, w["leela"]["id"], "scanning project")
    assert _ids(by_reason) == [str(w["old"]["id"])] and by_reason["items"][0]["matched_on"] == ["reasons"]


def test_L_SEARCH_3_sentences_closest_first(db: Conn, world: dict[str, Any]) -> None:
    w = world
    body = search(db, w["leela"]["id"], "rejection")
    assert _ids(body)[0] == str(w["mine"]["id"])  # in the title of hers; the teamed one too
    assert set(_ids(body)) == {str(w["mine"]["id"]), str(w["theirs"]["id"])}
    s = body["search"]
    assert s["sentence"] == (
        "Found 2 ideas about “rejection”: 1 of yours and 1 you teamed up on. "
        "Closest: “Rejection SMS shows a code, not a reason”."
    )
    assert s["matched_line"].startswith("Matched on titles")
    assert s["closest"]["id"] == w["mine"]["idea_id"]


def test_L_SEARCH_5_filters_with_live_counts(db: Conn, world: dict[str, Any]) -> None:
    w = world
    body = search(db, w["leela"]["id"], "rejection", {"list": ["teamed"]})
    assert _ids(body) == [str(w["theirs"]["id"])]
    groups = {g["key"]: g for g in body["filters"]}
    assert {o["value"]: o["count"] for o in groups["list"]["options"]} == {"yours": 1, "teamed": 1}
    assert body["active"] == [{"key": "list", "value": "teamed", "label": "Teamed up"}]
    drafts = search(db, w["leela"]["id"], "", {"filter": "drafts"})
    assert _ids(drafts) == [str(w["draft"]["id"])] and drafts["counts"]["filter:closed"] == 1


def test_L_SEARCH_7_no_result_offers_show_all(db: Conn, world: dict[str, Any]) -> None:
    body = search(db, world["leela"]["id"], "dividend warrant")
    assert body["items"] == [] and body["search"]["sentence"] == "Nothing found for “dividend warrant”."
    assert body["empty"]["action"]["label"] == "Show all ideas"


def test_L_SEARCH_1_someone_with_nothing_shared_and_someone_unknown(db: Conn, world: dict[str, Any]) -> None:
    new = f.person(db, "Kiran Dsouza", code=False)
    assert search(db, new["id"], "anything")["items"] == []
    with pytest.raises(Refused):
        search(db, "not-a-uuid", "x")
