"""Thin adapters to other lanes' worker modules (SHIP_PLAN_1PC §5a), so a change on their side touches one file.

- Answers under their parts (L-QUESTIONS.answer/5, S-06.layout/5): lane B's `desk.asking.answers_by_part`. Until
  lane B's branch is on `main` the module is not there and the page shows no answers under the parts; nothing is
  read twice and lane E keeps no copy of the questions' or answers' logic.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any

from core.db import Conn

AnswersByPart = Callable[[Conn, Any], dict[str, list[dict[str, Any]]]]


def _lane_b_answers() -> AnswersByPart | None:
    try:
        module = importlib.import_module("desk.asking")
    except ImportError:
        return None
    fn = getattr(module, "answers_by_part", None)
    return fn if callable(fn) else None


def answers_by_part(conn: Conn, idea_uuid: str) -> dict[str, list[dict[str, Any]]]:
    """Every question sent on the idea under its part, with its answer once sent (lane B's shape: `question`,
    `asked_by` (a first name), `answer`, `answered_at`, `files`, …). Empty until lane B's module is importable."""
    fn = _lane_b_answers()
    return fn(conn, idea_uuid) if fn is not None else {}
