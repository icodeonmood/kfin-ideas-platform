"""L-INBOX.rules/6, C-INBOX-READER (BLD-A220): an Inbox item links to its idea's conversation once. An action that
already goes to the conversation, at a place on it (`#say-hello`) or with a query, is that link; no second
"Open the conversation" is added beside it. No database: `resolved_actions` reads the row and the idea it is given.
Synthetic references only."""

from __future__ import annotations

from typing import Any

from notify.render import resolved_actions

REF = "IDEA-2026-000123"
IDEA: dict[str, Any] = {"ref": REF, "status": "being_built", "uuid": "00000000-0000-4000-8000-000000000123"}


def _labels(actions: list[dict[str, Any]]) -> list[tuple[str, str]]:
    return [(a["label"], a.get("to", "")) for a in actions]


def test_L_INBOX_6_J_TRACK_6_say_hello_on_the_conversation_gets_no_second_conversation_link() -> None:
    row = {
        "id": 41,
        "kind": "teamup_answer",
        "payload": {},
        "actions": [{"label": "Say hello", "to": f"/ideas/{REF}/conversation#say-hello", "style": "primary"}],
    }
    assert _labels(resolved_actions(row, IDEA)) == [("Say hello", f"/ideas/{REF}/conversation#say-hello")]


def test_L_INBOX_6_a_conversation_link_with_a_query_is_the_conversation_too() -> None:
    row = {
        "id": 42,
        "kind": "mention",
        "payload": {},
        "actions": [
            {"label": "Open the conversation", "to": f"/ideas/{REF}/conversation?at=m7", "style": "primary"}
        ],
    }
    assert [label for label, _ in _labels(resolved_actions(row, IDEA))] == ["Open the conversation"]


def test_L_INBOX_6_an_item_that_goes_elsewhere_still_gets_open_the_conversation_before_its_primary() -> None:
    row = {
        "id": 43,
        "kind": "teamup_answer",
        "payload": {},
        "actions": [{"label": "Open the idea", "to": f"/ideas/{REF}#say-hello", "style": "primary"}],
    }
    assert _labels(resolved_actions(row, IDEA)) == [
        ("Open the conversation", f"/ideas/{REF}/conversation"),
        ("Open the idea", f"/ideas/{REF}#say-hello"),
    ]
