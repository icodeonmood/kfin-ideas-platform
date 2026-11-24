"""BLD-A253: every synthetic person signs in as themselves, on one shared HTTP client (L-AUTH, AT-B8-01; BLD-A242).

The load-hour proof on a GitHub runner (CI run 45480395541, 25 Nov 2026) counted 169 of 170 sign-ins failed. The
shared client was given `httpx.Cookies(CookieJar(policy=...))`; httpx copies an `httpx.Cookies` into a fresh default
jar, so the policy that keeps no cookie was lost. The first person's session cookie then went with every later
person's first request, and `/auth/login` answered "already signed in" (`startSso`) instead of sending them to the
identity provider. The A242 fake app hid it: its session cookie is `Secure`, which no jar sends over plain http; the
dev stack on a runner serves http, so its cookie is not `Secure`. These tests use a fake that answers as the dev
stack does. No stack, no database, no network."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from loadtest import __main__ as lt
from tests.test_a242_loadtest_1pc import BASE, IDP, FakeClub


class DevStack(FakeClub):
    """FakeClub as the dev stack answers over plain http: the session cookie is not `Secure`, and `/auth/login`
    with a live session goes straight back to the app ("already signed in", apps/web/src/server/auth/sso.ts)."""

    def __init__(self) -> None:
        super().__init__()
        self.sessions: set[str] = set()
        self.logins_already_signed_in = 0
        self.idp_posts = 0

    @staticmethod
    def _token(request: httpx.Request) -> str:
        return (request.headers.get("cookie") or "").removeprefix("kfin_session=")

    def handle(self, request: httpx.Request) -> httpx.Response:
        host, path = request.url.host, request.url.path
        if host == "idp.test":
            self.idp_posts += 1
        if host == "web.test" and path == "/auth/login":
            self.calls.append((request.method, host, path))
            self.requests.append(request)
            if self._token(request) in self.sessions:
                self.logins_already_signed_in += 1
                return httpx.Response(307, headers={"location": f"{BASE}/"})
            return httpx.Response(307, headers={"location": f"{IDP}/authorize?client_id=web"})
        if host == "web.test" and path == "/auth/callback":
            self.calls.append((request.method, host, path))
            self.requests.append(request)
            token = f"tok{len(self.calls)}"
            self.sessions.add(token)
            # Plain http: the dev stack's session cookie is not Secure, so a jar that keeps it would send it.
            return httpx.Response(
                307,
                headers={
                    "location": "/",
                    "set-cookie": f"kfin_session={token}; Path=/; HttpOnly; SameSite=Lax",
                },
            )
        return super().handle(request)


@pytest.mark.parametrize("origin", [BASE, "https://web.test", IDP, "http://localhost:8090"])
def test_bld_a253_the_shared_client_keeps_no_cookie(origin: str) -> None:
    """The web app and the identity provider, over http and https: the shared client keeps and sends none."""

    def answer(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/set":
            return httpx.Response(
                200,
                headers=[
                    ("set-cookie", "kfin_session=t1; Path=/"),
                    ("set-cookie", "ideas_oidc=tx1; Path=/auth; HttpOnly"),
                    ("set-cookie", "idp_session=i1; Path=/; Secure"),
                ],
            )
        return httpx.Response(200, json={"cookie": request.headers.get("cookie")})

    async def go() -> tuple[int, list[str | None]]:
        async with lt.shared_client(httpx.MockTransport(answer)) as client:
            await client.get(f"{origin}/set")
            sent = [(await client.get(f"{origin}{p}")).json()["cookie"] for p in ("/next", "/auth/callback")]
            return len(client.cookies.jar), sent

    kept, sent = asyncio.run(go())
    assert kept == 0 and sent == [None, None]


def test_bld_a253_each_person_signs_in_as_themselves_on_the_dev_stack(tmp_path: Path) -> None:
    """The three authors one after another, then sign-ins arriving while shares run (most of the runner's 169)."""
    app = DevStack()
    argv = ["--base-url", BASE, "--scale", "0.0003", "--submissions-per-hour", "36000", "--authors", "3",
            "--people", "4", "--sign-ins", "60000", "--poll", "0.01", "--scan-timeout", "2", "--draft-timeout", "2",
            "--out", str(tmp_path)]  # fmt: skip
    code = lt.main(argv, transport=app.transport)
    # nobody started a sign-in carrying someone else's session, and each went to the identity provider
    assert app.logins_already_signed_in == 0
    assert all(not r.headers.get("cookie") for r in app.requests if r.url.path == "/auth/login")
    report = json.loads(next(tmp_path.glob("report-*.json")).read_text())
    sign_ins = report["operations"]["sign_in"]
    assert (
        sign_ins["attempted"] > 3 and sign_ins["failed"] == 0
    )  # more than the authors: arrivals during shares
    assert "sign_in" not in report["errors"]
    assert app.idp_posts == sign_ins["attempted"] == len(app.sessions)
    assert code == 0
