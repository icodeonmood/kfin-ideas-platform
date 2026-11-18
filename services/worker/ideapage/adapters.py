"""Thin adapters to other lanes' worker modules (SHIP_PLAN_1PC §5a), so a change on their side touches one file.

- Answers under their parts (L-QUESTIONS.answer/5, S-06.layout/5): lane B's `desk.asking.answers_by_part`, which is
  on `main`. The import guard stays only so that a missing module fails soft (the page shows no answers under the
  parts); nothing is read twice and lane E keeps no copy of the questions' or answers' logic.
- Whether similar ideas could be checked (L-SIMILAR.failure, C-TRACK's "Checked" line): lane C's c/similar keeps the
  latest matching run in `similar_runs` (its retries after sharing write only there), read through its
  `similar.matching.last_run`; before that table is on main, lane C's check records the outcome in
  `ideas.similar_check`. Only the run's state is read here, never its `found`: counts come from the visible
  `similar_links` (`read.similar_count`).
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any, Literal

from core.db import Conn

AnswersByPart = Callable[[Conn, Any], dict[str, list[dict[str, Any]]]]
LastRun = Callable[[Conn, str], dict[str, Any] | None]
SimilarStatus = Literal["none", "done", "failed"]


def _lane_b_answers() -> AnswersByPart | None:
    try:
        module = importlib.import_module("desk.asking")
    except ImportError:
        return None
    fn = getattr(module, "answers_by_part", None)
    return fn if callable(fn) else None


def answers_by_part(conn: Conn, idea_uuid: str) -> dict[str, list[dict[str, Any]]]:
    """Every question sent on the idea under its part, with its answer once sent, from lane B's
    `desk.asking.answers_by_part` (its shape: `question`, `asked_by` (a first name), `answer`, `answered_at`,
    `files`, …). Empty only if that module cannot be imported: the guard fails soft, it is not a pending seam."""
    fn = _lane_b_answers()
    return fn(conn, idea_uuid) if fn is not None else {}


def _lane_c_last_run() -> LastRun | None:
    try:
        module = importlib.import_module("similar.matching")
    except ImportError:
        return None
    fn = getattr(module, "last_run", None)
    return fn if callable(fn) else None


def similar_status(conn: Conn, idea_uuid: str) -> SimilarStatus:
    """Whether similar ideas were checked for this idea (L-SIMILAR.failure): "done", "failed", or "none" when nothing
    says either. Lane C's `similar_runs` row wins when the table is there and has one (through c/similar's
    `similar.matching.last_run`, or plain SQL while that module is not here); otherwise `ideas.similar_check`."""
    here = conn.execute("SELECT to_regclass('similar_runs') IS NOT NULL AS here").fetchone()
    if here is not None and here["here"]:
        last_run = _lane_c_last_run()
        if last_run is not None:
            run = last_run(conn, idea_uuid)
        else:
            row = conn.execute("SELECT state FROM similar_runs WHERE idea_uuid = %s", (idea_uuid,)).fetchone()
            run = dict(row) if row else None
        state = run.get("state") if run else None
        if state == "done":
            return "done"
        if state == "failed":
            return "failed"
    idea = conn.execute("SELECT similar_check FROM ideas WHERE id = %s", (idea_uuid,)).fetchone()
    check = idea["similar_check"] if idea else None
    if check == "done":
        return "done"
    if check == "failed":
        return "failed"
    return "none"
