"""Admin APIs (B2): role grants and kill switches. Every change needs a reason and lands in audit_log;
kill switches follow §7.6 "Who can flip"."""

from collections.abc import Iterator
from typing import Any

import pytest

from core.db import connect
from tests.web import people

pytestmark = pytest.mark.stack


@pytest.fixture
def dev_db() -> Iterator[Any]:
    with connect(autocommit=True) as conn:
        yield conn


def test_grant_and_revoke_are_audited(dev_db: Any) -> None:
    with people(dev_db) as make:
        admin = make((("admin", None),))
        target = make()
        email = dev_db.execute("SELECT email FROM users WHERE id = %s", (target.user_id,)).fetchone()["email"]
        b = admin.browser()

        assert (
            b.post(
                "/api/admin/roles", json={"email": email, "role": "reviewer", "reason": "short"}
            ).status_code
            == 400
        )
        # The old committee roles are retired (DEC-102, DEC-106): only the pack's roles can be given (BLD-A215).
        for retired in ("lob_committee", "core_committee", "sponsor"):
            assert b.post(
                "/api/admin/roles", json={"email": email, "role": retired, "reason": "launch week rota"}
            ).json() == {"error": "unknown_role"}
        r = b.post(
            "/api/admin/roles",
            json={"email": email, "role": "reviewer", "reason": "launch week review desk rota"},
        )
        assert r.status_code == 201
        grant_id = r.json()["id"]
        assert (
            b.post(
                "/api/admin/roles", json={"email": email, "role": "reviewer", "reason": "launch week again"}
            ).status_code
            == 409
        )

        audit = dev_db.execute(
            "SELECT actor, action, reason FROM audit_log WHERE entity = %s ORDER BY id",
            (f"role_grant:{grant_id}",),
        ).fetchall()
        assert [(a["actor"], a["action"]) for a in audit] == [(f"user:{admin.user_id}", "role.grant")]

        # The new reviewer can now reach the review queue.
        assert target.browser().get("/api/review/items").status_code != 403

        assert b.request("DELETE", f"/api/admin/roles/{grant_id}", json={"reason": "no"}).status_code == 400
        assert (
            b.request(
                "DELETE", f"/api/admin/roles/{grant_id}", json={"reason": "rota ended this week"}
            ).status_code
            == 204
        )
        assert target.browser().get("/api/review/items").status_code == 403
        row = dev_db.execute("SELECT valid_to FROM role_grants WHERE id = %s", (grant_id,)).fetchone()
        assert row["valid_to"] is not None, "revoked grants are ended, not deleted"
        actions = [
            a["action"]
            for a in dev_db.execute(
                "SELECT action FROM audit_log WHERE entity = %s ORDER BY id", (f"role_grant:{grant_id}",)
            ).fetchall()
        ]
        assert actions == ["role.grant", "role.revoke"]


def test_only_admins_grant_roles(dev_db: Any) -> None:
    with people(dev_db) as make:
        for role in ("reviewer", "core_committee", "infosec"):
            b = make(((role, None),)).browser()
            assert b.get("/api/admin/roles").status_code == 403
            assert b.post("/api/admin/roles", json={}).status_code == 403


def test_kill_switches_follow_who_can_flip(dev_db: Any) -> None:
    with people(dev_db) as make:
        infosec = make((("infosec", None),)).browser()
        admin = make((("admin", None),)).browser()
        hr = make((("hr", None),)).browser()

        def flip(b: Any, name: str, state: str) -> str:
            r = b.request(
                "PUT",
                "/api/admin/kill-switches",
                json={"name": name, "state": state, "reason": "access rule test"},
            )
            # The status and the error code together, so an intermittent failure says what happened (BLD-097).
            try:
                body = r.json()
            except ValueError:
                body = None
            code = body.get("error", "") if isinstance(body, dict) else r.headers.get("content-type", "")
            return f"{r.status_code} {code}"

        got = {
            "infosec submissions": flip(infosec, "submissions", "on"),
            "admin attachments.open": flip(admin, "attachments.open", "on"),
            "hr ai.all": flip(hr, "ai.all", "on"),
            "hr wall.public": flip(hr, "wall.public", "on"),
            "infosec attachments.open": flip(infosec, "attachments.open", "on"),
            "admin agent.judge": flip(admin, "agent.judge", "on"),
        }
        assert {k: v.split()[0] for k, v in got.items()} == {
            "infosec submissions": "403", "admin attachments.open": "403", "hr ai.all": "403",
            "hr wall.public": "200", "infosec attachments.open": "200", "admin agent.judge": "200",
        }, got  # fmt: skip
        listed = {
            s["name"]: s["can_flip"] for s in infosec.get("/api/admin/kill-switches").json()["switches"]
        }
        assert listed["attachments.open"] is True and listed["submissions"] is False
