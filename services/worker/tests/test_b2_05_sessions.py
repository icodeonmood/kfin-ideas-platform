"""AT-B2-05: any /api/* call without a session returns 401; the session cookie is HttpOnly, Secure and
SameSite=Lax with an 8-hour lifetime. Plus: sign-out revokes, expiry is enforced, cross-site writes refused."""

import re
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
import yaml

from core.db import connect
from tests import helpers
from tests.web import WEB, people, set_cookies, sign_in_with_mock

pytestmark = pytest.mark.stack

POLICY = yaml.safe_load((helpers.ROOT / "policy" / "rbac.yaml").read_text(encoding="utf-8"))


def _endpoints() -> list[tuple[str, str]]:
    return [(line.split()[0], re.sub(r"\{[a-z_]+\}", "x1", line.split()[1])) for line in POLICY["endpoints"]]


@pytest.fixture
def dev_db() -> Iterator[Any]:
    with connect(autocommit=True) as conn:
        yield conn


@pytest.mark.parametrize(("method", "path"), _endpoints())
def test_every_api_endpoint_needs_a_session(method: str, path: str) -> None:
    r = httpx.request(method, WEB + path, json={} if method != "GET" else None, timeout=10)
    assert r.status_code == 401, f"{method} {path} -> {r.status_code}"
    assert r.json() == {"error": "sign_in_required"}


def test_health_is_the_only_public_api() -> None:
    assert POLICY["public"] == ["GET /api/health"]
    assert httpx.get(WEB + "/api/health", timeout=10).status_code == 200


def test_session_cookie_flags() -> None:
    _, callback = sign_in_with_mock("SYN-00017")
    cookie = set_cookies(callback)["ideas_session"]
    assert cookie["httponly"] == "true"
    assert cookie["secure"] == "true"
    assert cookie["samesite"].lower() == "lax"
    assert cookie["max-age"] == str(8 * 60 * 60)
    assert cookie["path"] == "/"


def test_sign_out_revokes_the_session() -> None:
    browser, _ = sign_in_with_mock("SYN-00017")
    token = browser.cookies["ideas_session"]
    assert browser.get("/api/me").status_code == 200
    out = browser.post("/auth/logout")
    assert out.status_code == 303 and out.headers["location"].endswith("/signed-out")
    replay = httpx.get(WEB + "/api/me", headers={"Cookie": f"ideas_session={token}"}, timeout=10)
    assert replay.status_code == 401, "a revoked token must not work even if someone kept a copy"


def test_expired_session_is_refused(dev_db: Any) -> None:
    with people(dev_db) as make:
        person = make()
        assert person.browser().get("/api/me").status_code == 200
        dev_db.execute(
            "UPDATE sessions SET created_at = now() - interval '9 hours', expires_at = now() - interval '1 minute' "
            "WHERE user_id = %s",
            (person.user_id,),
        )
        assert person.browser().get("/api/me").status_code == 401


def test_cross_site_writes_are_refused(dev_db: Any) -> None:
    # A route no kill switch guards, so a switch flipped by another test cannot change the answer.
    with people(dev_db) as make:
        b = make().browser()
        body = {"version": "irrelevant"}
        r = b.post("/api/me/privacy-notice", json=body, headers={"Origin": "https://evil.example"})
        assert r.status_code == 403 and r.json() == {"error": "cross_origin"}
        same_origin = b.post("/api/me/privacy-notice", json=body, headers={"Origin": WEB})
        assert same_origin.status_code == 409  # reached the handler (wrong version), not refused


def test_pages_send_people_to_sign_in() -> None:
    r = httpx.get(WEB + "/my-ideas", follow_redirects=False, timeout=10)
    assert r.status_code in (302, 307)
    assert r.headers["location"] == f"{WEB}/sign-in?next=%2Fmy-ideas"


def test_session_store_holds_hashes_only(dev_db: Any) -> None:
    browser, _ = sign_in_with_mock("SYN-00017")
    token = browser.cookies["ideas_session"]
    hit = dev_db.execute(
        "SELECT count(*) AS n FROM sessions WHERE encode(id_hash, 'escape') LIKE %s", (f"%{token}%",)
    ).fetchone()["n"]
    assert hit == 0
