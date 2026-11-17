"""Similar ideas (L-SIMILAR) and the idea preview (A-API.idea-preview), read from the database alone (DEC-106).

- `preview.idea_preview`: the IdeaPreview another person may see of a shared idea. Masked text only, never the
  sharer's raw words (DEC-104, non-negotiable 7); `compare` for the review desk and the Ones Committee only.
- `index`: one search chunk per shared idea, built from its database row (title and short summary), never from
  the company repo's idea files.
- `matching`: hybrid retrieval over those chunks, labelled by the `judge` agent through the gateway, or by code
  when the assistant is off; kept in `similar_links`.
- `views.matches_for`: SimilarMatch[] from the stored links, as one viewer may see them.

The two entry points other lane C modules import (`tests/test_c_similar_entry_points.py` pins the names):
- `similar_for(conn, idea_uuid, title, summary)`: the draft's similar part (c/draft, `draft/adapters.py`).
- `match_shared(conn, idea_uuid, found_while=...)`: at send and after an edit (c/sort-submit, `submit/adapters.py`).
Imports are inside the functions, so `import similar` stays light for the preview's users.
"""

from __future__ import annotations

from typing import Any

from core.db import Conn

__all__ = ["match_shared", "similar_for"]


def similar_for(conn: Conn, idea_uuid: str, title: str, summary: str) -> list[dict[str, Any]] | None:
    """The draft's similar part (L-SIMILAR.rules/4, BLD-C093): match the draft now (or reuse the last run when its
    words changed too little), then return up to 8 SimilarMatch dicts as its sharer sees them. None when they could
    not be looked for: the part then says "Couldn't check for similar ideas. The review desk will."
    (L-SIMILAR.failure), never "none found". `title` and `summary` are the draft's newest title part."""
    from similar.matching import MAX_MATCHES, match_idea
    from similar.preview import Viewer
    from similar.views import matches_for

    run = match_idea(conn, idea_uuid, found_while="drafting", title=title, summary=summary)
    if run.state == "failed":
        return None
    owner = conn.execute(
        "SELECT m.user_id FROM ideas i JOIN contributor_map m ON m.contributor_code = i.contributor_code "
        "WHERE i.id = %s",
        (idea_uuid,),
    ).fetchone()
    if owner is None:
        return None
    try:
        found = matches_for(conn, idea_uuid, Viewer.of(conn, str(owner["user_id"])))
    except Exception:
        return None
    return None if found is None else found[:MAX_MATCHES]


def match_shared(conn: Conn, idea_uuid: str, *, found_while: str) -> int:
    """Match a shared idea at send (`checking`, always runs) or after an edit (`later`, runs on a material change)
    and keep the links (L-SIMILAR.rules/5, BLD-C093). Returns how many matches are stored for it, or -1 when
    matching failed (recorded, retried on the next run; sharing goes on, L-SIMILAR.failure). Safe inside the
    caller's transaction."""
    from similar.matching import match_idea

    if found_while not in ("drafting", "checking", "later"):
        raise ValueError("found_while")
    run = match_idea(conn, idea_uuid, found_while=found_while)  # type: ignore[arg-type]
    return -1 if run.state == "failed" else run.found
