"""DEC-110 (BLD-A219): a search's words are in no URL, the worker's own included. My ideas (S-07) and the review desk
(S-R1) read a search from a POST body; their GET routes no longer read a `q`, so nothing can send one there. The
links My ideas builds (tabs, filters, sorts, Copy link, Clear, a row's `back=`) never carry the search. No database:
the routes' connection and reads are stand-ins that record what they were asked. Synthetic words only."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ideapage import mine

WORDS = "Zebra7Kestrel rejection SMS"


@contextmanager
def _no_db(*_args: Any, **_kwargs: Any) -> Iterator[object]:
    yield object()


@pytest.fixture
def asked(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[dict[str, Any]]]:
    import desk.reads
    import desk.routes
    import ideapage.routes

    calls: list[dict[str, Any]] = []

    def fake_mine(_conn: object, user_id: str, params: dict[str, Any], **kw: Any) -> dict[str, Any]:
        calls.append({"route": "my-ideas", "user_id": user_id, "params": params, **kw})
        return {"ok": True}

    def fake_desk(_conn: object, user_id: str, tab: str, sort: str, q: str | None) -> dict[str, Any]:
        calls.append({"route": "desk", "user_id": user_id, "tab": tab, "sort": sort, "q": q})
        return {"ok": True}

    monkeypatch.setattr(ideapage.routes, "connect", _no_db)
    monkeypatch.setattr(desk.routes, "connect", _no_db)
    monkeypatch.setattr(desk.routes, "require_role", lambda *_a, **_k: None)
    monkeypatch.setattr(mine, "my_ideas", fake_mine)
    monkeypatch.setattr(desk.reads, "desk", fake_desk)
    yield calls


@pytest.fixture
def client() -> TestClient:
    import desk.routes
    import ideapage.routes

    app = FastAPI()
    app.include_router(ideapage.routes.build(lambda: None))
    app.include_router(desk.routes.build(lambda: None))
    return TestClient(app)


def test_DEC_110_S_07_my_ideas_reads_the_search_from_a_post_body(
    client: TestClient, asked: list[Any]
) -> None:
    res = client.post(
        "/internal/me/u-1/my-ideas",
        json={"list": "teamed", "sort": "stage", "q": WORDS, "row": "IDEA-2026-000002", "filter": 7},
    )
    assert res.status_code == 200
    assert asked[-1]["params"] == {
        "list": "teamed",
        "filter": None,
        "sort": "stage",
        "q": WORDS,
        "row": "IDEA-2026-000002",
    }


def test_DEC_110_S_07_my_ideas_get_never_reads_a_q(client: TestClient, asked: list[Any]) -> None:
    assert client.get("/internal/me/u-1/my-ideas", params={"sort": "shared", "q": WORDS}).status_code == 200
    assert "q" not in asked[-1]["params"]
    assert asked[-1]["params"]["sort"] == "shared"


def test_DEC_110_S_R1_desk_reads_the_search_from_a_post_body_capped_at_200(
    client: TestClient, asked: list[Any]
) -> None:
    res = client.post(
        "/internal/desk", params={"user_id": "u-2"}, json={"tab": "to_review", "sort": "area", "q": "x" * 250}
    )
    assert res.status_code == 200
    assert asked[-1] == {
        "route": "desk",
        "user_id": "u-2",
        "tab": "to_review",
        "sort": "area",
        "q": "x" * 200,
    }
    client.post("/internal/desk", params={"user_id": "u-2"}, json={"tab": 3, "q": ["no"]})
    assert asked[-1]["tab"] == "waiting" and asked[-1]["sort"] == "time_left" and asked[-1]["q"] is None


def test_DEC_110_S_R1_desk_get_never_reads_a_q(client: TestClient, asked: list[Any]) -> None:
    client.get("/internal/desk", params={"user_id": "u-2", "tab": "decided", "q": WORDS})
    assert asked[-1]["tab"] == "decided" and asked[-1]["q"] is None


def test_DEC_110_S_07_no_link_my_ideas_builds_carries_the_search() -> None:
    state = mine.normalise({"list": "teamed", "filter": "closed", "sort": "stage", "q": WORDS, "row": "R9"})
    assert state["q"] == WORDS
    assert mine.query_of(state) == "list=teamed&filter=closed&sort=stage&row=R9"
    assert mine.url_of(state, row=None) == "/my-ideas?list=teamed&filter=closed&sort=stage"
    assert (
        mine.url_of({**state, "list": "yours", "filter": "all", "sort": "latest", "row": None}) == "/my-ideas"
    )
    assert "Zebra7Kestrel" not in mine.url_of(state, filter="all")
