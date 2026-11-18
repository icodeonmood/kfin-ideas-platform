"""S-ADMIN, J-ONE step 1, L-DECIDE.rules/6 (DEC-111, BLD-A226): the admin page's picked ideas carry who asked to
join the build team, oldest first, from lane B's `desk.join_build.asks_for_idea` as it returns them, with the page's
day label. No database: the idea list and lane B's read are stubbed. Synthetic people only (non-negotiable 11)."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from programme import view

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
NOW = dt.datetime(2026, 11, 18, 11, 0, tzinfo=IST)
ASKED = "2026-11-12T09:30:00+05:30"
LATER = "2026-11-17T23:10:00+05:30"
UUID_A = "6f1c2a7e-0d0b-4a55-9c3e-3b9a6d1e0a01"
UUID_B = "6f1c2a7e-0d0b-4a55-9c3e-3b9a6d1e0a02"


class _Rows:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def fetchall(self) -> list[dict[str, Any]]:
        return self._rows


class _Conn:
    """Answers `_ideas`' one query by status: two picked ideas, nothing else."""

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> _Rows:
        assert "FROM ideas i" in sql
        if params == ("picked",):
            return _Rows([
                {"id": UUID_A, "idea_id": "IDEA-2026-000123", "title": "Mandate checks", "team": None,
                 "lead": None, "status_changed_at": dt.datetime(2026, 11, 11, 10, 0, tzinfo=IST)},
                {"id": UUID_B, "idea_id": "IDEA-2026-000124", "title": "Branch queue tokens", "team": None,
                 "lead": None, "status_changed_at": None},
            ])  # fmt: skip
        return _Rows([])


@pytest.fixture
def stubbed(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    asked_for: list[str] = []
    asks = {
        UUID_A: [
            {"user_id": "0b7e6a52-6c1a-4e0e-8f43-000000000001", "name": "Tanvi Rao", "asked_at": ASKED},
            {"user_id": "0b7e6a52-6c1a-4e0e-8f43-000000000002", "name": "Kabir Sethi", "asked_at": LATER},
        ],
        UUID_B: [],
    }

    def asks_for_idea(conn: Any, idea_uuid: str) -> list[dict[str, Any]]:
        asked_for.append(idea_uuid)
        return [dict(a) for a in asks[idea_uuid]]

    monkeypatch.setattr(view, "roles", lambda conn, user_id: {"admin"})
    monkeypatch.setattr(view.join_build, "asks_for_idea", asks_for_idea)
    monkeypatch.setattr(view.wall, "removals", lambda conn: [])
    monkeypatch.setattr(view.impact, "due", lambda conn, now: [])
    monkeypatch.setattr(view.impact, "entered", lambda conn: [])
    monkeypatch.setattr(view.ones, "list_ones", lambda conn: [])
    return asked_for


def test_s_admin_j_one_1_l_decide_6_picked_ideas_carry_asked_to_join_oldest_first(stubbed: list[str]) -> None:
    out = view.admin_view(_Conn(), "0b7e6a52-6c1a-4e0e-8f43-0000000000ad", NOW)  # type: ignore[arg-type]
    first, second = out["picked"]
    assert first["asked_to_join"] == [
        {"user_id": "0b7e6a52-6c1a-4e0e-8f43-000000000001", "name": "Tanvi Rao", "asked_at": ASKED,
         "asked_label": "12 Nov 2026"},
        {"user_id": "0b7e6a52-6c1a-4e0e-8f43-000000000002", "name": "Kabir Sethi", "asked_at": LATER,
         "asked_label": "17 Nov 2026"},
    ]  # fmt: skip
    assert second["asked_to_join"] == []
    # lane B's read is asked once per picked idea, by the idea's id; the id itself does not reach the page
    assert stubbed == [UUID_A, UUID_B]
    assert set(first) == {"idea_ref", "title", "team", "lead", "since", "since_label", "asked_to_join"}
    # names and times only: no email or anything else about the person (S-ADMIN privacy)
    assert all(set(a) == {"user_id", "name", "asked_at", "asked_label"} for a in first["asked_to_join"])
    # the other lists keep their shape
    assert out["being_built"] == [] and out["shipped"] == []


def test_s_admin_l_decide_6_the_review_desk_sees_no_asks(
    stubbed: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(view, "roles", lambda conn, user_id: {"reviewer"})
    out = view.admin_view(_Conn(), "0b7e6a52-6c1a-4e0e-8f43-0000000000de", NOW)  # type: ignore[arg-type]
    assert set(out) == {"can", "off_wall"} and stubbed == []
