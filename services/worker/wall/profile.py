"""Profile and settings (S-H6, A-API.me): who the person is in 1% Club, their private points, whether their name
shows on the Wall, and how they are reached. Only ever the signed-in person's own (P-PRODUCT.privacy: points are
private to the person; Person.settings and Person.email are self only).

Switches save one at a time and the response carries every switch's new state (S-H6.rules/1). Teams messages are
built and switched off until IT approves them (DEC-105): the switch reads `available: false` until the
`comms.teams` kill switch exists and is on (an unknown switch counts as off, §7.6), and cannot be changed meanwhile.
"""

from __future__ import annotations

from typing import Any

from psycopg.types.json import Jsonb

from core import killswitch
from core.db import Conn
from onepc.enums import ROLE
from points.ledger import mine as my_points
from wall import kindling
from wall.common import MSG_SAVE_FAILED, Refused, day_label, initials, tier_label
from wall.ones import approved_brief

PERSON_SWITCHES = ("show_name_on_wall", "shortcut_p", "sidebar_folded")  # person_settings
CHANNEL_SWITCHES = ("teams", "email", "reminders")  # comms_prefs
TEAMS_SWITCH = "comms.teams"
DEFAULTS = {
    "show_name_on_wall": True, "shortcut_p": True, "sidebar_folded": False,
    "teams": True, "email": True, "reminders": True,
}  # fmt: skip


def teams_available(conn: Conn) -> bool:
    return killswitch.is_on(TEAMS_SWITCH, conn)


def settings(conn: Conn, user_id: str) -> dict[str, Any]:
    """E-ENTITIES Person.settings, with the defaults where nothing is saved yet. Teams reads off while it is
    unavailable, whatever was saved."""
    ps = conn.execute("SELECT * FROM person_settings WHERE user_id = %s", (user_id,)).fetchone() or {}
    cp = conn.execute("SELECT * FROM comms_prefs WHERE user_id = %s", (user_id,)).fetchone() or {}
    out = {k: bool(ps[k]) if k in ps else DEFAULTS[k] for k in PERSON_SWITCHES}
    out.update({k: bool(cp[k]) if k in cp else DEFAULTS[k] for k in CHANNEL_SWITCHES})
    if not teams_available(conn):
        out["teams"] = False
    return out


def _roles(conn: Conn, user_id: str) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT role FROM role_grants WHERE user_id = %s AND valid_from <= now() "
        "AND (valid_to IS NULL OR valid_to > now())",
        (user_id,),
    ).fetchall()
    have = {str(r["role"]) for r in rows} | {"employee"}
    return [r for r in ROLE if r in have and r != "build_team"]  # build_team is per idea, not a person's role


def profile(conn: Conn, user_id: str) -> dict[str, Any]:
    """`GET /me/profile`: E-ENTITIES Person with `points` and `settings` (self only), plus what S-H6 shows: the
    line under the name, the tier ring for the avatar, the One dashboard link for a One (S-H6.rules/4), and
    `refer_as` for "How should we refer to you?" (DEC-108; lane C's answer, "unset" until its route lands)."""
    u = conn.execute(
        "SELECT id, name, first_name, email, area, location, tier FROM users WHERE id = %s AND active",
        (user_id,),
    ).fetchone()
    if u is None:
        raise Refused(404, "not_found")
    one = conn.execute(
        "SELECT id, number, tier, way_in, inducted_at, swap_until, brief_encrypted, brief_approved_at FROM ones "
        "WHERE user_id = %s AND status = 'active' AND number IS NOT NULL",
        (user_id,),
    ).fetchone()
    tier = int(one["tier"] if one else u["tier"])  # a One's tier is their One tier (L-ONES.rules/3, /4)
    name = str(u["name"])
    person: dict[str, Any] = {
        "id": str(u["id"]),
        "name": name,
        "first_name": str(u["first_name"] or name.split()[0]),
        "initials": initials(name),
        "area": str(u["area"] or ""),
        "city": str(u["location"] or ""),
        "email": str(u["email"] or ""),
        "roles": _roles(conn, user_id),
        "tier": tier,
        "points": int(my_points(conn, user_id)["total"]),  # private to the person (P-PRODUCT.privacy)
        "settings": settings(conn, user_id),
    }
    if one is not None:
        person["one"] = {
            "number": one["number"],
            "flag": "founding" if one["way_in"] == "founding" else "one",
            "since": one["inducted_at"].isoformat(),
            "number_locked_at": one["swap_until"].isoformat(),
            "brief": approved_brief(dict(one)) or "",
        }
    place = ", ".join(x for x in (person["area"], person["city"]) if x)
    return {
        "person": person,
        "tier_label": tier_label(tier),
        # "Investor service, Hyderabad. Tier 2, Glow." (S-H6.layout/1)
        "line": f"{place}. {tier_label(tier)}." if place else f"{tier_label(tier)}.",
        "avatar": {"initials": person["initials"], "tier": tier},
        "one_dashboard": "/one" if one is not None else None,
        "one_since_label": day_label(one["inducted_at"]) if one is not None else None,
        "available": {"teams": teams_available(conn)},
        # "How should we refer to you?" (DEC-108, BLD-E010): "she", "he", "they" or "unset" (the default, and
        # "Prefer not to say"). TODO(lane C): lane C owns the answer and its store through `GET/PUT
        # /api/me/refer-as` (on main by Wed 18 Nov, 12:00); the screen saves there directly. Until then this is
        # "unset", so S-H6 needs no special case. Lane E builds no store and no write path for it.
        "refer_as": "unset",
    }


def save_settings(conn: Conn, user_id: str, body: Any) -> dict[str, Any]:
    """`PATCH /me/settings`: any of the switches, each a boolean; saves at once and returns every switch's state.
    A refusal carries "Couldn't save that. Try again." under the switch it names (V-FIELDS.one/5), so the screen
    flips it back (S-H6.rules/1 NOT DRAWN default). The Wall switch applies to every idea past and future: the
    Wall reads it live (its short cache is cleared here). Logged with the switch names and new values only."""
    if not isinstance(body, dict):
        raise Refused(422, "bad_setting", MSG_SAVE_FAILED)
    known = (*PERSON_SWITCHES, *CHANNEL_SWITCHES)
    for key, value in body.items():
        if key not in known or not isinstance(value, bool):
            raise Refused(422, "bad_setting", MSG_SAVE_FAILED, field=str(key) if key in known else None)
    if "teams" in body and not teams_available(conn):
        raise Refused(409, "teams_off", MSG_SAVE_FAILED, field="teams")
    if conn.execute("SELECT 1 FROM users WHERE id = %s AND active", (user_id,)).fetchone() is None:
        raise Refused(404, "not_found")
    person = {k: body[k] for k in PERSON_SWITCHES if k in body}
    channel = {k: body[k] for k in CHANNEL_SWITCHES if k in body}
    with conn.transaction():
        if person:
            cols = ", ".join(person)
            sets = ", ".join(f"{k} = EXCLUDED.{k}" for k in person)
            conn.execute(
                f"INSERT INTO person_settings (user_id, {cols}) VALUES (%s{', %s' * len(person)}) "  # noqa: S608
                f"ON CONFLICT (user_id) DO UPDATE SET {sets}",
                (user_id, *person.values()),
            )
        if "show_name_on_wall" in person:
            channel["public_name_consent"] = person["show_name_on_wall"]  # old pages read this until Monday
        if channel:
            cols = ", ".join(channel)
            sets = ", ".join(f"{k} = EXCLUDED.{k}" for k in channel)
            conn.execute(
                f"INSERT INTO comms_prefs (user_id, {cols}) VALUES (%s{', %s' * len(channel)}) "  # noqa: S608
                f"ON CONFLICT (user_id) DO UPDATE SET {sets}",
                (user_id, *channel.values()),
            )
        if body:
            conn.execute(
                "INSERT INTO audit_log (actor, action, entity, after) VALUES (%s, 'profile.settings_changed', %s, %s)",
                (f"user:{user_id}", f"user:{user_id}", Jsonb({k: body[k] for k in sorted(body)})),
            )
    if "show_name_on_wall" in body:
        kindling.clear_cache()
    return {"settings": settings(conn, user_id)}
