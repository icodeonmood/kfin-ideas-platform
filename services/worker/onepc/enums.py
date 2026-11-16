"""E-ENUMS wire values for Python, read from `onepc/enums.json`: a copy of `contracts/1pc/enums.json` written by
`cd apps/web && npm run sync:shared` (the worker image carries no contracts/ folder; a test keeps the copy equal to
the source, and the source equal to the cut-over migration's CHECK constraints).

Never write a wire value by hand elsewhere: use `values("idea_status")` or the named tuples below.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

ENUMS_FILE = Path(__file__).with_name("enums.json")


@cache
def _data() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(ENUMS_FILE.read_text(encoding="utf-8"))
    return data


def names() -> tuple[str, ...]:
    return tuple(_data()["enums"])


def values(name: str) -> tuple[Any, ...]:
    """The enum's wire values in the pack's order. KeyError for an unknown name (fail loudly)."""
    return tuple(_data()["enums"][name]["values"])


def labels(name: str) -> dict[str, str]:
    return dict(_data()["enums"][name].get("labels") or {})


def is_value(name: str, value: object) -> bool:
    return value in values(name)


def db_checks() -> dict[str, tuple[str, ...]]:
    """Each database CHECK ("table.column") and the enum(s) whose values it must hold."""
    return {k: tuple(v) for k, v in _data()["db_checks"].items()}


def db_values_outside_the_pack() -> dict[str, tuple[str, ...]]:
    """Old values a reused column keeps after the cut-over, until Monday's cleanup decides each."""
    return {k: tuple(v) for k, v in _data()["db_values_outside_the_pack"].items()}


def expected_check_values(key: str) -> frozenset[str]:
    out = {str(v) for name in db_checks()[key] for v in values(name)}
    return frozenset(out | set(db_values_outside_the_pack().get(key, ())))


IDEA_STATUS = values("idea_status")
CLOSED_STATUSES: tuple[str, ...] = tuple(_data()["enums"]["idea_status"]["groups"]["closed"])
PICKED_AND_BUILDING: tuple[str, ...] = tuple(_data()["enums"]["idea_status"]["groups"]["picked_and_building"])
STAGE = values("stage")
KIND = values("kind")
BRINGS = values("brings")
PART = values("part")
DECISION = values("decision")
RETURN_IN = values("return_in")
WINDOW_STATE = values("window_state")
QUESTION_SET_STATE = values("question_set_state")
TIME_TO_ANSWER = values("time_to_answer")
TEAMUP_STATE = values("teamup_state")
MERGE_REQUEST_STATE = values("merge_request_state")
FILE_STATE = values("file_state")
LINK_STATE = values("link_state")
HIDDEN_KIND = values("hidden_kind")
SHOW_REASON = values("show_reason")
DRAFT_PART = values("draft_part")
PART_STATE = values("part_state")
CHANNEL = values("channel")
DRAFT_STEP = values("draft_step")
INBOX_KIND = values("inbox_kind")
ROLE = values("role")
TIER_NAME: dict[int, str] = {int(k): v for k, v in labels("tier").items()}
CLOCK_KIND = values("clock_kind")
