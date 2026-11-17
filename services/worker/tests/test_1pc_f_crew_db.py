"""Find your crew against a migrated database (L-CREW/1–10, A-API.team-up `GET /crew` and the passes): who sees
which card and why, in what order, the filters, passing every card to the end of the deck and back (V-ACC.teamup/8),
"Your crews", Home's top three, and the `/internal` routes."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from core.db import Conn
from crew import deck
from tests import helpers
from tests import lane_f_fixtures as f

NOW = f.NOW


@pytest.fixture
def world(db: Conn) -> dict[str, Any]:
    """Leela (Investor service, Hyderabad) and colleagues' ideas that reach her for each of the four reasons, plus
    ideas she must never see on the deck."""
    leela = f.person(db, "Leela Sharma", city="Hyderabad", area="Investor service")
    omkar = f.person(db, "Omkar Joshi", city="Mumbai", area="Operations")
    ritu = f.person(db, "Ritu Bansal", city="Chennai", area="Investor service")
    vikram = f.person(db, "Vikram Sethi", city="Pune", area="Operations")
    pooja = f.person(db, "Pooja Gill", city="Hyderabad", area="Operations")
    tarun = f.person(db, "Tarun Mehra", city="Kolkata", area="Sales")
    mine = f.idea(db, leela, "Rejection SMS shows a code, not a reason", area="Investor service", city="Hyderabad",
                  shared_days=3)  # Saturday  # fmt: skip
    close = f.idea(db, omkar, "Rejection codes confuse investors at the counter", status="picked", shared_days=2,
                   helpers=("Branch staff",), helper_text="Someone who takes these calls at a branch every day.")  # fmt: skip
    f.link(db, mine, close, strength="close", reason="Close match: same R07 SMS")
    for who in (ritu, vikram, pooja):
        f.join(db, close, who)
    touch = f.idea(db, vikram, "Nominee updates bounce between two teams", area="Operations", city="Pune",
                   shared_days=4, helpers=("Investor service",))  # fmt: skip
    area = f.idea(db, ritu, "Branch queue times are not tracked anywhere", area="Investor service", city="Chennai",
                  shared_days=1, summary="We can't tell how long investors wait. So we can't staff for it.")  # fmt: skip
    office = f.idea(db, pooja, "Same KYC details typed into three screens", status="checking", area="Operations",
                    city="Hyderabad", shared_days=0.5, helpers=("Operations",))  # fmt: skip
    # Never on Leela's deck: no reason, closed, shipped, a draft, and her own.
    f.idea(db, tarun, "Sales targets sheet is emailed weekly", area="Sales", city="Kolkata")
    f.idea(db, pooja, "Old idea that was not picked", status="not_picked", area="Investor service", city="Hyderabad")
    f.idea(db, pooja, "Shipped already", status="shipped", area="Investor service", city="Hyderabad")
    f.idea(db, ritu, "A draft in her area", area="Investor service", shared_days=None)
    return {"leela": leela, "omkar": omkar, "ritu": ritu, "vikram": vikram, "pooja": pooja, "tarun": tarun,
            "mine": mine, "close": close, "touch": touch, "area": area, "office": office}  # fmt: skip


def _ids(body: dict[str, Any]) -> list[str]:
    return [c["id"] for c in body["items"]]


def test_L_CREW_1_to_3_one_reason_per_card_strongest_first(db: Conn, world: dict[str, Any]) -> None:
    body = deck.deck(db, world["leela"]["id"], now=NOW)
    w = world
    assert _ids(body) == [w["close"]["idea_id"], w["touch"]["idea_id"], w["area"]["idea_id"], w["office"]["idea_id"]]
    assert [(c["reason_kind"], c["reason"]) for c in body["items"]] == [
        ("close_to_yours", "Same R07 SMS as your idea from Saturday"),
        ("touches_your_work", "They need someone in Investor service"),
        ("same_area", "Your area, Investor service"),
        ("same_office", "Same office as you, Hyderabad"),
    ]
    assert body["total"] == body["deck_total"] == 4 and body["state"] == "cards"


def test_L_CREW_3_newer_first_within_a_reason(db: Conn, world: dict[str, Any]) -> None:
    newer = f.idea(db, world["tarun"], "Investors queue twice for KYC", area="Investor service", city="Kolkata",
                   shared_days=0.2)  # fmt: skip
    ids = _ids(deck.deck(db, world["leela"]["id"], now=NOW))
    assert ids.index(newer["idea_id"]) == ids.index(world["area"]["idea_id"]) - 1


def test_L_CREW_4_every_card_field(db: Conn, world: dict[str, Any]) -> None:
    card = deck.deck(db, world["leela"]["id"], now=NOW)["items"][0]
    assert card["status"] == "picked" and card["title"] == "Rejection codes confuse investors at the counter"
    assert (card["area"], card["city"]) == ("Operations", "Mumbai")
    assert card["in_their_words"] == "Branches hear the same question every day."
    assert card["looking_for"] == "Someone who takes these calls at a branch every day."
    assert card["lead"]["name"] == "Omkar Joshi" and card["lead"]["initials"] == "OJ"
    assert card["crew_count"] == 4 and [p["initials"] for p in card["crew_faces"]] == ["OJ", "RB", "VS"]
    assert card["hue"] in (1, 2) and card["shared_at"].startswith("2026-11-15")
    office = deck.deck(db, world["leela"]["id"], now=NOW)["items"][3]
    assert office["status"] == "checking" and office["looking_for"] == "Operations"
    area = deck.deck(db, world["leela"]["id"], now=NOW)["items"][2]
    assert "looking_for" not in area  # no answer and no picks: left out (BLD-F031)


def test_L_CREW_1_not_on_not_asked_not_passed(db: Conn, world: dict[str, Any]) -> None:
    w = world
    leela = w["leela"]
    f.join(db, w["close"], leela)
    f.request(db, w["touch"], leela)
    f.request(db, w["office"], leela, state="withdrawn")  # withdrawn: may ask again, so it stays
    deck.pass_idea(db, leela["id"], w["area"]["idea_id"])
    assert _ids(deck.deck(db, leela["id"], now=NOW)) == [w["office"]["idea_id"]]
    f.request(db, w["office"], leela, state="declined")
    body = deck.deck(db, leela["id"], now=NOW)
    assert body["items"] == [] and body["state"] == "everyone_seen"
    assert (body["joined"], body["pending"], body["passed"], body["asked"]) == (1, 1, 1, 2)


def test_L_CREW_5_filters_with_live_counts_and_chips(db: Conn, world: dict[str, Any]) -> None:
    body = deck.deck(db, world["leela"]["id"], {"location": ["Hyderabad"], "colour": ["red"]}, now=NOW)
    assert _ids(body) == [world["office"]["idea_id"]] and body["total"] == 1 and body["deck_total"] == 4
    assert body["active"] == [{"key": "location", "value": "Hyderabad", "label": "Hyderabad"}]
    groups = {g["key"]: g for g in body["filters"]}
    assert [g["label"] for g in body["filters"]] == ["Location", "Category", "Idea status", "Team size", "Looking for"]
    assert {o["value"]: o["count"] for o in groups["location"]["options"]} == {
        "Mumbai": 1, "Pune": 1, "Chennai": 1, "Hyderabad": 1,
    }  # fmt: skip
    assert {o["label"]: o["count"] for o in groups["team_size"]["options"]} == {
        "Just the lead": 1, "2 to 3 people": 0, "4 or more": 0,
    }  # fmt: skip
    assert body["counts"]["location:Mumbai"] == 1 and body["counts"]["status:checking"] == 1
    both = deck.deck(db, world["leela"]["id"], {"category": ["Operations"], "team_size": ["four_plus"]}, now=NOW)
    assert _ids(both) == [world["close"]["idea_id"]]


def test_V_ACC_teamup_8_pass_every_card_then_undo_last_then_reset(db: Conn, world: dict[str, Any]) -> None:
    leela = world["leela"]["id"]
    f.request(db, world["touch"], world["leela"])  # she asked on one card, then passes the rest
    ids = _ids(deck.deck(db, leela, now=NOW))
    for ref in ids:
        out = deck.pass_idea(db, leela, ref)
        assert out["last_passed"] == ref
    assert deck.pass_idea(db, leela, ids[-1])["passed"] == len(ids)  # passing twice changes nothing
    end = deck.deck(db, leela, now=NOW)
    # "That's everyone for now. You asked to team up on 1 idea." … "3 passed" with "Undo last pass".
    assert end["state"] == "everyone_seen" and end["items"] == []
    assert (end["asked"], end["passed"], end["last_passed"]) == (1, 3, ids[-1])
    undo = deck.undo_last(db, leela, now=NOW)
    assert undo["restored"] == ids[-1] and undo["card"]["id"] == ids[-1] and undo["passed"] == 2
    assert undo["last_passed"] == ids[-2]
    assert _ids(deck.deck(db, leela, now=NOW)) == [ids[-1]]
    again = deck.reset(db, leela)
    assert again == {"reset": 2, "passed": 0, "last_passed": None}
    assert _ids(deck.deck(db, leela, now=NOW)) == ids
    assert deck.undo_last(db, leela, now=NOW) == {"restored": None, "card": None, "passed": 0, "last_passed": None}


def test_L_CREW_6_only_a_colleagues_shared_idea_can_be_passed(db: Conn, world: dict[str, Any]) -> None:
    from crew.store import Refused

    leela = world["leela"]["id"]
    for bad in ("IDEA-2026-999999", world["mine"]["idea_id"]):
        with pytest.raises(Refused) as e:
            deck.pass_idea(db, leela, bad)
        assert e.value.status == 404
    with pytest.raises(Refused) as e:
        deck.pass_idea(db, leela, None)
    assert e.value.code == "idea_required" and e.value.field == "idea_id"


def test_L_CREW_8_nothing_yet_for_someone_new_with_nothing_near(db: Conn, world: dict[str, Any]) -> None:
    newcomer = f.person(db, "Kiran Dsouza", city="Jaipur", area="Legal", code=False)
    body = deck.deck(db, newcomer["id"], now=NOW)
    assert body["state"] == "nothing_yet" and body["items"] == [] and body["your_crews"]["items"] == []
    assert (body["joined"], body["pending"], body["passed"], body["asked"]) == (0, 0, 0, 0)


def test_L_CREW_9_your_crews_waiting_and_on_the_crew(db: Conn, world: dict[str, Any]) -> None:
    w = world
    f.join(db, w["close"], w["leela"], days=2)
    f.request(db, w["touch"], w["leela"], days=0.5)
    crews = deck.deck(db, w["leela"]["id"], now=NOW)["your_crews"]
    assert crews["teamed_link"] == "/my-ideas?list=teamed"
    assert [(i["id"], i["state"], i["label"]) for i in crews["items"]] == [
        (w["touch"]["idea_id"], "waiting", "Waiting for Vikram"),
        (w["close"]["idea_id"], "on_crew", "On the crew"),
    ]
    assert crews["items"][0]["lead"]["area"] == "Operations" and crews["items"][0]["request_id"]


def test_L_CREW_10_home_shows_the_top_three(db: Conn, world: dict[str, Any]) -> None:
    top = deck.home(db, world["leela"]["id"], now=NOW)
    assert top["total"] == 4 and [c["id"] for c in top["top"]] == _ids(deck.deck(db, world["leela"]["id"], now=NOW))[:3]


def test_L_CREW_2_close_to_yours_from_a_newer_idea_that_matched_hers(db: Conn, world: dict[str, Any]) -> None:
    w = world
    later = f.idea(db, w["tarun"], "SMS codes again", area="Sales", city="Kolkata", shared_days=0.1)
    f.link(db, later, w["mine"], strength="related", reason="Related: the calls you describe")
    cards = deck.deck(db, w["leela"]["id"], now=NOW)["items"]
    assert [c["id"] for c in cards][:2] == [w["close"]["idea_id"], later["idea_id"]]
    assert cards[1]["reason"] == "Close to your idea from Saturday"


@pytest.fixture
def client(db: Conn, test_database: str, company_repo: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    from core.config import get_settings

    monkeypatch.setenv("COMPANY_REPO_PATH", str(company_repo))
    monkeypatch.setenv("DATABASE_URL", helpers.db_url(test_database))
    monkeypatch.setenv("INTERNAL_API_TOKEN", "lane-f-test-token-0123456789abcdef")
    get_settings.cache_clear()
    from api.app import app

    yield TestClient(app, headers={"X-Internal-Token": "lane-f-test-token-0123456789abcdef"})
    monkeypatch.undo()
    get_settings.cache_clear()


def test_A_API_team_up_crew_routes(client: TestClient, world: dict[str, Any]) -> None:
    leela = world["leela"]["id"]
    assert TestClient(client.app).get("/internal/crew", params={"user_id": leela}).status_code == 401
    body = client.get("/internal/crew", params=[("user_id", leela), ("location", "Hyderabad"),
                                                ("location", "Mumbai")]).json()  # fmt: skip
    assert body["total"] == 2 and [a["value"] for a in body["active"]] == ["Hyderabad", "Mumbai"]
    home = client.get("/internal/crew", params={"user_id": leela, "limit": 3}).json()
    assert len(home["items"]) == 3 and home["total"] == 4
    ref = home["items"][0]["id"]
    assert client.post("/internal/crew/pass", params={"user_id": leela}, json={"idea_id": ref}).json()["passed"] == 1
    assert client.post("/internal/crew/pass/undo", params={"user_id": leela}).json()["restored"] == ref
    assert client.post("/internal/crew/pass/reset", params={"user_id": leela}).json()["passed"] == 0
    bad = client.post("/internal/crew/pass", params={"user_id": leela}, json={})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "idea_required"
    assert client.get("/internal/crew", params={"user_id": "not-a-uuid"}).status_code == 404
    assert client.get("/internal/crew", params={"user_id": leela, "limit": 0}).status_code == 422
