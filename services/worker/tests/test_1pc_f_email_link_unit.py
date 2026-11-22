"""L-NOTIFY, L-INBOX, S-H2B, BLD-F099 without a database: the lead's `teamup_request` email says "Read the note and
answer in the app", and its "Answer the request" button opens the in-app item its answers are on
(`/inbox/<item id>`), never the idea's conversation, which can't answer it. The item posts its answers as bare ops
(lane F's `tell_lead`), so the rule is: when an item's own buttons, as posted, are all ops, the email's
`links.action` is its in-app item, or the Inbox when there is none. An item with a `to` keeps its link, and the
in-app item is unchanged. Words come from the seed template; the idea is a synthetic stand-in; the link carries only
the item id."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from comms import templates
from notify import render

SEED = Path(__file__).resolve().parents[3] / "seed" / "company-repo"
BASE = "https://ideas.example.test"
REF = "IDEA-2026-001481"
RID = "5b0e7a3c-2d41-4f6e-9a18-0c7d3e2b9f11"
NOW = dt.datetime(2026, 11, 22, 12, 0, tzinfo=dt.UTC)
IDEA = {
    "uuid": "0f3c9a52-7e1d-4b8a-a6c2-91d4e5f60718",
    "ref": REF,
    "title": "Investors call to ask why a redemption was rejected",
    "status": "with_review_desk",
}

# The lead's answers as `tell_lead` posts them: bare ops, no `to` (as stored, None keys dropped).
ANSWERS = [
    {"label": "Decline", "style": "text", "op": "decline"},
    {"label": "Team up only", "style": "line", "op": "team_only"},
    {"label": "Merge it", "style": "primary", "op": "merge"},
]
SAY_HELLO = [{"label": "Say hello", "style": "primary", "to": f"/ideas/{REF}/conversation#say-hello"}]


class _NoRows:
    """A connection that finds nothing: no sender, no reader."""

    def execute(self, *_: Any, **__: Any) -> Any:
        return self

    def fetchone(self) -> None:
        return None

    def fetchall(self) -> list[Any]:
        return []


@pytest.fixture(autouse=True)
def _seed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(render, "load", lambda name: templates._load(SEED, name))
    monkeypatch.setattr(render, "_idea", lambda _conn, _uuid: dict(IDEA))
    monkeypatch.setattr(render, "get_settings", lambda: SimpleNamespace(app_base_url=f"{BASE}/"))


def _row(kind: str, actions: list[dict[str, str]], refs: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": 903,  # the email row's own id: never the link (an email row is not in the Inbox)
        "kind": kind,
        "user_id": "u-lead",
        "idea_uuid": IDEA["uuid"],
        "payload": refs,
        "actions": actions,
        "created_at": NOW,
        "needs_you": kind == "teamup_request",
        "resolved_at": None,
        "read_at": None,
        "archived_at": None,
    }


def _email_link(row: dict[str, Any], item_id: int | None) -> str:
    _, data = render.variables(_NoRows(), row, "u-lead", NOW, absolute=True, item_id=item_id)  # type: ignore[arg-type]
    return str(data["links"]["action"])


REQUEST = {"request_id": RID, "request": "teamup", "brought": 1}


def test_L_NOTIFY_L_INBOX_S_H2B_BLD_F099_the_request_email_opens_the_in_app_item_with_its_answers() -> None:
    row = _row("teamup_request", ANSWERS, REQUEST)
    assert _email_link(row, 57) == f"{BASE}/inbox/57"
    # The template's button is that link, and the email carries no note and no words (L-NOTIFY/3).
    tpl = templates._load(SEED, "inbox/teamup_request")
    assert "[Answer the request]({{links.action}})" in tpl.body


def test_L_INBOX_S_H2B_BLD_F099_the_in_app_item_keeps_its_buttons_and_links() -> None:
    """Only the email changes: the in-app item still lists the answers and "Open the conversation"."""
    row = _row("teamup_request", ANSWERS, REQUEST)
    item = render.item(_NoRows(), row, "u-lead", NOW)  # type: ignore[arg-type]
    assert [(a["label"], a.get("op"), a.get("to")) for a in item["actions"]] == [
        ("Decline", "decline", None),
        ("Team up only", "team_only", None),
        ("Open the conversation", None, f"/ideas/{REF}/conversation"),
        ("Merge it", "merge", None),
    ]
    _, data = render.variables(_NoRows(), row, "u-lead", NOW)  # type: ignore[arg-type]
    assert data["links"]["action"] == f"/ideas/{REF}/conversation"  # the in-app path, as before


def test_L_NOTIFY_BLD_F099_an_item_with_a_to_keeps_todays_email_link() -> None:
    row = _row("teamup_answer", SAY_HELLO, {"request_id": RID, "request": "teamup", "answer": "team_only"})
    assert _email_link(row, 57) == f"{BASE}/ideas/{REF}/conversation#say-hello"


def test_L_NOTIFY_L_INBOX_BLD_F099_answers_with_no_in_app_item_open_the_inbox() -> None:
    row = _row("teamup_request", ANSWERS, REQUEST)
    assert _email_link(row, None) == f"{BASE}/inbox"
