"""AT-B2-04 (HTTP half): for every role column in §3.1 and every day-one endpoint in §8, the running proxy
allows or denies exactly as policy/rbac.yaml says. Table-driven, generated from the policy file.

Allowed means "not 401/403" (the route itself may still be unbuilt: 404 or 501). Denied means exactly 403.

Membership-scoped endpoints (BLD-108) are open to everyone signed in at the proxy but served only to members of a
group (for "ones": an active One, DEC-077). No role grants membership, so every role column expects 403 there,
and a separate test proves a member persona is let through.
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


def _path(line: str) -> tuple[str, str]:
    method, path = line.split()[:2]
    return method, re.sub(r"\{[a-z_]+\}", "x1", path)


ENDPOINTS = [(*_path(line), line.split()[2:]) for line in POLICY["endpoints"]]
MEMBERSHIP: dict[tuple[str, str], str] = {
    _path(line): group for group, lines in POLICY.get("membership_scoped", {}).items() for line in lines
}


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
        allowed = _expected(roles, capabilities) and (method, path) not in MEMBERSHIP
        if allowed and status in (401, 403):
            wrong.append(f"{method} {path}: expected allowed, got {status}")
        if not allowed and status != 403:
            wrong.append(f"{method} {path}: expected 403, got {status}")
    assert wrong == []


def test_membership_scoped_endpoints_are_listed_and_signed_in() -> None:
    listed = {(m, p): caps for m, p, caps in ENDPOINTS}
    assert MEMBERSHIP, "the Ones-only routes should be declared"
    for key in MEMBERSHIP:
        # Membership narrows a signed-in route; it never widens one.
        assert listed.get(key) == ["signed_in"], key


def test_membership_scoped_endpoints_admit_their_members() -> None:
    """The same requests the matrix sends, from an active One: never 401 or 403, and the leaderboard serves."""
    with connect(autocommit=True) as conn, people(conn) as make:
        one = make()
        conn.execute(
            "INSERT INTO ones (induction_no, user_id, number, way_in, swap_until) VALUES ("
            "(SELECT coalesce(max(induction_no), 0) + 1 FROM ones), %s, "
            "(SELECT min(n) FROM generate_series(900, 999) n WHERE n NOT IN "
            "(SELECT number FROM ones WHERE number IS NOT NULL UNION SELECT number FROM one_legend_numbers)), "
            "'sponsored', now() + interval '30 days')",
            (one.user_id,),
        )
        try:
            browser = one.browser()
            wrong = []
            for method, path in [k for k, group in MEMBERSHIP.items() if group == "ones"]:
                status = browser.request(method, path, json={} if method != "GET" else None).status_code
                if status in (401, 403):
                    wrong.append(f"{method} {path}: a One got {status}")
            assert wrong == []
            assert browser.get("/api/ones/leaderboard").status_code == 200
        finally:
            conn.execute("DELETE FROM ones WHERE user_id = %s", (one.user_id,))


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
