"""Kill switches (§7.6), worker side. Read on every use with a 10-second cache (BLD-006).

"on" means the feature runs; "off" means it is killed. Every change needs a reason and writes `audit_log`.
The web app has the same logic in TypeScript (`apps/web/src/server/killswitch.ts`); both read one table.

CLI:  python -m core.killswitch set <name> <on|off> --reason "…" --actor REV-0001
      python -m core.killswitch list
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Any

from psycopg.types.json import Jsonb

from core.db import Conn, connect
from core.logging import get_logger

log = get_logger("killswitch")

CACHE_SECONDS = 10.0
REASON_MIN_CHARS = 10
_cache: dict[str, Any] = {"at": 0.0, "states": {}}


class KillSwitchError(ValueError):
    pass


def states(conn: Conn | None = None, *, now: float | None = None) -> dict[str, str]:
    t = time.monotonic() if now is None else now
    if t - _cache["at"] < CACHE_SECONDS and _cache["states"]:
        return dict(_cache["states"])
    own = conn is None
    c = conn or connect(autocommit=True)
    try:
        rows = c.execute("SELECT name, state FROM kill_switches").fetchall()
    finally:
        if own:
            c.close()
    _cache["states"] = {r["name"]: r["state"] for r in rows}
    _cache["at"] = t
    return dict(_cache["states"])


def is_on(name: str, conn: Conn | None = None) -> bool:
    """A switch the table does not know is treated as off: fail closed."""
    return states(conn).get(name) == "on"


def is_on_fresh(name: str, conn: Conn | None = None) -> bool:
    """One switch read straight from the table, past the 10-second cache: for a step that must never run on a
    stale "on" (a hosted speech call sends raw voice out, DEC-096). Unknown counts as off."""
    own = conn is None
    c = conn or connect(autocommit=True)
    try:
        row = c.execute("SELECT state FROM kill_switches WHERE name = %s", (name,)).fetchone()
    finally:
        if own:
            c.close()
    return row is not None and row["state"] == "on"


def clear_cache() -> None:
    _cache["at"], _cache["states"] = 0.0, {}


def set_switch(conn: Conn, name: str, state: str, *, reason: str, actor: str, ip: str | None = None) -> None:
    """Flip a switch. One transaction: the change and its audit row."""
    if state not in ("on", "off"):
        raise KillSwitchError("state must be on or off")
    if len(reason.strip()) < REASON_MIN_CHARS:
        raise KillSwitchError(f"a reason of at least {REASON_MIN_CHARS} characters is required")
    if not actor.strip():
        raise KillSwitchError("actor is required")
    with conn.transaction():
        before = conn.execute(
            "SELECT state FROM kill_switches WHERE name = %s FOR UPDATE", (name,)
        ).fetchone()
        if before is None:
            raise KillSwitchError(f"unknown kill switch {name}")
        conn.execute(
            "UPDATE kill_switches SET state = %s, reason = %s, changed_by = %s, changed_at = now() WHERE name = %s",
            (state, reason.strip(), actor, name),
        )
        conn.execute(
            "INSERT INTO audit_log (actor, action, entity, before, after, reason, ip) "
            "VALUES (%s, 'kill_switch.set', %s, %s, %s, %s, %s)",
            (
                actor,
                f"kill_switch:{name}",
                Jsonb({"state": before["state"]}),
                Jsonb({"state": state}),
                reason.strip(),
                ip,
            ),
        )
    clear_cache()
    # The product lead and InfoSec are alerted through the comms module (B6); until then the log line is the alert.
    log.warning("killswitch.changed", switch=name, state=state, actor_code=actor)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("set")
    s.add_argument("name")
    s.add_argument("state", choices=["on", "off"])
    s.add_argument("--reason", required=True)
    s.add_argument("--actor", required=True)
    sub.add_parser("list")
    args = parser.parse_args(argv)
    with connect(autocommit=True) as conn:
        if args.cmd == "set":
            try:
                set_switch(conn, args.name, args.state, reason=args.reason, actor=args.actor)
            except KillSwitchError as exc:
                print(f"refused: {exc}")
                return 2
            print(f"{args.name} is now {args.state}")
        for name, state in sorted(states(conn, now=float("inf")).items()):
            print(f"{name:22} {state}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
