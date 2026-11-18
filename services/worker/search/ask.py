"""L-SEARCH/4, "ask in your own words" (C-SEARCH ask): the seam only.

Turning a question into filters is in the drop order for launch (docs/SHIP_PLAN_1PC.md §4), so `interpret` always
answers None and search treats the question as plain words. When it is built it must go through the gateway
(non-negotiables 1 and 2) and return the filters it read plus the one-sentence answer.
"""

from __future__ import annotations

from typing import Any


def interpret(question: str) -> dict[str, Any] | None:
    """The filters a question stands for, and its one-sentence answer; None until "ask" is built (BLD-F040)."""
    del question
    return None
