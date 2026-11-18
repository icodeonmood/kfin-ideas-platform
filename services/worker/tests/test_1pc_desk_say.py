"""The desk's conversation lines go only through lane F's `convo.post` (BLD-B249, L-CONVO), without a database:
`desk.adapters.say` hands every argument on as it is, and has no direct insert to fall back on."""

from __future__ import annotations

import datetime as dt
import sys
from typing import Any, cast

import pytest

from core.db import Conn
from desk import adapters

IDEA = "6f1d2c3b-4a5e-4f60-8172-93a4b5c6d7e8"
SET = "8d2f4b6a-1c3e-4a5b-9d7f-2e6c8a0b4d13"
MEERA = "6c1f6a0e-1b8e-4d0a-9a51-0d6f3e2a1b05"


class _NoSql:
    """A connection that fails the test if the desk writes anything itself."""

    def execute(self, *_: Any, **__: Any) -> None:
        raise AssertionError("the desk wrote to the database itself")


def test_L_CONVO_say_hands_every_line_to_convo_post(monkeypatch: pytest.MonkeyPatch) -> None:
    posted: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def post(*args: Any, **kwargs: Any) -> str:
        posted.append((args, kwargs))
        return "entry-1"

    monkeypatch.setattr("convo.post", post)
    conn = cast(Conn, _NoSql())
    at = dt.datetime(2026, 11, 16, 11, 20, tzinfo=dt.timezone(dt.timedelta(hours=5, minutes=30)))
    adapters.say(conn, IDEA, "desk.asked", author_user_id=MEERA, payload={"set_id": SET, "count": 3},
                 question_set_id=SET, entry_type="questions", at=at)  # fmt: skip
    assert posted == [
        (
            (conn, IDEA, "desk.asked"),
            {"author_user_id": MEERA, "author_code": None, "payload": {"set_id": SET, "count": 3},
             "question_set_id": SET, "entry_type": "questions", "at": at},
        )
    ]  # fmt: skip


def test_L_CONVO_say_has_no_direct_insert_when_convo_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "convo", None)  # as if lane F's writer were not there
    with pytest.raises(ImportError):
        adapters.say(cast(Conn, _NoSql()), IDEA, "desk.opened")
