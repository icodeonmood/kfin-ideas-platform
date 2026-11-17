"""L-QUESTIONS.clock/2, L-DECIDE.rules/7, L-COMMITTEE.rules/6: lane A's job runner calls lane B's one sweep every
5 minutes (`desk.clocks`), so answer reminders, Not now returns and window expiry happen with nobody on a screen."""

from __future__ import annotations

from typing import Any

import pytest

from jobs import handlers
from jobs.runner import HANDLERS
from jobs.schedule import EVERY


def test_L_QUESTIONS_clock_2_the_schedule_runs_the_desk_sweep_every_5_minutes() -> None:
    assert EVERY["desk.clocks"] == 5
    assert HANDLERS["desk.clocks"] is handlers.desk_clocks


def test_L_QUESTIONS_clock_2_the_handler_calls_run_due_on_the_runners_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from desk import clocks

    calls: list[tuple[Any, ...]] = []

    def run_due(conn: Any, at: Any = None) -> dict[str, int]:
        calls.append((conn, at))
        return {"returned": 0, "windows_closed": 0, "reminded": 0}

    monkeypatch.setattr(clocks, "run_due", run_due)
    conn = object()
    handlers.desk_clocks(conn, {})  # type: ignore[arg-type]
    assert calls == [(conn, None)]
