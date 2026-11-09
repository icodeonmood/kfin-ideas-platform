"""HTTP helpers for stack tests against the web app: real sign-in through the mock IdP, and test sessions.

Session cookies are Secure. Python's cookie jar will not send a Secure cookie to http://localhost (browsers
will), so these helpers read Set-Cookie and send Cookie headers themselves.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.cookies import SimpleCookie
from typing import Any

import httpx
import psycopg
from psycopg import sql

from core.config import get_settings
from core.db import Conn

WEB = get_settings().app_base_url.rstrip("/")
OIDC_ISSUER = get_settings().oidc_issuer.rstrip("/")


def set_cookies(response: httpx.Response) -> dict[str, dict[str, str]]:
    """Every Set-Cookie on a response: name -> attributes (value under "value")."""
    out: dict[str, dict[str, str]] = {}
    for header in response.headers.get_list("set-cookie"):
        jar: SimpleCookie = SimpleCookie()
        jar.load(header)
        for name, morsel in jar.items():
            attrs = {k: v for k, v in morsel.items() if v}
            lowered = header.lower()
            attrs["value"] = morsel.value
            attrs["httponly"] = "true" if "httponly" in lowered else ""
            attrs["secure"] = "true" if "; secure" in lowered else ""
            out[name] = attrs
    return out


@dataclass
class Browser:
    """A tiny browser: keeps cookies (including Secure ones) and never follows redirects on its own."""

    cookies: dict[str, str] = field(default_factory=dict)

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        url = url if url.startswith("http") else WEB + url
        headers = {**kwargs.pop("headers", {})}
        if self.cookies and url.startswith(WEB):
            headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in self.cookies.items())
        response = httpx.request(method, url, headers=headers, follow_redirects=False, timeout=15, **kwargs)
        if url.startswith(WEB):
            for name, attrs in set_cookies(response).items():
                if attrs.get("max-age") == "0" or not attrs["value"]:
                    self.cookies.pop(name, None)
                else:
                    self.cookies[name] = attrs["value"]
        return response

    def get(self, url: str, **kw: Any) -> httpx.Response:
        return self.request("GET", url, **kw)

    def post(self, url: str, **kw: Any) -> httpx.Response:
        return self.request("POST", url, **kw)


def sign_in_with_mock(
    username: str, claims: dict[str, str] | None = None, next_path: str = "/"
) -> tuple[Browser, httpx.Response]:
    """The real authorisation-code flow: /auth/login → mock IdP form → /auth/callback. Returns the callback response."""
    b = Browser()
    start = b.get(f"/auth/login?next={next_path}")
    assert start.status_code in (302, 307), start.status_code
    authorize = start.headers["location"]
    assert authorize.startswith(f"{OIDC_ISSUER}/authorize?")
    form = httpx.post(
        authorize,
        data={"username": username, "claims": json.dumps(claims) if claims else ""},
        follow_redirects=False,
        timeout=15,
    )
    assert form.status_code in (302, 303), form.status_code
    callback = form.headers["location"]
    assert callback.startswith(WEB + "/auth/callback?")
    return b, b.get(callback)


@dataclass
class TestPerson:
    user_id: str
    contributor_code: str
    token: str

    def browser(self) -> Browser:
        return Browser(cookies={"ideas_session": self.token})


@contextmanager
def people(conn: Conn) -> Iterator[Any]:
    """Create synthetic people with sessions straight in the dev database; delete them afterwards."""
    created: list[str] = []

    def make(roles: tuple[tuple[str, str | None], ...] = (), *, accepted: bool = True) -> TestPerson:
        suffix = secrets.token_hex(4)
        user = conn.execute(
            "INSERT INTO users (emp_id_hash, name, email, source) VALUES (%s, %s, %s, 'sign_in') RETURNING id",
            (f"test:{suffix}", f"Test Person {suffix}", f"test.{suffix}@kfintech.example"),
        ).fetchone()
        assert user is not None
        user_id = str(user["id"])
        created.append(user_id)
        code = f"CTR-{suffix}"
        conn.execute(
            "INSERT INTO contributor_map (contributor_code, user_id) VALUES (%s, %s)", (code, user_id)
        )
        for role, scope in roles:
            conn.execute(
                "INSERT INTO role_grants (user_id, role, scope_id) VALUES (%s, %s, %s)",
                (user_id, role, scope),
            )
        if accepted:
            conn.execute(
                "INSERT INTO privacy_acceptances (user_id, notice_version) VALUES (%s, %s)",
                (user_id, get_settings().privacy_notice_version),
            )
        token = secrets.token_urlsafe(32)
        conn.execute(
            "INSERT INTO sessions (id_hash, user_id, expires_at) VALUES (%s, %s, now() + interval '1 hour')",
            (hashlib.sha256(token.encode()).digest(), user_id),
        )
        return TestPerson(user_id, code, token)

    try:
        yield make
    finally:
        if created:
            # Ideas are keyed by contributor code (no FK, so erasure keeps them): remove test drafts explicitly.
            conn.execute(
                "DELETE FROM pseudonym_vault WHERE scope_id IN (SELECT idea_id FROM ideas WHERE contributor_code IN "
                "(SELECT contributor_code FROM contributor_map WHERE user_id = ANY(%s::uuid[])))",
                (created,),
            )
            conn.execute(
                "DELETE FROM ideas WHERE contributor_code IN "
                "(SELECT contributor_code FROM contributor_map WHERE user_id = ANY(%s::uuid[]))",
                (created,),
            )
            remove_people(conn, created)


# Rows that test people may have created and that keep a user from being deleted (RESTRICT or NO ACTION foreign
# keys to users): Ember drafts and issues, deliveries, write-ups, check-ins, files, proposals and decisions.
_BLOCKING_FKS = """
SELECT n.nspname AS schema, t.relname AS tbl, a.attname AS col
FROM pg_constraint c
JOIN pg_class t ON t.oid = c.conrelid
JOIN pg_namespace n ON n.oid = t.relnamespace
JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
WHERE c.contype = 'f' AND c.confrelid = 'users'::regclass AND c.confdeltype IN ('r', 'a')
ORDER BY t.relname, a.attname
"""


def remove_people(conn: Conn, user_ids: list[str], passes: int = 6) -> None:
    """Delete test people and every row they created that would block it, so teardown never fails (the RBAC HTTP
    matrix, for example, opens an Ember draft as its admin). Drafts go first; then each blocking table, a few passes
    so rows that block each other clear in order. Only rows that point at these test people are touched."""
    conn.execute(
        "DELETE FROM ember_issues WHERE state <> 'sent' AND (created_by = ANY(%(u)s::uuid[]) "
        "OR chair_note_by = ANY(%(u)s::uuid[]) OR note_approved_by = ANY(%(u)s::uuid[]))",
        {"u": user_ids},
    )
    fks = conn.execute(_BLOCKING_FKS).fetchall()
    for _ in range(passes):
        try:
            with conn.transaction():
                conn.execute("DELETE FROM users WHERE id = ANY(%s::uuid[])", (user_ids,))
            return
        except psycopg.errors.IntegrityError:  # a foreign key (RESTRICT or NO ACTION) still points at them
            pass
        for fk in fks:
            try:
                with conn.transaction():
                    conn.execute(
                        sql.SQL("DELETE FROM {} WHERE {} = ANY(%s::uuid[])").format(
                            sql.Identifier(fk["schema"], fk["tbl"]), sql.Identifier(fk["col"])
                        ),
                        (user_ids,),
                    )
            except psycopg.Error:
                continue  # another of their rows still points here; the next pass clears it
    conn.execute("DELETE FROM users WHERE id = ANY(%s::uuid[])", (user_ids,))  # raises with the real reason
