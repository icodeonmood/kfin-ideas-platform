"""The Ones on measured, confirmed impact (L-ONES.rules/1-3; DEC-102, DEC-106; J-ONE steps 3 and 6).

- **Becoming a One** (`on_measurement` -> `_induct`): once an idea has shipped and a measurement of it counts,
  everyone credited on it who has never been a One becomes one: the next free number (`ones.numbers`), the number
  window from rules/promises.md, and a tier from their measured impact. A person an admin removed is not brought
  back automatically; the admin's call stands, and marking them a Founding One is the way back.
- **A measurement counts** once it is entered and, if it carries money, Finance has confirmed it (L-IMPACT/3,
  BLD-A213). Hours saved and money come from the latest counted measurement of each shipped idea the person is
  credited on (the 90-day one over the 30-day one, measure by measure).
- **Tiers** (`rules/tiers.md`, L-ONES.open): the highest tier whose hours or money threshold the person's total
  meets. A tier only rises on its own, and each rise leaves a glow-up for the One's dashboard (S-ONE, the "moment"
  of L-ONES.rules/3).
- **Admin path** (DEC-106): mark a Founding One, remove a One. Both need a reason and are audited.

The office screen (S-OFFICE) and the Wall's "The Ones" read active Ones with a number from `ones`, and the office
screen reads `ones.measures`; both are written here, so a new One shows there as soon as they are inducted.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from psycopg.types.json import Jsonb

from core.config import get_settings
from core.db import Conn
from notify import post
from ones import numbers
from programme.common import (
    Refused,
    audit,
    credited_users,
    log,
    need,
    now_utc,
    promise,
    reason,
    user_by_email,
)

MEASURES = ("time", "money", "effort", "scale")
# The pack's thresholds are open (L-ONES.open); these are the seeded rules/tiers.md values, used only when the rule
# cannot be read.
DEFAULT_TIERS: dict[int, tuple[float, float]] = {
    1: (0, 0),
    2: (100, 500_000),
    3: (250, 1_000_000),
    4: (500, 2_500_000),
    5: (1000, 5_000_000),
    6: (2500, 10_000_000),
    7: (5000, 25_000_000),
}


def tier_rules() -> dict[int, tuple[float, float]]:
    from rules import load_rule

    try:
        data = load_rule(get_settings().company_repo_path, "tiers").data["tiers"]
        return {int(k): (float(v["hours_month"]), float(v["money_year"])) for k, v in data.items()}
    except Exception:  # an unreadable rule must not stop an induction; the seeded values stand in
        log.warning("programme.tiers_default")
        return dict(DEFAULT_TIERS)


def tier_for(
    hours_month: float, money_year: float, rules: dict[int, tuple[float, float]] | None = None
) -> int:
    rules = rules or tier_rules()
    best = 1
    for tier in sorted(rules):
        need_hours, need_money = rules[tier]
        if hours_month >= need_hours or money_year >= need_money:
            best = tier
    return best


# --- What counts ------------------------------------------------------------------------------------------------


def counted_rows(conn: Conn, idea_uuids: list[str]) -> dict[str, list[dict[str, Any]]]:
    """Each idea's counted measurements, the 90-day one first."""
    out: dict[str, list[dict[str, Any]]] = {}
    if not idea_uuids:
        return out
    for r in conn.execute(
        "SELECT id, idea_uuid, mark, results, finance_confirmed_at FROM delivery_measurements "
        "WHERE idea_uuid = ANY(%s::uuid[]) AND filled_at IS NOT NULL "
        "AND (NOT (results ? 'money') OR finance_confirmed_at IS NOT NULL) "
        "ORDER BY idea_uuid, (mark = 'day_90') DESC",
        (idea_uuids,),
    ).fetchall():
        out.setdefault(str(r["idea_uuid"]), []).append(dict(r))
    return out


def latest(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """The latest counted figure for each measure (L-IMPACT/4)."""
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        for key in MEASURES:
            value = (r["results"] or {}).get(key)
            if key not in out and isinstance(value, dict) and value.get("amount") is not None:
                out[key] = value
    return out


def hours_a_month(figure: dict[str, Any] | None) -> float:
    if not figure:
        return 0.0
    amount, unit = float(figure.get("amount") or 0), str(figure.get("unit") or "").lower()
    if "day" in unit:
        return amount * 8 / (12 if "year" in unit else 1)  # an 8-hour working day
    if "hour" in unit:
        return amount / 12 if "year" in unit else amount
    return 0.0


def rupees_a_year(figure: dict[str, Any] | None) -> float:
    if not figure:
        return 0.0
    amount = float(figure.get("amount") or 0)
    return amount * 12 if "month" in str(figure.get("unit") or "").lower() else amount


def credited_shipped_ideas(conn: Conn, user_id: str) -> list[str]:
    """Shipped ideas the person is credited on: their own, and ideas theirs was merged into (merge standing)."""
    rows = conn.execute(
        "SELECT i.id FROM ideas i WHERE i.status = 'shipped' AND (i.contributor_code IN (SELECT contributor_code "
        "FROM contributor_map WHERE user_id = %(u)s) OR i.id IN (SELECT m.lead_idea_uuid FROM merges m "
        "JOIN ideas mi ON mi.id = m.merged_idea_uuid JOIN contributor_map cm ON cm.contributor_code = "
        "mi.contributor_code WHERE cm.user_id = %(u)s AND m.reversed_at IS NULL))",
        {"u": user_id},
    ).fetchall()
    return [str(r["id"]) for r in rows]


def person_totals(conn: Conn, user_id: str) -> tuple[float, float]:
    """Hours a month and rupees a year across every shipped idea the person is credited on, counted figures only."""
    rows = counted_rows(conn, credited_shipped_ideas(conn, user_id))
    hours = money = 0.0
    for idea_rows in rows.values():
        figures = latest(idea_rows)
        hours += hours_a_month(figures.get("time"))
        money += rupees_a_year(figures.get("money"))
    return hours, money


def one_measures(conn: Conn, idea_uuid: str) -> dict[str, Any]:
    """The idea's counted figures in the shape `ones.measures` has always had (`{value, unit}`, money with its
    Finance flag), which the office screen reads."""
    figures = latest(counted_rows(conn, [idea_uuid]).get(idea_uuid, []))
    out: dict[str, Any] = {}
    for key, f in figures.items():
        out[key] = {"value": f["amount"], "unit": f.get("unit")}
        if key == "money":
            out[key]["finance_confirmed"] = True  # counted money is Finance-confirmed by definition
    return out


# --- Becoming a One, and rising ---------------------------------------------------------------------------------


def _new_one(
    conn: Conn, user_id: str, way_in: str, idea_ref: str | None, tier: int, now: dt.datetime
) -> dict[str, Any]:
    window = dt.timedelta(days=int(promise("ones", "number_change_days", 30)))
    n = conn.execute("SELECT next_number('ONE', '') AS n").fetchone()
    assert n is not None
    number = numbers.next_number(conn, 0, now)
    row = conn.execute(
        "INSERT INTO ones (induction_no, user_id, number, way_in, idea_id, tier, inducted_at, swap_until) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
        (n["n"], user_id, number, way_in, idea_ref, tier, now, now + window),
    ).fetchone()
    assert row is not None
    one_id = int(row["id"])
    numbers.wear(conn, one_id, number, "allocated", now)
    conn.execute("UPDATE users SET tier = %s WHERE id = %s", (tier, user_id))
    return {"user_id": user_id, "one_id": one_id, "number": number, "tier": tier}


def on_measurement(
    conn: Conn, idea_row: dict[str, Any], measurement_id: int, actor: str, now: dt.datetime
) -> dict[str, list[dict[str, Any]]]:
    """Call inside the transaction that entered or confirmed a measurement. Inducts whoever the rules now make a
    One, raises tiers, refreshes the Ones' measures. Idempotent: nothing happens until a measurement counts."""
    out: dict[str, list[dict[str, Any]]] = {"inducted": [], "tier_rises": []}
    idea_uuid = str(idea_row["id"])
    if idea_row["status"] != "shipped" or not counted_rows(conn, [idea_uuid]).get(idea_uuid):
        return out
    rules = tier_rules()
    for user_id in credited_users(conn, idea_uuid):
        existing = conn.execute("SELECT * FROM ones WHERE user_id = %s FOR UPDATE", (user_id,)).fetchone()
        hours, money = person_totals(conn, user_id)
        tier = tier_for(hours, money, rules)
        if existing is None:
            one = _new_one(conn, user_id, "accepted_idea", idea_row["idea_id"], tier, now)
            audit(conn, actor, "ones.inducted", f"one:{one['one_id']}",
                  {"idea_id": idea_row["idea_id"], "number": one["number"], "tier": tier,
                   "measurement_id": measurement_id, "how": "measured_impact"})  # fmt: skip
            post(conn, "stage_moved", [user_id], idea_id=idea_uuid,
                 refs={"event": "one_inducted", "number": one["number"], "tier": tier},
                 dedupe_key=f"one_inducted:{one['one_id']}")  # fmt: skip
            out["inducted"].append(one)
        elif existing["status"] == "active" and tier > int(existing["tier"]):
            conn.execute("UPDATE ones SET tier = %s WHERE id = %s", (tier, existing["id"]))
            conn.execute("UPDATE users SET tier = %s WHERE id = %s", (tier, user_id))
            conn.execute(
                "INSERT INTO one_glow_ups (one_id, proposal_id, measurement_id, tier_from, tier_to, created_at) "
                "VALUES (%s, NULL, %s, %s, %s, %s)",
                (existing["id"], measurement_id, existing["tier"], tier, now),
            )
            audit(conn, actor, "ones.tier_rose", f"one:{existing['id']}",
                  {"tier_from": int(existing["tier"]), "tier_to": tier, "measurement_id": measurement_id},
                  before={"tier": int(existing["tier"])})  # fmt: skip
            post(conn, "stage_moved", [user_id], idea_id=idea_uuid,
                 refs={"event": "tier_rose", "tier_from": int(existing["tier"]), "tier_to": tier},
                 dedupe_key=f"tier_rose:{existing['id']}:{tier}")  # fmt: skip
            out["tier_rises"].append(
                {"user_id": user_id, "one_id": int(existing["id"]), "tier_from": int(existing["tier"]),
                 "tier_to": tier}
            )  # fmt: skip
    measures = one_measures(conn, idea_uuid)
    if measures:
        conn.execute(
            "UPDATE ones SET measures = %s WHERE idea_id = %s AND way_in = 'accepted_idea'",
            (Jsonb(measures), idea_row["idea_id"]),
        )
    return out


# --- The admin path (DEC-106) -----------------------------------------------------------------------------------


def mark_founding(
    conn: Conn, actor: str, body: dict[str, Any], now: dt.datetime | None = None
) -> dict[str, Any]:
    """An admin marks a Founding One (L-ONES.rules/1, DEC-102): a One keeps their number and gains the flag; a
    removed One comes back to the same record; anyone else becomes a One with the next free number."""
    now = now or now_utc()
    need(conn, actor, {"admin"})
    why = reason(body.get("reason"))
    with conn.transaction():
        user_id = user_by_email(conn, body.get("email"), "email")
        existing = conn.execute("SELECT * FROM ones WHERE user_id = %s FOR UPDATE", (user_id,)).fetchone()
        if existing is not None and existing["status"] == "active":
            if existing["way_in"] == "founding":
                raise Refused(
                    409, "already_founding", "That person is already a Founding One.", field="email"
                )
            conn.execute("UPDATE ones SET way_in = 'founding' WHERE id = %s", (existing["id"],))
            out = {"user_id": user_id, "one_id": int(existing["id"]), "number": existing["number"],
                   "tier": int(existing["tier"])}  # fmt: skip
        elif existing is not None:
            window = dt.timedelta(days=int(promise("ones", "number_change_days", 30)))
            number = numbers.next_number(conn, int(existing["id"]), now)
            conn.execute(
                "UPDATE ones SET status = 'active', number = %s, way_in = 'founding', inducted_at = %s, "
                "swap_until = %s, retired_at = NULL WHERE id = %s",
                (number, now, now + window, existing["id"]),
            )
            numbers.wear(conn, int(existing["id"]), number, "allocated", now)
            out = {"user_id": user_id, "one_id": int(existing["id"]), "number": number,
                   "tier": int(existing["tier"])}  # fmt: skip
        else:
            hours, money = person_totals(conn, user_id)
            out = _new_one(conn, user_id, "founding", None, tier_for(hours, money), now)
            post(conn, "stage_moved", [user_id], refs={"event": "one_inducted", "number": out["number"],
                 "tier": out["tier"], "founding": True}, dedupe_key=f"one_inducted:{out['one_id']}")  # fmt: skip
        audit(conn, actor, "ones.founding_marked", f"one:{out['one_id']}",
              {"number": out["number"]}, reason=why)  # fmt: skip
    return out


def remove_one(
    conn: Conn, actor: str, one_id: Any, body: dict[str, Any], now: dt.datetime | None = None
) -> dict[str, Any]:
    """An admin removes a One (DEC-106): their number rests (`ones.numbers`), and their card, posts and light leave
    the Wall, Home and the office screen, which read active Ones only. The record stays."""
    now = now or now_utc()
    need(conn, actor, {"admin"})
    why = reason(body.get("reason"))
    try:
        oid = int(one_id)
    except (TypeError, ValueError):
        raise Refused(404, "not_found", "That One is not on the list any more.") from None
    with conn.transaction():
        one = conn.execute(
            "SELECT * FROM ones WHERE id = %s AND status = 'active' FOR UPDATE", (oid,)
        ).fetchone()
        if one is None:
            raise Refused(404, "not_found", "That One is not on the list any more.")
        numbers.release(conn, oid, now)
        conn.execute(
            "UPDATE ones SET status = 'retired', number = NULL, retired_at = %s WHERE id = %s", (now, oid)
        )
        audit(conn, actor, "ones.removed", f"one:{oid}", {"status": "retired"},
              before={"number": one["number"], "tier": int(one["tier"]), "way_in": one["way_in"]},
              reason=why)  # fmt: skip
    return {"one_id": oid, "removed": True}


def list_ones(conn: Conn) -> list[dict[str, Any]]:
    """Active Ones for the admin page, by number."""
    rows = conn.execute(
        "SELECT o.id, o.number, o.tier, o.way_in, o.idea_id, o.inducted_at, u.name, u.email FROM ones o "
        "JOIN users u ON u.id = o.user_id WHERE o.status = 'active' AND o.number IS NOT NULL ORDER BY o.number"
    ).fetchall()
    return [
        {"id": int(r["id"]), "number": int(r["number"]), "tier": int(r["tier"]),
         "founding": r["way_in"] == "founding", "idea_ref": r["idea_id"], "name": r["name"],
         "email": r["email"], "since": r["inducted_at"].isoformat()}
        for r in rows
    ]  # fmt: skip
