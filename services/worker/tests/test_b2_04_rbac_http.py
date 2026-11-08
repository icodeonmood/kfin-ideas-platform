"""AT-B2-04 (HTTP half): for every role column in §3.1 and every day-one endpoint in §8, the running proxy
allows or denies exactly as policy/rbac.yaml says. Table-driven, generated from the policy file.

Allowed means "not 401/403" (the route itself may still be unbuilt: 404 or 501). Denied means exactly 403.
"""

import re
from collections.abc import Iterator
from typing import Any

import pytest
import yaml

from core.db import connect
from tests import helpers
from tests.web import people

pytestmark = pytest.mark.stack

POLICY = yaml.safe_load((helpers.ROOT / "policy" / "rbac.yaml").read_text(encoding="utf-8"))
ROLE_COLUMNS: list[str] = POLICY["roles"]


def _effective(role: str) -> set[str]:
    roles = {"contributor", role}
    alias = POLICY["role_aliases"].get(role)
    return roles | ({alias} if alias else set())


def _expected(roles: set[str], capabilities: list[str]) -> bool:
    return any(set(POLICY["capabilities"][c]) & roles for c in capabilities)


ENDPOINTS = [
    (parts[0], re.sub(r"\{[a-z_]+\}", "x1", parts[1]), parts[2:])
    for parts in (line.split() for line in POLICY["endpoints"])
]


@pytest.fixture(scope="module")
def sessions() -> Iterator[dict[str, Any]]:
    with connect(autocommit=True) as conn, people(conn) as make:
        yield {
            role: make(() if role == "contributor" else ((role, None),)).browser() for role in ROLE_COLUMNS
        }


@pytest.mark.parametrize("role", ROLE_COLUMNS)
def test_matrix_for_role(role: str, sessions: dict[str, Any]) -> None:
    browser = sessions[role]
    roles = _effective(role)
    wrong: list[str] = []
    for method, path, capabilities in ENDPOINTS:
        status = browser.request(method, path, json={} if method != "GET" else None).status_code
        allowed = _expected(roles, capabilities)
        if allowed and status in (401, 403):
            wrong.append(f"{method} {path}: expected allowed, got {status}")
        if not allowed and status != 403:
            wrong.append(f"{method} {path}: expected 403, got {status}")
    assert wrong == []


def test_unlisted_api_paths_are_refused(sessions: dict[str, Any]) -> None:
    r = sessions["admin"].get("/api/secret-new-route")
    assert r.status_code == 404 and r.json() == {"error": "not_found"}


def test_pages_follow_the_policy(sessions: dict[str, Any]) -> None:
    redirected = (302, 307)
    assert sessions["contributor"].get("/review").status_code in redirected
    assert sessions["reviewer"].get("/review").status_code not in redirected
    assert sessions["core_committee"].get("/desk-decisions").status_code not in redirected
    assert sessions["contributor"].get("/admin").status_code in redirected
    assert sessions["admin"].get("/admin").status_code not in redirected
