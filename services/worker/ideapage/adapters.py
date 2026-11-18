"""Thin adapters to other lanes' worker modules (SHIP_PLAN_1PC §5a), so a change on their side touches one file.

- Answers under their parts (L-QUESTIONS.answer/5, S-06.layout/5): lane B's `desk.asking.answers_by_part`. Until
  lane B's branch is on `main` the module is not there and the page shows no answers under the parts; nothing is
  read twice and lane E keeps no copy of the questions' or answers' logic.
- An idea's lead (L-TEAMUP.rules/10): lane F's `teamup.store.lead_code`, the live crew-lead row, else the sharer. Until
  lane F's module is importable the lead is the sharer, which is what an idea nobody handed over reads as anyway.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any

from core.db import Conn

AnswersByPart = Callable[[Conn, Any], dict[str, list[dict[str, Any]]]]
LeadCode = Callable[[Conn, dict[str, Any]], str]


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


def _lane_f_lead_code() -> LeadCode | None:
    try:
        module = importlib.import_module("teamup.store")
    except ImportError:
        return None
    fn = getattr(module, "lead_code", None)
    return fn if callable(fn) else None


def lead_code(conn: Conn, idea: dict[str, Any]) -> str:
    """The idea's lead now (`idea` needs `id` and `contributor_code`): its live `lead` crew row, so a lead who was
    handed over is the one named, else the person who shared it. The sharer until lane F's module is importable."""
    fn = _lane_f_lead_code()
    return fn(conn, idea) if fn is not None else str(idea["contributor_code"])
