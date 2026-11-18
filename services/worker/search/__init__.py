"""L-SEARCH (lane F): search a person's own list by what it says, with filters and live counts.

For lane E's My ideas (S-07) and any list that swaps it in:

    search.search(conn, user_id: str, q: str | None, filters: Mapping | None = None, *, now=None) -> dict

Scope is the person's own ideas and drafts and the ideas they teamed up on (L-SEARCH/1). The pure rules are in
`search.rules`; "ask in your own words" is the seam `search.ask.interpret`, which answers None until it is built.
"""

from search.ask import interpret
from search.mine import search

__all__ = ["interpret", "search"]
