"""L-HIDE.rules/7 and /8: the sharer's notice when the review desk hides a detail (`detail_hidden_by_desk`,
BLD-C063), on both sides of the guard, without the stack. The notice carries IDs only, never the hidden value."""

from __future__ import annotations

from typing import Any

import pytest

import notify
from hide import desk

IDEA = {
    "id": "0b6f1c1e-1111-4a4a-8a8a-000000000001",
    "sharer_user_id": "0b6f1c1e-2222-4a4a-8a8a-000000000002",
}
REVIEWER = "0b6f1c1e-3333-4a4a-8a8a-000000000003"


@pytest.fixture
def posted(monkeypatch: pytest.MonkeyPatch) -> list[tuple[tuple[Any, ...], dict[str, Any]]]:
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def record(*a: Any, **kw: Any) -> notify.Posted:
        calls.append((a, kw))
        return notify.Posted()

    monkeypatch.setattr(notify, "post", record)
    return calls


def test_l_hide_rules_7_kind_absent_means_audit_only(
    monkeypatch: pytest.MonkeyPatch, posted: list[Any]
) -> None:
    monkeypatch.setattr(notify, "INBOX_KINDS", frozenset(notify.INBOX_KINDS - {desk.NOTIFY_KIND}))
    assert desk._notify_sharer(object(), IDEA, REVIEWER) is False  # type: ignore[arg-type]
    assert posted == []


def test_l_hide_rules_8_kind_present_posts_once_with_ids_only(
    monkeypatch: pytest.MonkeyPatch, posted: list[Any]
) -> None:
    monkeypatch.setattr(notify, "INBOX_KINDS", frozenset(notify.INBOX_KINDS | {desk.NOTIFY_KIND}))
    conn = object()
    assert desk._notify_sharer(conn, IDEA, REVIEWER) is True  # type: ignore[arg-type]
    assert len(posted) == 1
    args, kwargs = posted[0]
    assert args == (conn, "detail_hidden_by_desk", [IDEA["sharer_user_id"]])
    assert kwargs == {
        "idea_id": IDEA["id"],
        "sender": REVIEWER,
    }  # not needs_you, no refs: no value can ride along


def test_l_hide_rules_7_a_sharer_who_is_also_the_reviewer_gets_no_notice(
    monkeypatch: pytest.MonkeyPatch, posted: list[Any]
) -> None:
    monkeypatch.setattr(notify, "INBOX_KINDS", frozenset(notify.INBOX_KINDS | {desk.NOTIFY_KIND}))
    assert desk._notify_sharer(object(), IDEA, str(IDEA["sharer_user_id"])) is False  # type: ignore[arg-type]
    assert desk._notify_sharer(object(), {**IDEA, "sharer_user_id": None}, REVIEWER) is False  # type: ignore[arg-type]
    assert posted == []
