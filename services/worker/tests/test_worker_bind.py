"""BLD-C017, BLD-C030: the worker's API is not reachable from the speech network, its internal routes refuse callers
without the token, and the speech service's address is allowlisted outside dev and test. No stack needed."""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any

import pytest

from core.config import Settings, get_settings
from core.netbind import BindError, api_hosts, pick_address

TOKEN = "synthetic-internal-token-for-the-auth-test-000"


def test_the_api_listens_on_the_peers_network_only() -> None:
    interfaces = [("127.0.0.1", "255.0.0.0"), ("172.19.0.5", "255.255.0.0"), ("172.23.0.3", "255.255.0.0")]
    assert pick_address("172.19.0.2", interfaces) == "172.19.0.5"  # postgres's network, not the speech one
    assert pick_address("10.9.9.9", interfaces) is None


def test_without_a_peer_it_listens_everywhere_and_with_an_unknown_one_it_refuses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert api_hosts("") == ["0.0.0.0"]  # noqa: S104 - what is expected with no peer
    monkeypatch.setattr("core.netbind.socket.gethostbyname", lambda host: "10.9.9.9")
    monkeypatch.setattr("core.netbind.local_ipv4", lambda: [("172.19.0.5", "255.255.0.0")])
    with pytest.raises(BindError) as exc:
        api_hosts("postgres", wait_s=0)
    assert exc.value.code == "no_interface_on_peer_network"
    monkeypatch.setattr("core.netbind.socket.gethostbyname", lambda host: "172.19.0.2")
    assert api_hosts("postgres", wait_s=0) == ["127.0.0.1", "172.19.0.5"]


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    from fastapi.testclient import TestClient

    monkeypatch.setenv("INTERNAL_API_TOKEN", TOKEN)
    monkeypatch.setenv("DATABASE_URL", "postgres://nobody:nothing@127.0.0.1:1/none?connect_timeout=1")
    get_settings.cache_clear()
    from api.app import app

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c, app
    get_settings.cache_clear()


def test_every_internal_route_refuses_a_caller_without_the_token(client: Any) -> None:
    """What the speech service (or anything else on a network it should not be on) would meet."""
    c, app = client
    checked = 0
    for route in app.routes:
        path = getattr(route, "path", "")
        if not path.startswith("/internal/") or path == "/internal/health":
            continue
        filled = path
        for part in [p for p in path.split("/") if p.startswith("{")]:
            filled = filled.replace(part, "00000000-0000-0000-0000-000000000000")
        for method in sorted(getattr(route, "methods", set()) - {"HEAD", "OPTIONS"}):
            r = c.request(method, filled, headers={"X-Internal-Token": "wrong"})
            assert r.status_code == 401, (method, path, r.status_code)
            r = c.request(method, filled)
            assert r.status_code == 401, (method, path, r.status_code)
            checked += 1
    assert checked > 50


def test_the_one_open_route_reveals_nothing(client: Any) -> None:
    c, _app = client
    r = c.get("/internal/health")
    assert r.status_code in (200, 503)
    assert set(r.json()) <= {"status", "roles", "detail"}
    for docs in ("/docs", "/redoc", "/openapi.json"):
        assert c.get(docs).status_code == 404


@pytest.mark.parametrize(
    ("url", "ok"),
    [
        ("http://speech:8300", True),
        ("http://speech", True),
        ("https://speech:8300", False),
        ("http://evil.example:8300", False),
        ("http://user:pass@speech:8300", False),
        ("ftp://speech", False),
    ],
)
def test_outside_dev_the_speech_url_must_be_the_internal_service(
    monkeypatch: pytest.MonkeyPatch, url: str, ok: bool
) -> None:
    monkeypatch.setenv("APP_ENV", "uat")
    monkeypatch.setenv("SPEECH_ENGINE_URL", url)
    if ok:
        assert Settings().speech_engine_url == url
    else:
        with pytest.raises(ValueError):
            Settings()
    monkeypatch.setenv("APP_ENV", "test")  # dev and test may point anywhere (the contract test)
    assert Settings().speech_engine_url == url
    os.environ.pop("SPEECH_ENGINE_URL", None)
