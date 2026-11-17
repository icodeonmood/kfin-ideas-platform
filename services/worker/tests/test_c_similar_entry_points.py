"""The two L-SIMILAR entry points other lane C modules import (BLD-C093): c/draft's `draft/adapters.py` calls
`similar_for`, c/sort-submit's `submit/adapters.py` calls `match_shared`. A rename or a signature change breaks this
branch, not theirs."""

from __future__ import annotations

import inspect

import similar
from similar import match_shared, similar_for


def test_bld_c093_entry_points_keep_their_names_and_signatures() -> None:
    assert set(similar.__all__) >= {"similar_for", "match_shared"}

    sig = inspect.signature(similar_for)
    assert list(sig.parameters) == ["conn", "idea_uuid", "title", "summary"]
    assert all(p.kind is p.POSITIONAL_OR_KEYWORD for p in sig.parameters.values())
    assert sig.return_annotation == "list[dict[str, Any]] | None"

    sig = inspect.signature(match_shared)
    assert list(sig.parameters) == ["conn", "idea_uuid", "found_while"]
    assert sig.parameters["found_while"].kind is inspect.Parameter.KEYWORD_ONLY
    assert sig.return_annotation == "int"
