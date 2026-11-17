"""The S1 to S3 experiments for worker-side code (L-AUDIT.flags, P-DECISIONS.experiments). The web app has the same
rules in `apps/web/src/server/flags.ts`; a shared test vector keeps the two buckets equal.

- An admin sets each flag's state (on or off) and the share of people who get the alternative (0 to 100).
- A person an admin assigned gets that variant. Everyone else is placed by a deterministic bucket: the first four
  bytes of SHA-256 of "<key>:<user id>", as an unsigned number, modulo 100. Below `alternative_percent` means the
  alternative. Raising the percentage only adds people; nobody already in the alternative flips back.
- A flag that is off, or unknown, gives the default and logs nothing.
- The first time a person is shown a variant on a screen, one exposure row is written (the unique index
  `flag_exposures_once` keeps it to one per person, screen and variant).
"""

from __future__ import annotations

import hashlib
from typing import Literal

from core.db import Conn

Variant = Literal["default", "alternative"]


def bucket(key: str, user_id: str) -> int:
    digest = hashlib.sha256(f"{key}:{user_id}".encode()).digest()
    return int.from_bytes(digest[:4], "big") % 100


def variant_for(conn: Conn, user_id: str, key: str) -> Variant | None:
    """The person's variant, or None when the flag is off or unknown (then the default applies, unlogged)."""
    flag = conn.execute("SELECT state, alternative_percent FROM flags WHERE key = %s", (key,)).fetchone()
    if flag is None or flag["state"] != "on":
        return None
    assigned = conn.execute(
        "SELECT variant FROM flag_assignments WHERE flag_key = %s AND user_id = %s", (key, user_id)
    ).fetchone()
    if assigned is not None:
        return "alternative" if assigned["variant"] == "alternative" else "default"
    return "alternative" if bucket(key, user_id) < int(flag["alternative_percent"]) else "default"


def flag_variant(conn: Conn, user_id: str, key: str, screen: str) -> Variant:
    """What `screen` (a screen ID such as "S-04") shows this person, logging the exposure once."""
    variant = variant_for(conn, user_id, key)
    if variant is None:
        return "default"
    conn.execute(
        "INSERT INTO flag_exposures (flag_key, user_id, variant, screen) VALUES (%s, %s, %s, %s) "
        "ON CONFLICT (flag_key, user_id, screen, variant) DO NOTHING",
        (key, user_id, variant, screen),
    )
    return variant
