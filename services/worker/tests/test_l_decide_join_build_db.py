"""Ask to join the build team (L-DECIDE.rules/6, A-API POST /ideas/:id/join-build; DEC-111, BLD-B256), against the
database: who may ask (the sharer and the crew), when (after a Pick that stands, until the team is chosen), once per
person with one audit row, the decision payload's `join_build` for S-06 and the asks lane A shows on S-ADMIN.
J-REVIEW step 6 and J-TRACK step 7. Synthetic people only; lane A's `notify` is replaced by a recorder."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from core.db import Conn
from desk import committee, decide, join_build
from desk.store import Refused
from tests import desk_fixtures as f
from tests import helpers
from tests.desk_fixtures import clean_up_desk_rows  # noqa: F401 (autouse: removes what the helpers made)

DECIDED = f.at(16, 16, 58)  # Monday 16 November, 4:58 pm
REASON = "Picked. A clear problem, a real number and a simple fix for the branch."
NOTE = "The SMS templates are frozen until the platform upgrade in January, so a team picked now would wait."
TOKEN = "lane-b-test-token-join-build-0123456789"


@pytest.fixture
def repo(company_repo: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    from core.config import get_settings

    monkeypatch.setenv("COMPANY_REPO_PATH", str(company_repo))
    get_settings.cache_clear()
    yield company_repo
    monkeypatch.undo()
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def told(monkeypatch: pytest.MonkeyPatch) -> f.FakeNotify:
    return f.install_fake_notify(monkeypatch)


@pytest.fixture
def cast(db: Conn, repo: Path) -> dict[str, Any]:
    kavya, farhan = f.person(db, "Kavya Menon"), f.person(db, "Farhan Shaikh")
    idea = f.idea(db, kavya)
    f.crew(db, idea, farhan)
    return {
        "kavya": kavya, "farhan": farhan, "idea": idea,
        "nikhil": f.person(db, "Nikhil Das"),
        "meera": f.person(db, "Meera Iyer", roles=("reviewer",)),
        "rohan": f.person(db, "Rohan Mehta", roles=("committee",)),
    }  # fmt: skip


def _pick(db: Conn, cast: dict[str, Any]) -> dict[str, Any]:
    return decide.send(
        db, cast["idea"]["idea_id"], cast["meera"]["id"], {"choice": "pick", "reason": REASON}, DECIDED
    )


def _window(db: Conn, decision_id: str) -> str:
    row = db.execute("SELECT id FROM decision_windows WHERE decision_id = %s", (decision_id,)).fetchone()
    assert row is not None
    return str(row["id"])


def _asks(db: Conn, cast: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(r) for r in db.execute(
        "SELECT user_id::text AS user_id, asked_at FROM join_build_asks WHERE idea_uuid = %s ORDER BY asked_at",
        (cast["idea"]["id"],),
    ).fetchall()]  # fmt: skip


def _audits(db: Conn, cast: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(r) for r in db.execute(
        "SELECT actor, entity, before, after FROM audit_log WHERE action = 'idea.join_build_ask' AND entity = %s "
        "ORDER BY id",
        (f"idea:{cast['idea']['idea_id']}",),
    ).fetchall()]  # fmt: skip


def _refused(fn: Any, *args: Any) -> Refused:
    with pytest.raises(Refused) as exc:
        fn(*args)
    return exc.value


def _payload(db: Conn, cast: dict[str, Any], who: str) -> Any:
    got = committee.decision_for_viewer(db, cast["idea"]["idea_id"], cast[who]["id"], f.at(17, 9))
    assert got is not None
    return got.get("join_build", "absent")


def test_L_DECIDE_6_the_sharer_asks_after_a_pick_once_with_one_audit_row(
    db: Conn, cast: dict[str, Any]
) -> None:
    _pick(db, cast)
    got = join_build.ask(db, cast["idea"]["idea_id"], cast["kavya"]["id"], f.at(17, 9))
    assert dt.datetime.fromisoformat(got["asked_at"]) == f.at(17, 9)
    assert set(got) == {"asked_at"}
    assert [a["user_id"] for a in _asks(db, cast)] == [cast["kavya"]["id"]]
    audits = _audits(db, cast)
    assert len(audits) == 1
    assert audits[0]["actor"] == f"user:{cast['kavya']['id']}" and audits[0]["before"] is None
    assert set(audits[0]["after"]) == {"ask_id"}  # IDs only (non-negotiable 3)
    # a repeat later: the first ask's time, still one row and one audit row
    again = join_build.ask(db, cast["idea"]["idea_id"], cast["kavya"]["id"], f.at(18, 11))
    assert again == got
    assert len(_asks(db, cast)) == 1 and len(_audits(db, cast)) == 1


def test_L_DECIDE_6_a_crew_member_asks_and_an_outsider_is_refused(db: Conn, cast: dict[str, Any]) -> None:
    _pick(db, cast)
    join_build.ask(db, cast["idea"]["idea_id"], cast["farhan"]["id"], f.at(17, 9))
    for who in ("nikhil", "meera", "rohan"):  # the desk and the committee are not the sharer or crew
        got = _refused(join_build.ask, db, cast["idea"]["idea_id"], cast[who]["id"])
        assert (got.status, got.code) == (403, "forbidden")
    # a crew member who left is no longer crew
    db.execute(
        "UPDATE crew_members SET left_at = now(), left_how = 'left' WHERE idea_uuid = %s AND contributor_code = %s",
        (cast["idea"]["id"], cast["farhan"]["code"]),
    )
    got = _refused(join_build.ask, db, cast["idea"]["idea_id"], cast["farhan"]["id"])
    assert (got.status, got.code) == (403, "forbidden")
    assert [a["user_id"] for a in _asks(db, cast)] == [cast["farhan"]["id"]]
    assert len(_audits(db, cast)) == 1


def test_L_DECIDE_6_unknown_ideas_are_not_found(db: Conn, cast: dict[str, Any]) -> None:
    got = _refused(join_build.ask, db, "IDEA-2026-999999", cast["kavya"]["id"])
    assert (got.status, got.code) == (404, "not_found")


def test_L_DECIDE_6_before_a_pick_or_after_a_reversal_is_not_picked(db: Conn, cast: dict[str, Any]) -> None:
    got = _refused(join_build.ask, db, cast["idea"]["idea_id"], cast["kavya"]["id"])
    assert (got.status, got.code) == (409, "not_picked")
    assert got.message  # a line ready to show, never idea text
    d = _pick(db, cast)
    committee.reverse_window(db, _window(db, d["id"]), cast["rohan"]["id"],
                             {"to": "not_now", "note": NOTE, "return_in": "3m"}, f.at(17, 10))  # fmt: skip
    got = _refused(join_build.ask, db, cast["idea"]["idea_id"], cast["kavya"]["id"])
    assert (got.status, got.code) == (409, "not_picked")
    assert _asks(db, cast) == [] and _audits(db, cast) == []


def test_L_DECIDE_6_a_not_now_or_not_picked_is_not_picked(db: Conn, cast: dict[str, Any]) -> None:
    decide.send(db, cast["idea"]["idea_id"], cast["meera"]["id"],
                {"choice": "not_picked", "reason": REASON}, DECIDED)  # fmt: skip
    got = _refused(join_build.ask, db, cast["idea"]["idea_id"], cast["kavya"]["id"])
    assert (got.status, got.code) == (409, "not_picked")
    assert _payload(db, cast, "kavya")["can_ask"] is False


def test_L_DECIDE_6_a_committee_reversal_to_pick_opens_asking(db: Conn, cast: dict[str, Any]) -> None:
    """L-COMMITTEE.rules/3: the new choice takes its consequences, so a reversal to Pick stands as a Pick."""
    d = decide.send(db, cast["idea"]["idea_id"], cast["meera"]["id"],
                    {"choice": "not_picked", "reason": REASON}, DECIDED)  # fmt: skip
    committee.reverse_window(db, _window(db, d["id"]), cast["rohan"]["id"], {"to": "pick", "note": NOTE},
                             f.at(17, 10))  # fmt: skip
    assert _payload(db, cast, "kavya")["can_ask"] is True
    join_build.ask(db, cast["idea"]["idea_id"], cast["kavya"]["id"], f.at(17, 11))
    assert len(_asks(db, cast)) == 1


def test_L_DECIDE_6_once_the_team_is_chosen_it_is_team_chosen(db: Conn, cast: dict[str, Any]) -> None:
    _pick(db, cast)
    join_build.ask(db, cast["idea"]["idea_id"], cast["kavya"]["id"], f.at(17, 9))
    db.execute(
        "INSERT INTO build_teams (idea_uuid, name) VALUES (%s, 'Branch messages')", (cast["idea"]["id"],)
    )
    for who in ("kavya", "farhan"):  # a repeat is refused too: the ask was made, asking is closed
        got = _refused(join_build.ask, db, cast["idea"]["idea_id"], cast[who]["id"])
        assert (got.status, got.code) == (409, "team_chosen")
    farhan = _payload(db, cast, "farhan")
    assert (farhan["can_ask"], farhan["asked_at"]) == (False, None) and farhan["reply_by"] is not None
    assert _payload(db, cast, "kavya")["asked_at"] is not None  # her ask stays on her page
    assert len(_asks(db, cast)) == 1 and len(_audits(db, cast)) == 1


def test_L_DECIDE_6_the_decision_payload_join_build_for_the_sharer_before_and_after_asking(
    db: Conn, cast: dict[str, Any]
) -> None:
    d = _pick(db, cast)
    team_by = db.execute("SELECT team_by FROM idea_decisions WHERE id = %s", (d["id"],)).fetchone()
    assert team_by is not None and team_by["team_by"] is not None
    stored = team_by["team_by"]
    # the date the Pick set, as the decision stored it
    assert dt.datetime.fromisoformat(d["team_by"]) == stored
    before = _payload(db, cast, "kavya")
    assert set(before) == {"can_ask", "asked_at", "reply_by"}
    assert (before["can_ask"], before["asked_at"]) == (True, None)
    assert dt.datetime.fromisoformat(before["reply_by"]) == stored
    asked = join_build.ask(db, cast["idea"]["idea_id"], cast["kavya"]["id"], f.at(17, 9))
    after = _payload(db, cast, "kavya")
    assert (after["can_ask"], after["asked_at"], after["reply_by"]) == (
        False,
        asked["asked_at"],
        before["reply_by"],
    )
    assert dt.datetime.fromisoformat(after["asked_at"]) == f.at(17, 9)
    # the crew reads its own: Farhan has not asked
    assert _payload(db, cast, "farhan") == {"can_ask": True, "asked_at": None, "reply_by": before["reply_by"]}
    # null for anyone else: the desk and the committee read the decision but are not the sharer or crew
    for who in ("meera", "rohan"):
        assert _payload(db, cast, who) is None
    # an outsider reads the stage only, with no join_build at all
    assert committee.decision_for_viewer(db, cast["idea"]["idea_id"], cast["nikhil"]["id"], f.at(17, 9)) == {
        "stage_only": True, "decision": {"choice": "pick", "label": "Picked"},
    }  # fmt: skip


def test_L_DECIDE_6_join_build_has_no_reply_by_without_a_pick_date(db: Conn, cast: dict[str, Any]) -> None:
    decide.send(db, cast["idea"]["idea_id"], cast["meera"]["id"],
                {"choice": "not_now", "reason": REASON, "return_in": "3m"}, DECIDED)  # fmt: skip
    assert _payload(db, cast, "kavya") == {"can_ask": False, "asked_at": None, "reply_by": None}


def test_L_DECIDE_6_asks_for_idea_oldest_first(db: Conn, cast: dict[str, Any]) -> None:
    _pick(db, cast)
    join_build.ask(db, cast["idea"]["idea_id"], cast["kavya"]["id"], f.at(17, 9))
    # Farhan asks after Kavya, with an earlier time: the list follows asked_at
    join_build.ask(db, cast["idea"]["idea_id"], cast["farhan"]["id"], f.at(17, 8))
    got = join_build.asks_for_idea(db, str(cast["idea"]["id"]))
    assert [(a["user_id"], a["name"]) for a in got] == [
        (cast["farhan"]["id"], "Farhan Shaikh"), (cast["kavya"]["id"], "Kavya Menon"),
    ]  # fmt: skip
    assert [dt.datetime.fromisoformat(a["asked_at"]) for a in got] == [f.at(17, 8), f.at(17, 9)]
    assert all(set(a) == {"user_id", "name", "asked_at"} for a in got)
    assert join_build.asks_for_idea(db, str(f.idea(db, cast["nikhil"])["id"])) == []


def test_L_DECIDE_6_on_an_idea_a_pick_joined_the_ask_goes_to_the_lead(db: Conn, cast: dict[str, Any]) -> None:
    """L-MERGE.desk/5: the joined idea's page shows the lead's Pick; its sharer asks to join the one build team."""
    ravi = f.person(db, "Ravi Nair")
    ravis = f.idea(db, ravi, title="Rejection SMS codes confuse investors", shared_at=f.at(15, 9))
    decide.send(db, cast["idea"]["idea_id"], cast["meera"]["id"],
                {"choice": "pick", "reason": REASON, "joined_with": ravis["idea_id"]}, DECIDED)  # fmt: skip
    seen = committee.decision_for_viewer(db, ravis["idea_id"], ravi["id"], f.at(17, 9))
    assert seen is not None and seen["joined_into"] == cast["idea"]["idea_id"]
    assert seen["join_build"]["can_ask"] is True
    join_build.ask(db, ravis["idea_id"], ravi["id"], f.at(17, 9))
    assert [a["user_id"] for a in _asks(db, cast)] == [ravi["id"]]  # stored on the lead
    after = committee.decision_for_viewer(db, ravis["idea_id"], ravi["id"], f.at(17, 10))
    assert after is not None and after["join_build"]["can_ask"] is False and after["join_build"]["asked_at"]


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


def test_L_DECIDE_6_the_worker_route_answers_in_the_packs_shape(
    db: Conn, cast: dict[str, Any], client: TestClient
) -> None:
    ref = cast["idea"]["idea_id"]
    url = f"/internal/ideas/{ref}/join-build"
    res = client.post(url, params={"user_id": cast["kavya"]["id"]})
    assert res.status_code == 409 and res.json()["error"]["code"] == "not_picked"
    _pick(db, cast)
    res = client.post(url, params={"user_id": cast["kavya"]["id"]})
    assert res.status_code == 200 and set(res.json()) == {"asked_at"}
    assert res.headers["Cache-Control"] == "no-store"
    assert client.post(url, params={"user_id": cast["kavya"]["id"]}).json() == res.json()
    res = client.post(url, params={"user_id": cast["nikhil"]["id"]})
    assert res.status_code == 403 and res.json()["error"]["code"] == "forbidden"
    res = client.post("/internal/ideas/IDEA-2026-999999/join-build", params={"user_id": cast["kavya"]["id"]})
    assert res.status_code == 404 and res.json()["error"]["code"] == "not_found"
    res = client.post(url, params={"user_id": "not-a-user"})
    assert res.status_code == 403
    assert TestClient(client.app).post(url, params={"user_id": cast["kavya"]["id"]}).status_code == 401
    body = client.get(f"/internal/ideas/{ref}/decision", params={"user_id": cast["kavya"]["id"]}).json()
    assert body["join_build"]["can_ask"] is False and body["join_build"]["reply_by"]
    assert dt.datetime.fromisoformat(body["join_build"]["asked_at"]) == _asks(db, cast)[0]["asked_at"]
