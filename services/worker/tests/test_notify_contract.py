"""The L-NOTIFY entry point's contract (BLD-A180): other lanes call `notify.post` from their own code now; the
body lands after lane E's cut-over without the signature changing."""

from __future__ import annotations

import inspect
from typing import Any

import pytest

import notify
from notify import Action, NotifyError, post


class _NoConn:
    def execute(self, *_: Any, **__: Any) -> Any:
        raise AssertionError("the stub never touches the database")


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
        "sent_to_desk", "answer_reminder",
    } == notify.INBOX_KINDS  # fmt: skip
    for kind in notify.INBOX_KINDS:
        assert post(_NoConn(), kind, ["u-1"]).ids == []  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "call",
    [
        lambda: post(_NoConn(), "no_such_kind", ["u-1"]),  # type: ignore[arg-type]
        lambda: post(_NoConn(), "decision", [""]),  # type: ignore[arg-type]
        lambda: post(_NoConn(), "decision", ["u-1"], refs={"reason": ["free", "text"]}),  # type: ignore[arg-type, dict-item]
        lambda: post(_NoConn(), "decision", ["u-1"], actions=[Action("Open")]),  # type: ignore[arg-type]
    ],
)
def test_bad_calls_are_refused(call: Any) -> None:
    with pytest.raises(NotifyError):
        call()
