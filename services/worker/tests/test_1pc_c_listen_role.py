"""Listen in Sarvam's voice is for the review desk and the Ones Committee only (BLD-C198; P-PRODUCT.privacy, DEC-104;
L-LISTEN, DEC-108 (4)). The web app's `view_review_queue` also lets admins in, so the worker's two listen routes check
the signed-in person (`user_id`) against desk.store.READERS before they read anything, as every other desk read does.
Synthetic people only; no audio is made in these tests."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from fastapi.testclient import TestClient

import api.app as app_module
from core.config import get_settings
from core.db import connect
from desk.store import READERS
from speech import listen
from tests import helpers

IDEA = "11111111-2222-4333-8444-555555555555"
TOKEN = {"X-Internal-Token": "t" * 32}
ROUTES = (f"/internal/listen/{IDEA}", f"/internal/listen/{IDEA}/chapters")


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("SPEECH_MODE", "fake")
    monkeypatch.setenv("INTERNAL_API_TOKEN", "t" * 32)
    get_settings.cache_clear()
    yield TestClient(app_module.app)
    get_settings.cache_clear()


def _nothing_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """Past the gate, these would read the script or the cached audio: a refusal must stop before them."""

    def read(*a: Any, **k: Any) -> Any:
        raise AssertionError("read past the role check")

    monkeypatch.setattr(listen, "prepare", read)
    monkeypatch.setattr(listen, "chapters", read)


def test_BLD_C198_listen_refuses_anyone_not_on_the_desk_or_committee(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    @contextmanager
    def fake_connect(**k: Any) -> Iterator[Any]:
        yield object()

    asked: list[tuple[str, frozenset[str]]] = []

    def has_role(conn: Any, user_id: str, roles: frozenset[str]) -> bool:
        asked.append((user_id, frozenset(roles)))
        return False  # an admin with no desk or committee grant, or nobody at all

    monkeypatch.setattr(app_module, "connect", fake_connect)
    monkeypatch.setattr("desk.store.has_role", has_role)
    _nothing_read(monkeypatch)
    admin = str(uuid.uuid4())
    for route in ROUTES:
        for query in (f"?user_id={admin}", ""):
            r = client.get(route + query, headers=TOKEN)
            assert r.status_code == 403, (route, query)
            assert r.json() == {"error": "forbidden"}
            assert "audio" not in r.headers.get("content-type", "")
    assert {roles for _, roles in asked} == {READERS}
    assert {u for u, _ in asked} == {admin, ""}


def test_BLD_C198_listen_still_needs_the_internal_token(client: TestClient) -> None:
    for route in ROUTES:
        assert client.get(route).status_code in (401, 403)


@pytest.fixture
def real_db(db: Any, test_database: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    """The routes' own connections go to this run's test database."""

    @contextmanager
    def test_connect(**k: Any) -> Iterator[Any]:
        with connect(helpers.db_url(test_database), autocommit=True) as conn:
            yield conn

    monkeypatch.setattr(app_module, "connect", test_connect)
    yield db


def _person(db: Any, roles: tuple[str, ...]) -> str:
    user_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO users (id, emp_id_hash, name, email, first_name) VALUES (%s, %s, 'Synthetic Person', %s, "
        "'Synthetic')",
        (user_id, f"h-c198-{user_id}", f"person.{user_id[:8]}@kfintech.example"),
    )
    for role in roles:
        db.execute("INSERT INTO role_grants (user_id, role) VALUES (%s, %s)", (user_id, role))
    return user_id


def test_BLD_C198_against_postgres_an_admin_is_refused_the_desk_and_committee_pass(
    client: TestClient, real_db: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    passed: list[str] = []

    def chapters(conn: Any, ref: str) -> None:
        passed.append("chapters")
        return None  # 202 pending: nothing cached in this test

    def prepare(conn: Any, ref: str, **k: Any) -> Any:
        passed.append("audio")
        raise listen.ListenRefused(404, "not_found")  # the gate let them in; no script in this test

    monkeypatch.setattr(listen, "chapters", chapters)
    monkeypatch.setattr(listen, "prepare", prepare)
    admin = _person(real_db, ("admin",))
    nobody = _person(real_db, ())
    for user_id in (admin, nobody):
        for route in ROUTES:
            r = client.get(f"{route}?user_id={user_id}", headers=TOKEN)
            assert r.status_code == 403 and r.json() == {"error": "forbidden"}
    assert passed == []

    for roles in (("reviewer",), ("committee",), ("admin", "reviewer")):
        user_id = _person(real_db, roles)
        r = client.get(f"{ROUTES[1]}?user_id={user_id}", headers=TOKEN)
        assert r.status_code == 202 and r.json() == {"pending": True}, roles
        r = client.get(f"{ROUTES[0]}?user_id={user_id}", headers=TOKEN)
        assert r.status_code == 404 and r.json() == {"error": "not_found"}, roles
    assert passed == ["chapters", "audio"] * 3

    # A grant that has ended is no grant.
    ended = _person(real_db, ())
    real_db.execute(
        "INSERT INTO role_grants (user_id, role, valid_from, valid_to) "
        "VALUES (%s, 'reviewer', now() - interval '2 days', now() - interval '1 day')",
        (ended,),
    )
    for route in ROUTES:
        r = client.get(f"{route}?user_id={ended}", headers=TOKEN)
        assert r.status_code == 403 and r.json() == {"error": "forbidden"}, route
    assert passed == ["chapters", "audio"] * 3
