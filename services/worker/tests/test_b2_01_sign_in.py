"""AT-B2-01: first sign-in creates a `users` row from claims, shows the privacy notice, and stores acceptance with
the notice version. Driven through the real flow: /auth/login → mock IdP → /auth/callback."""

import secrets
from collections.abc import Iterator
from typing import Any

import generators as g
import pytest

from core.config import get_settings
from core.db import connect
from identity.codes import emp_id_hash
from tests.web import sign_in_with_mock

pytestmark = pytest.mark.stack


@pytest.fixture
def dev_db() -> Iterator[Any]:
    with connect(autocommit=True) as conn:
        yield conn


def test_first_sign_in_of_someone_not_yet_in_hr(dev_db: Any) -> None:
    employee_id = f"SYN-N{secrets.token_hex(3).upper()}"
    name = g.person_name(g.default_rng(5))
    email = f"new.joiner.{secrets.token_hex(3)}@kfintech.example"
    try:
        browser, callback = sign_in_with_mock(
            employee_id, {"email": email, "name": name, "employeeId": employee_id}
        )
        assert callback.headers["location"].startswith("http://localhost:3000/privacy-notice")

        user = dev_db.execute(
            "SELECT u.*, m.contributor_code FROM users u JOIN contributor_map m ON m.user_id = u.id "
            "WHERE u.emp_id_hash = %s",
            (emp_id_hash(employee_id),),
        ).fetchone()
        assert user is not None, "a users row is created from the claims"
        assert (user["name"], user["email"], user["source"]) == (name, email, "sign_in")
        assert user["last_sign_in_at"] is not None
        assert user["contributor_code"].startswith("CTR-")

        page = browser.get("/privacy-notice?next=%2F")
        assert page.status_code == 200 and "How 1% Club uses your information" in page.text
        assert browser.get("/").status_code in (302, 307), "pages wait for the notice"

        version = get_settings().privacy_notice_version
        assert browser.post("/api/me/privacy-notice", json={"version": "0.0-old"}).status_code == 409
        assert browser.post("/api/me/privacy-notice", json={"version": version}).status_code == 200
        accepted = dev_db.execute(
            "SELECT notice_version FROM privacy_acceptances WHERE user_id = %s", (user["id"],)
        ).fetchall()
        assert [r["notice_version"] for r in accepted] == [version]
        assert browser.get("/").status_code == 200

        # A second sign-in does not create a second person.
        sign_in_with_mock(employee_id, {"email": email, "name": name, "employeeId": employee_id})
        assert (
            dev_db.execute("SELECT count(*) AS n FROM users WHERE email = %s", (email,)).fetchone()["n"] == 1
        )
    finally:
        dev_db.execute("DELETE FROM users WHERE emp_id_hash = %s", (emp_id_hash(employee_id),))


def test_sign_in_matches_the_hr_record(dev_db: Any) -> None:
    """Persona SYN-00017 comes from the synthetic HR import (make seed); signing in must not duplicate them."""
    before = dev_db.execute("SELECT count(*) AS n FROM users").fetchone()["n"]
    _, callback = sign_in_with_mock("SYN-00017")
    assert callback.status_code in (302, 307)
    row = dev_db.execute(
        "SELECT source, last_sign_in_at FROM users WHERE emp_id_hash = %s", (emp_id_hash("SYN-00017"),)
    ).fetchone()
    assert row["source"] == "hr" and row["last_sign_in_at"] is not None
    assert dev_db.execute("SELECT count(*) AS n FROM users").fetchone()["n"] == before


def test_leavers_cannot_sign_in(dev_db: Any) -> None:
    employee_id = f"SYN-L{secrets.token_hex(3).upper()}"
    email = f"leaver.{secrets.token_hex(3)}@kfintech.example"
    try:
        sign_in_with_mock(
            employee_id, {"email": email, "name": "Synthetic Leaver", "employeeId": employee_id}
        )
        dev_db.execute("UPDATE users SET active = false WHERE emp_id_hash = %s", (emp_id_hash(employee_id),))
        _, callback = sign_in_with_mock(employee_id, {"email": email, "employeeId": employee_id})
        assert callback.headers["location"].endswith("/sign-in?error=inactive")
        assert "ideas_session" not in callback.headers.get("set-cookie", "").split("=")[0]
    finally:
        dev_db.execute("DELETE FROM users WHERE emp_id_hash = %s", (emp_id_hash(employee_id),))


def test_a_forged_state_is_refused() -> None:
    from tests.web import Browser

    b = Browser()
    b.get("/auth/login?next=/")
    r = b.get("/auth/callback?code=anything&state=not-the-one-we-sent")
    assert r.headers["location"].endswith("/sign-in?error=state_mismatch")


def test_next_cannot_leave_the_site() -> None:
    from tests.web import Browser

    for evil in (
        "https://example.com",
        "//example.com",
        "/\\example.com",
        "/%09/example.com",
        "/%0A/example.com",
    ):
        b = Browser()
        b.get(f"/auth/login?next={evil}")
        page = b.get(f"/sign-in?next={evil}")
        assert "/auth/login?next=%2F" in page.text


def test_conflicting_claims_are_refused(dev_db: Any) -> None:
    """Review finding: an unknown employee ID with a colleague's email must not sign in as that colleague."""
    colleague_email = dev_db.execute(
        "SELECT email FROM users WHERE emp_id_hash = %s", (emp_id_hash("SYN-00017"),)
    ).fetchone()["email"]
    stranger = f"SYN-X{secrets.token_hex(3).upper()}"
    _, callback = sign_in_with_mock(
        stranger, {"employeeId": stranger, "email": colleague_email, "name": "Someone"}
    )
    assert callback.headers["location"].endswith("/sign-in?error=identity_mismatch")
    assert (
        dev_db.execute(
            "SELECT count(*) AS n FROM users WHERE emp_id_hash = %s", (emp_id_hash(stranger),)
        ).fetchone()["n"]
        == 0
    )


def test_double_slash_lookalikes_never_reach_a_handler() -> None:
    """Review question: can "//api/…" be treated as a page? Next.js answers every such path with a 308 to the
    clean path, which then gets the normal session, privacy and policy checks (the proxy also refuses "//")."""
    import httpx

    from tests.web import WEB

    for path, clean in (
        ("//api/admin/roles", "/api/admin/roles"),
        ("/api//admin/roles", "/api/admin/roles"),
        ("//admin", "/admin"),
    ):
        r = httpx.get(WEB + path, timeout=10, follow_redirects=False)
        assert r.status_code == 308 and r.headers["location"] in (clean, WEB + clean), path
        assert httpx.get(WEB + clean, timeout=10, follow_redirects=False).status_code in (302, 307, 401), (
            clean
        )
