"""The office screen's Ones (S-OFFICE, L-DISPLAY.office; A-API `GET /display/office`).

Active Ones with a number, in induction order (Founding Ones first), with their tier, the approved impact brief
(checked again, as on the Wall, so no name or client reaches the screen) and the measures everyone may see: money
only once Finance has confirmed it. A One's name shows unless they hid it from the Wall in Profile (DEC-104,
`person_settings.show_name_on_wall`; no row means shown). `ones.public` off hides all of it.
"""

from __future__ import annotations

from typing import Any

from core import killswitch
from core.db import Conn
from ones.text import unseal
from ones.tiers import tier_colour, tier_name
from views.common import checked_summary


def _public_measures(measures: dict[str, Any] | None) -> dict[str, Any]:
    out = {}
    for key, value in (measures or {}).items():
        if key == "money" and not value.get("finance_confirmed"):
            continue
        out[key] = {"value": value.get("value"), "unit": value.get("unit")}
    return out


def office(conn: Conn) -> dict[str, Any]:
    if not killswitch.is_on("ones.public", conn):
        return {"paused": True, "ones": []}
    rows = conn.execute(
        "SELECT o.id, o.number, o.induction_no, o.way_in, o.tier, o.brief_encrypted, o.brief_approved_at, "
        "o.measures, u.name, u.first_name, coalesce(s.show_name_on_wall, true) AS show_name "
        "FROM ones o JOIN users u ON u.id = o.user_id LEFT JOIN person_settings s ON s.user_id = o.user_id "
        "WHERE o.status = 'active' AND o.number IS NOT NULL ORDER BY o.induction_no"
    ).fetchall()
    ones = []
    for r in rows:
        brief = unseal(r["brief_encrypted"], f"one:{r['id']}:brief") if r["brief_approved_at"] else None
        name = r["name"] if r["show_name"] else None
        ones.append(
            {
                "number": r["number"],
                "induction_no": r["induction_no"],
                "name": name,
                "first_name": (r["first_name"] or (name or "").split(" ")[0] or None) if name else None,
                "founding": r["way_in"] == "founding",
                "tier": r["tier"],
                "tier_name": tier_name(r["tier"]),
                "tier_colour": tier_colour(r["tier"]),
                "brief": checked_summary(conn, brief),
                "measures": _public_measures(r["measures"]),
            }
        )
    return {"paused": False, "ones": ones}
