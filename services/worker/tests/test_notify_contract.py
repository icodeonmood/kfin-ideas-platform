"""The L-NOTIFY entry points' contract (BLD-A180, BLD-A200): other lanes call `notify.post` and `notify.resolve`
from their own code; the signatures do not change. What they do in the database is in tests/test_notify.py."""

from __future__ import annotations

import inspect
from typing import Any

import pytest

import notify
from notify import Action, NotifyError, post, resolve
from onepc.enums import INBOX_KIND


class _NoConn:
    def execute(self, *_: Any, **__: Any) -> Any:
        raise AssertionError("a call with no one to tell never touches the database")


U1 = "6f1c2a9e-3b7d-4e0a-9c55-2f4b8d1e7a01"


def test_the_signature_is_the_published_contract() -> None:
    params = list(inspect.signature(post).parameters)
    assert params == [
        "conn", "kind", "recipients", "idea_id", "sender", "needs_you", "due_at", "actions", "refs", "dedupe_key",
    ]  # fmt: skip
    assert {p for p, v in inspect.signature(post).parameters.items() if v.kind is v.KEYWORD_ONLY} == set(
        params[3:]
    )


def test_every_inbox_kind_from_the_contract_is_accepted() -> None:
    assert {
        "questions", "teamup_request", "teamup_answer", "decision", "decision_reversed", "desk_merge",
        "worth_revised", "stage_moved", "build_ask", "mention", "crew_joined", "comment", "draft_kept",
        "sent_to_desk", "answer_reminder", "detail_hidden_by_desk",
    } == notify.INBOX_KINDS  # fmt: skip
    # Every E-ENUMS.inbox kind is one; L-HIDE/7's kind may arrive in contracts/1pc/enums.json with lane C's c/hide
    # (BLD-A205). No induction kind: a new One gets no Inbox item at launch (BLD-A186).
    assert set(INBOX_KIND) <= notify.INBOX_KINDS
    assert notify.INBOX_KINDS - set(INBOX_KIND) <= {"detail_hidden_by_desk"}
    assert not any("induct" in k or k.startswith("one") for k in notify.INBOX_KINDS)
    for (
        kind
    ) in notify.INBOX_KINDS:  # the sender is never a recipient, so nobody is left and nothing is written
        assert post(_NoConn(), kind, [U1], sender=U1).ids == []  # type: ignore[arg-type]


def test_resolve_takes_a_dedupe_key_and_optional_recipients() -> None:
    """BLD-A180: lane B resolves "qs:<set_id>" when the answers are sent; lane F its request keys."""
    params = inspect.signature(resolve).parameters
    assert list(params) == ["conn", "dedupe_key", "recipients"]
    assert (
        params["recipients"].kind is params["recipients"].KEYWORD_ONLY
        and params["recipients"].default is None
    )
    assert resolve(_NoConn(), "teamup_request:abc", recipients=[]) == 0  # type: ignore[arg-type]
    with pytest.raises(NotifyError):
        resolve(_NoConn(), "free text with spaces")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "call",
    [
        lambda: post(_NoConn(), "no_such_kind", ["u-1"]),  # type: ignore[arg-type]
        lambda: post(_NoConn(), "decision", [""]),  # type: ignore[arg-type]
        lambda: post(_NoConn(), "decision", ["u-1"]),  # type: ignore[arg-type]
        lambda: post(_NoConn(), "decision", [U1], refs={"reason": ["free", "text"]}),  # type: ignore[arg-type, dict-item]
        lambda: post(_NoConn(), "decision", [U1], refs={"reason": "Not-now"}),  # type: ignore[arg-type]
        lambda: post(_NoConn(), "teamup_answer", [U1], refs={"answer": "declined because it overlaps"}),  # type: ignore[arg-type]
        lambda: post(_NoConn(), "decision", [U1], actions=[Action("Open")]),  # type: ignore[arg-type]
        lambda: post(_NoConn(), "decision", [U1], dedupe_key="no spaces allowed"),  # type: ignore[arg-type]
        lambda: post(_NoConn(), "detail_hidden_by_desk", [U1], refs={"count": 1}),  # type: ignore[arg-type]
    ],
)
def test_bad_calls_are_refused(call: Any) -> None:
    with pytest.raises(NotifyError):
        call()
