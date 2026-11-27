"""Appeals (§4.12, DEC-057, BLD-222): what is left after DEC-106 retired filing and hearing an appeal.

The routes that filed, listed and decided appeals went in BLD-E078 (R1, dead code only), with the panel, rotation and
outcome code they alone reached. Left are the two reads the committee flow in `committee/rounds.py` and
`committee/decide.py` still calls: whether a decision could be appealed (it sets the decision's appeal window) and the
latest re-score direction note. They go with the `appeals` table in R2.
"""

from __future__ import annotations

from core.db import Conn

WINDOW_WD = 15


def appealable(conn: Conn, cluster_id: str, outcome: str, decision_id: str | None = None) -> bool:
    """A decline, or a park when the group was parked before (§4.12 "parked twice")."""
    if outcome == "declined":
        return True
    if outcome != "parked":
        return False
    before = conn.execute(
        "SELECT count(*) AS n FROM decisions WHERE cluster_id = %s AND outcome = 'parked' AND id IS DISTINCT FROM %s",
        (cluster_id, decision_id),
    ).fetchone()
    return int(before["n"] if before else 0) >= 1


def direction_for(conn: Conn, cluster_id: str) -> str | None:
    """The latest re-score direction note for a group (tagged), for the next round's view."""
    row = conn.execute(
        "SELECT reasons FROM appeals WHERE cluster_id = %s AND outcome = 're_score' ORDER BY decided_at DESC LIMIT 1",
        (cluster_id,),
    ).fetchone()
    return str(row["reasons"]) if row and row["reasons"] else None
