"""One table of stage words for every view (DEC-038, brand pass review A5).

`PUBLIC_WORDS` is what anyone sees for an idea that has reached the wall; the owner's own view (`views.mine`)
uses the same word for the same stage, adding only stages nobody else sees (drafts, checks, the review desk).
Never "duplicate", "rejected", "already solved" or "Garage" (CLAUDE.md "Words on screen", DEC-035).

The one exception is Find your crew (BLD-104): a match card for an idea that has shipped says "Already running",
like a solution card, because the choice the person makes there is to ask to use it.
"""

from __future__ import annotations

PUBLIC_WORDS: dict[str, str] = {
    "reviewed": "Reviewed",
    "in_cluster": "Grouped with similar ideas",
    "ready_for_scoring": "Being assessed",
    "scored": "Being assessed",
    "shortlisted": "Shortlisted",
    "presenting": "Being presented",
    "picked": "Picked",
    "handover": "Being built",
    "in_garage": "Being built",
    "in_fix_track": "Being fixed",
    "shipped": "Shipped",
    "resolved": "Fixed",
    "measuring": "Shipped",
    "closed": "Shipped",
}

# Find your crew only (BLD-104).
MATCH_CARD_WORDS: dict[str, str] = {
    **PUBLIC_WORDS,
    "scanned": "With the review desk",
    "needs_info": "With the review desk",
    "declined": "Looked at before",
    "parked": "Looked at before",
    "shipped": "Already running",
    "measuring": "Already running",
    "closed": "Already running",
}
