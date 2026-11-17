"""Lane F: team-up requests, draft merge requests, lead-accepted merges and crews (L-TEAMUP, L-MERGE.request,
L-MERGE.effects for `lead_accepted`, A-API.team-up).

- `requests`: asking to team up on a shared idea, withdrawing, the lead's answer, and the reads every screen needs.
- `drafts`: a sharer asks, from an unsent draft, for it to be merged in (L-MERGE.request).
- `merging.apply_lead_merge`: what a merge the lead accepted does, in one transaction (modelled on lane B's
  `desk_merge`, so the two can converge after launch).
- `crew`: leaving a crew and the lead removing a member (L-TEAMUP/11, NOT DRAWN default).
- `routes`: the `/internal/*` router, mounted at the end of `api/app.py`.

Other lanes call `close_requests_for(conn, idea_uuid)` when an idea closes (withdrawn, not picked, not now, merged
away), so its waiting requests close with it (L-TEAMUP.states); reads also settle them lazily.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import datetime as dt

    from core.db import Conn


def close_requests_for(conn: Conn, idea_uuid: Any, at: dt.datetime | None = None) -> int:
    """Close every waiting request on an idea that has just closed. Returns how many closed."""
    from teamup.requests import close_requests_for as _close

    return _close(conn, idea_uuid, at)
