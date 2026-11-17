"""The review side's `/internal/*` routes end to end through the worker app (A-API.desk, .questions, .committee):
the token guard, JSON that encodes, the pack's error shape, and one journey from the desk to the committee."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from core.db import Conn
from tests import desk_fixtures as f
from tests import helpers

TOKEN = "lane-b-test-token-0123456789abcdef"
REASON = "A clear problem, a real number and a simple fix for the branch."


@pytest.fixture
def client(
    db: Conn, test_database: str, company_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    from core.config import get_settings

    monkeypatch.setenv("COMPANY_REPO_PATH", str(company_repo))
    monkeypatch.setenv("DATABASE_URL", helpers.db_url(test_database))
    monkeypatch.setenv("INTERNAL_API_TOKEN", TOKEN)
    get_settings.cache_clear()
    from api.app import app

    yield TestClient(app, headers={"X-Internal-Token": TOKEN})
    monkeypatch.undo()
    get_settings.cache_clear()


@pytest.fixture
def cast(db: Conn, client: TestClient) -> dict[str, Any]:
    kavya = f.person(db, "Kavya Menon")
    return {
        "kavya": kavya,
        "meera": f.person(db, "Meera Iyer", roles=("reviewer",)),
        "rohan": f.person(db, "Rohan Mehta", roles=("committee",)),
        "idea": f.idea(db, kavya),
    }


def test_the_token_guards_every_desk_route(client: TestClient) -> None:
    bare = TestClient(client.app)
    assert bare.get("/internal/desk", params={"user_id": "x"}).status_code == 401
    assert bare.post("/internal/committee/windows/x/extend", params={"user_id": "x"}).status_code == 401


def test_A_API_desk_from_the_queue_to_the_committee(client: TestClient, cast: dict[str, Any]) -> None:
    meera, rohan, ref = cast["meera"]["id"], cast["rohan"]["id"], cast["idea"]["idea_id"]
    q = client.get("/internal/desk", params={"user_id": meera, "tab": "to_review"})
    assert q.status_code == 200 and q.json()["counts"]["to_review"] == 1
    assert client.post(f"/internal/desk/ideas/{ref}/open", params={"user_id": meera}).json()["first"] is True
    page = client.get(f"/internal/desk/ideas/{ref}", params={"user_id": meera}).json()
    assert page["panel"]["state"] == "reviewing" and page["can_act"] is True
    assert (
        client.get(f"/internal/desk/ideas/{ref}/listen", params={"user_id": meera}).json()["parts"][0]["part"]
        == "summary"
    )
    bad = client.post(
        f"/internal/desk/ideas/{ref}/decision", params={"user_id": meera}, json={"choice": "pick"}
    )
    assert bad.status_code == 422
    assert bad.json() == {"error": {"code": "reason_too_short", "field": "reason",
                                    "message": "Give Kavya a reason of at least a line, 30 characters or more."}}  # fmt: skip
    sent = client.post(f"/internal/desk/ideas/{ref}/decision", params={"user_id": meera},
                       json={"choice": "pick", "reason": REASON})  # fmt: skip
    assert sent.status_code == 201 and sent.json()["label"] == "Picked"
    rows = client.get("/internal/committee", params={"user_id": rohan}).json()
    assert rows["counts"]["window"] == 1
    window = rows["items"][0]["window_id"]
    words = client.get(f"/internal/committee/windows/{window}/reversing", params={"user_id": rohan}).json()
    assert words["send_label"] == "Reverse and tell Kavya"
    ext = client.post(f"/internal/committee/windows/{window}/extend", params={"user_id": rohan})
    assert ext.status_code == 200 and ext.json()["window"]["extended"] == "Extended once"
    rev = client.post(f"/internal/committee/windows/{window}/reverse", params={"user_id": rohan},
                      json={"to": "not_picked", "note": "The SMS vendor is changing; this goes with the new one."})  # fmt: skip
    assert rev.status_code == 200 and rev.json()["reversal"]["to"] == "not_picked"
    again = client.post(f"/internal/committee/windows/{window}/extend", params={"user_id": rohan})
    assert again.status_code == 409 and again.json()["error"]["code"] == "already_reversed"
    decision = client.get(f"/internal/ideas/{ref}/decision", params={"user_id": cast["kavya"]["id"]}).json()
    assert decision["reversal"]["to"] == "not_picked"


def test_unknown_ideas_and_windows_are_not_found(client: TestClient, cast: dict[str, Any]) -> None:
    meera = cast["meera"]["id"]
    assert client.get("/internal/desk/ideas/IDEA-2026-999999", params={"user_id": meera}).status_code == 404
    assert (
        client.post("/internal/committee/windows/nope/extend", params={"user_id": meera}).status_code == 404
    )


def test_P_PRODUCT_privacy_the_reason_is_for_the_sharer_crew_desk_and_committee(
    db: Conn, client: TestClient, cast: dict[str, Any]
) -> None:
    ref = cast["idea"]["idea_id"]
    client.post(f"/internal/desk/ideas/{ref}/decision", params={"user_id": cast["meera"]["id"]},
                json={"choice": "pick", "reason": REASON})  # fmt: skip
    crew, stranger = f.person(db, "Farhan Nair"), f.person(db, "Sneha Kulkarni")
    f.crew(db, cast["idea"], crew)
    for reader in (cast["kavya"], crew, cast["meera"], cast["rohan"]):
        got = client.get(f"/internal/ideas/{ref}/decision", params={"user_id": reader["id"]}).json()
        assert got["decision"]["reason"] == REASON, reader["name"]
    got = client.get(f"/internal/ideas/{ref}/decision", params={"user_id": stranger["id"]}).json()
    assert got == {"stage_only": True, "decision": {"choice": "pick", "label": "Picked"}}


def test_L_QUESTIONS_answer_only_the_sharer_reaches_their_questions(
    db: Conn, client: TestClient, cast: dict[str, Any]
) -> None:
    """Anyone else gets 404, not 403, so the idea's questions are not confirmed to exist (lane A's review)."""
    ref = cast["idea"]["idea_id"]
    sent = client.post(f"/internal/desk/ideas/{ref}/question-sets", params={"user_id": cast["meera"]["id"]},
                       json={"questions": [{"part": "often", "text": "Is it 40 calls a day at one branch?"}],
                             "time_to_answer": "3d"})  # fmt: skip
    assert sent.status_code == 201, sent.text
    set_id = sent.json()["id"]
    question_id = sent.json()["questions"][0]["id"]
    stranger = f.person(db, "Sneha Kulkarni")
    who = {"user_id": stranger["id"]}
    assert client.get(f"/internal/ideas/{ref}/question-set", params=who).status_code == 404
    assert (
        client.put(
            f"/internal/questions/{question_id}/answer", params=who, json={"text": "Not mine"}
        ).status_code
        == 404
    )
    assert client.post(f"/internal/question-sets/{set_id}/send", params=who).status_code == 404
    mine = client.get(f"/internal/ideas/{ref}/question-set", params={"user_id": cast["kavya"]["id"]})
    assert mine.status_code == 200


def test_P_PRODUCT_privacy_admins_never_read_or_act_on_the_desk(
    db: Conn, client: TestClient, cast: dict[str, Any]
) -> None:
    """The web capabilities let admins reach the desk routes; the worker refuses them (DEC-104): the sharer's words,
    answers, the worth note and the decision's reason are for the sharer, crew, review desk and committee."""
    ref = cast["idea"]["idea_id"]
    admin = f.person(db, "Priya Iyer", roles=("admin",))
    core = f.person(db, "Anil Kapoor", roles=("core_committee",))
    who = {"user_id": admin["id"]}
    forbidden = {
        "error": {"code": "forbidden", "message": "Only the review desk and the Ones Committee can see this."}
    }
    for res in (
        client.get(f"/internal/desk/ideas/{ref}", params=who),
        client.get("/internal/desk", params=who),
        client.get(f"/internal/desk/ideas/{ref}/listen", params=who),
    ):
        assert (res.status_code, res.json()) == (403, forbidden)
    for res in (
        client.post(f"/internal/desk/ideas/{ref}/decision", params=who, json={"choice": "pick", "reason": REASON}),
        client.post(f"/internal/desk/ideas/{ref}/open", params=who),
        client.put(f"/internal/desk/ideas/{ref}/worth", params=who, json={"hours_month": "70"}),
        client.post(f"/internal/desk/ideas/{ref}/question-sets", params=who,
                    json={"questions": [{"part": "often", "text": "Is it 40 calls a day at one branch?"}]}),
        # the committee reads the desk but never acts on it
        client.post(f"/internal/desk/ideas/{ref}/decision", params={"user_id": cast["rohan"]["id"]},
                    json={"choice": "pick", "reason": REASON}),
    ):  # fmt: skip
        assert res.status_code == 403 and res.json()["error"]["code"] == "forbidden"
    assert db.execute("SELECT count(*) AS n FROM idea_decisions").fetchone() == {"n": 0}
    for reader in (cast["meera"], cast["rohan"], core):
        assert client.get(f"/internal/desk/ideas/{ref}", params={"user_id": reader["id"]}).status_code == 200
    assert client.get("/internal/desk", params={"user_id": "not-a-user"}).status_code == 403


def test_A_API_conventions_2_numbers_and_lists_in_a_body_answer_422_never_500(
    client: TestClient, cast: dict[str, Any]
) -> None:
    ref, meera, kavya = cast["idea"]["idea_id"], cast["meera"]["id"], cast["kavya"]["id"]
    sent = client.post(f"/internal/desk/ideas/{ref}/question-sets", params={"user_id": meera},
                       json={"questions": [{"part": "often", "text": "Is it 40 calls a day at one branch?"}]})  # fmt: skip
    question_id = sent.json()["questions"][0]["id"]
    bad = client.put(f"/internal/questions/{question_id}/answer", params={"user_id": kavya},
                     json={"text": "One branch.", "file_ids": 5})  # fmt: skip
    assert (bad.status_code, bad.json()["error"]["code"]) == (422, "file_not_found")
    for body, code in (
        ({"outside_tools": []}, "outside_tools_invalid"),
        ({"hours_month": 70}, "worth_invalid"),
    ):
        res = client.put(f"/internal/desk/ideas/{ref}/worth", params={"user_id": meera}, json=body)
        assert (res.status_code, res.json()["error"]["code"]) == (422, code)
