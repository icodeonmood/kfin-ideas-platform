"""L-AUTH.rules/2-3 (BLD-E002): the sign-in code email goes out at once through the comms path, only while both
`auth.email_code` and `comms.email` are on, only to an active person, and the code is never stored or logged."""

from __future__ import annotations

import secrets
from collections.abc import Iterator
from typing import Any

import pytest

from comms import sign_in_code
from core import killswitch


@pytest.fixture
def person(db: Any, company_repo: Any, test_database: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    """A person, with the email rendered from this checkout's template (a fresh copy of the seed)."""
    from comms import templates
    from tests import helpers

    settings = helpers.settings_for(company_repo, test_database)
    for module in (templates, sign_in_code):
        monkeypatch.setattr(module, "get_settings", lambda: settings)
    templates._load.cache_clear()
    killswitch.clear_cache()
    tag = secrets.token_hex(3)
    row = db.execute(
        "INSERT INTO users (emp_id_hash, name, email, source) VALUES (%s, %s, %s, 'hr') RETURNING id",
        (f"test:code:{tag}", "Synthetic Signer", f"signer.{tag}@kfintech.example"),
    ).fetchone()
    yield db, str(row["id"]), f"signer.{tag}@kfintech.example"
    templates._load.cache_clear()
    killswitch.clear_cache()


def test_the_code_email_goes_out_at_once_and_nothing_keeps_the_code(
    person: Any, monkeypatch: pytest.MonkeyPatch, captured_logs: Any
) -> None:
    db, user_id, address = person
    sent: list[tuple[str, Any]] = []
    monkeypatch.setattr("comms.sign_in_code._smtp", lambda to, email: sent.append((to, email)))
    queued = db.execute("SELECT count(*) AS n FROM notifications").fetchone()["n"]
    sign_in_code.send(db, user_id, "481902", 10)
    assert [to for to, _ in sent] == [address]
    email = sent[0][1]
    assert email.subject == "Your 1% Club sign-in code"
    assert "481902" in email.text and "10 minutes" in email.text and "Synthetic" in email.text
    assert db.execute("SELECT count(*) AS n FROM notifications").fetchone()["n"] == queued  # never queued
    assert "481902" not in captured_logs.getvalue()


@pytest.mark.parametrize("switch", ["auth.email_code", "comms.email"])
def test_either_switch_off_stops_it(person: Any, monkeypatch: pytest.MonkeyPatch, switch: str) -> None:
    db, user_id, _ = person
    sent: list[str] = []
    monkeypatch.setattr("comms.sign_in_code._smtp", lambda to, email: sent.append(to))
    db.execute("UPDATE kill_switches SET state = 'off' WHERE name = %s", (switch,))
    killswitch.clear_cache()
    with pytest.raises(sign_in_code.CodeEmailRefused) as refused:
        sign_in_code.send(db, user_id, "481902", 10)
    assert refused.value.status == 503 and sent == []


def test_a_leaver_or_a_bad_request_gets_nothing(person: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    db, user_id, _ = person
    sent: list[str] = []
    monkeypatch.setattr("comms.sign_in_code._smtp", lambda to, email: sent.append(to))
    with pytest.raises(sign_in_code.CodeEmailRefused):
        sign_in_code.send(db, user_id, "48190x", 10)
    with pytest.raises(ValueError):
        sign_in_code.send(db, "not-a-uuid", "481902", 10)
    db.execute("UPDATE users SET active = false WHERE id = %s", (user_id,))
    with pytest.raises(sign_in_code.CodeEmailRefused) as refused:
        sign_in_code.send(db, user_id, "481902", 10)
    assert refused.value.status == 404 and sent == []
