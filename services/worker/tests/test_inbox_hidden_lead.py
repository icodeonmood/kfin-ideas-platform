"""DEC-104 and BLD-A196 without a database: a requester the lead declined never reads the name or users.id of a
lead who hid their name from the Wall, or has left, in the Inbox item, its JSON or the email. The lead is read by
lane C's rule (`similar.preview.person_refs`, BLD-F029): "A colleague" with no initials and an opaque `p…` id, and
the sender reads "The lead" from the template. A lead who shows their name is named; an approved requester is on
the crew and reads the name. The connection answers the reads `notify.render` makes from synthetic rows; the same
cases against the real tables run in CI in tests/test_notify.py."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

import pytest

from comms import templates
from notify import render

SEED = Path(__file__).resolve().parents[3] / "seed" / "company-repo"
NOW = dt.datetime(2026, 11, 18, 12, 0, tzinfo=dt.UTC)
LEAD = "0b7e2c41-9d3a-4f58-8e16-5a2c7d9f3b10"  # Ravi Nair, the idea's lead (synthetic)
ASKER = "6f1c2a9e-3b7d-4e0a-9c55-2f4b8d1e7a01"  # Kavya Menon, who asked (synthetic)
IDEA = "c3d9a1f2-4b6e-4c8a-9f21-7e5d3b2a1c90"
LEAD_CODE = "CTR-7a1b2c"
REQUEST = "5b0e7a3c-2d41-4f6e-9a18-0c7d3e2b9f11"


class _Rows:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def fetchone(self) -> dict[str, Any] | None:
        return self.rows[0] if self.rows else None

    def fetchall(self) -> list[dict[str, Any]]:
        return self.rows


class _Conn:
    """The reads `notify.render` makes, answered from synthetic rows. `show` and `active` are the lead's
    `person_settings.show_name_on_wall` and `users.active`."""

    def __init__(self, *, show: bool, active: bool) -> None:
        self.show, self.active = show, active
        self.users = {LEAD: ("Ravi Nair", "Ravi"), ASKER: ("Kavya Menon", "Kavya")}

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> _Rows:
        if "FROM ideas WHERE id" in sql:
            return _Rows([{"id": IDEA, "idea_id": "IDEA-2026-000900", "title": "Rejection SMS codes confuse investors",
                           "status": "with_review_desk", "decide_by": None, "contributor_code": LEAD_CODE}])  # fmt: skip
        if "person_settings" in sql:  # lane C's person_refs
            return _Rows([{"contributor_code": LEAD_CODE, "id": LEAD, "name": "Ravi Nair", "first_name": "Ravi",
                           "area": "Investor service", "location": "Hyderabad", "active": self.active,
                           "show_name": self.show}])  # fmt: skip
        if "FROM contributor_map WHERE user_id" in sql:
            return _Rows([{"contributor_code": LEAD_CODE}] if params[0] == LEAD else [])
        if "FROM users WHERE id" in sql:
            name = self.users.get(str(params[0]))
            return _Rows([{"id": params[0], "name": name[0], "first_name": name[1]}] if name else [])
        return _Rows([])


@pytest.fixture(autouse=True)
def _seed_templates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(render, "load", lambda name: templates._load(SEED, name))


def _row(answer: str, channel: str = "in_app") -> dict[str, Any]:
    return {
        "id": 77,
        "user_id": ASKER,
        "channel": channel,
        "kind": "teamup_answer",
        "payload": {"request_id": REQUEST, "request": "teamup", "answer": answer, "has_reason": True},
        "actions": [],
        "from_user_id": LEAD,
        "idea_uuid": IDEA,
        "created_at": NOW,
        "needs_you": False,
        "resolved_at": None,
        "read_at": None,
        "archived_at": None,
        "dedupe_key": None,
    }


def _read(conn: _Conn, answer: str) -> tuple[dict[str, Any], str]:
    item = render.item(conn, _row(answer), ASKER, NOW)  # type: ignore[arg-type]
    mail = render.email(conn, _row(answer, "email"), NOW)  # type: ignore[arg-type]
    return item, "\n".join((mail.subject, mail.text, mail.html))


@pytest.mark.parametrize(
    ("case", "show", "active"), [("hid their name", False, True), ("has left", True, False)]
)
def test_DEC_104_a_declined_requester_never_reads_a_hidden_or_departed_lead(
    case: str, show: bool, active: bool
) -> None:
    item, mail = _read(_Conn(show=show, active=active), "decline")
    assert item["from"]["name"] == "A colleague" and item["from"]["initials"] == "", case
    assert item["from"]["id"].startswith("p") and item["from"]["id"] != LEAD, case
    assert item["body"]["sender"] == "The lead", case
    assert (
        f"{item['body']['sender']} {item['line']}" == "The lead declined your team-up request, with a reason"
    )
    assert (
        "The lead answered your team-up request" in mail and "The lead declined your team-up request" in mail
    )
    everything = json.dumps(item, ensure_ascii=False) + mail
    for leak in (LEAD, "Ravi"):
        assert leak not in everything, (case, leak)


def test_DEC_104_a_declined_requester_reads_a_lead_who_shows_their_name() -> None:
    item, mail = _read(_Conn(show=True, active=True), "decline")
    assert item["from"] == {
        "id": LEAD,
        "name": "Ravi Nair",
        "first_name": "Ravi",
        "initials": "RN",
        "role_label": "",
    }
    assert item["body"]["sender"] == "Ravi Nair"
    assert "Ravi Nair answered your team-up request" in mail


@pytest.mark.parametrize("answer", ["team_only", "merge"])
def test_DEC_104_an_approved_requester_is_on_the_crew_and_reads_the_name(answer: str) -> None:
    item, mail = _read(_Conn(show=False, active=True), answer)
    assert item["from"]["id"] == LEAD and item["body"]["sender"] == "Ravi Nair"
    assert item["line"] == "approved your team-up request"
    assert item["body"]["note"] == "You’re on Ravi’s crew now."
    assert "Ravi Nair answered your team-up request" in mail
