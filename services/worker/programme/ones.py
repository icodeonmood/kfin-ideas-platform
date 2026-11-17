"""The Ones on measured, confirmed impact: lane A's side (J-ONE steps 3 and 6; L-ONES.rules/1-3; DEC-102, DEC-106).

Lane E owns L-ONES, and this module calls its entry points (`wall/__init__.py`), never its tables' rules:

- **Becoming a One** is `wall.ones.induct_for_idea`: once an idea has shipped and a figure of it counts (money only
  once Finance confirmed it, `wall.impact.latest_figures`), everyone credited who has never been a One becomes one,
  with the next free number and the number window. A person an admin removed is not brought back automatically.
  `on_measurement` calls it after every measurement entered or confirmed (J-ONE step 3's trigger).
- **Founding Ones and removing a One** are `wall.ones.mark_founding` and `wall.ones.remove_one`, both audited by
  lane E. The admin page reaches them through `mark_founding` and `remove_one` here, which look the person up and
  check the admin's grants (BLD-A217).
- **Tiers** are lane A's part, which lane E's stack does not have (BLD-A214; L-ONES.open default): the highest tier
  in `rules/tiers.md` whose hours or money threshold the person's total meets, summed over every shipped idea they
  are credited on with lane E's own figure rules. A new One starts at that tier. An active One's tier only rises,
  and each rise leaves an unseen glow-up for the dashboard's moment (S-ONE, L-ONES.rules/3; J-ONE step 6).
- **The office screen** (S-OFFICE) reads `ones.measures`, so the idea's counted figures are copied there.

No Inbox item is posted for a new One or a tier rise at launch (BLD-A186): the moment shows on /one, the Wall and the
office screen.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from psycopg.types.json import Jsonb

from core.config import get_settings
from core.db import Conn
from programme.common import Refused, audit, log, need, now_utc, user_by_email
from wall import ones as lane_e
from wall.common import Refused as LaneERefused
from wall.impact import hours_a_month, latest_figures, measurement_rows, rupees_a_year

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
MSG_NOT_A_ONE = "That One is not on the list any more."


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


# --- What counts (lane E's figure rules) ---------------------------------------------------------------------------


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
    """Hours a month and rupees a year across every shipped idea the person is credited on: the latest figure of each
    measure that counts (money only once Finance confirmed it), as the Wall and S-ONE count them."""
    hours = money = 0.0
    for rows in measurement_rows(conn, credited_shipped_ideas(conn, user_id)).values():
        figures = latest_figures(rows)
        if "time" in figures:
            hours += hours_a_month(figures["time"])
        if "money" in figures:
            money += rupees_a_year(figures["money"])
    return hours, money


def one_measures(conn: Conn, idea_uuid: str) -> dict[str, Any]:
    """The idea's counted figures in the shape `ones.measures` has always had (`{value, unit}`, money with its
    Finance flag), which the office screen and lane E's `figures_from_measures` read."""
    figures = latest_figures(measurement_rows(conn, [idea_uuid]).get(idea_uuid, []))
    out: dict[str, Any] = {}
    for key, f in figures.items():
        if f.amount is None:
            continue
        value: int | float = int(f.amount) if f.amount == int(f.amount) else f.amount
        out[key] = {"value": value, "unit": f.unit}
        if key == "money":
            out[key]["finance_confirmed"] = True  # counted money is Finance-confirmed by definition
    return out


# --- Becoming a One, and rising (J-ONE steps 3 and 6) ----------------------------------------------------------------


def on_measurement(
    conn: Conn, idea_row: dict[str, Any], measurement_id: int, actor: str, now: dt.datetime
) -> dict[str, list[dict[str, Any]]]:
    """Call inside the transaction that entered or confirmed a measurement. Inducts whoever the rules now make a One
    (lane E), sets or raises tiers, refreshes the Ones' measures. Idempotent: nothing happens until a figure counts."""
    out: dict[str, list[dict[str, Any]]] = {"inducted": [], "tier_rises": []}
    idea_uuid = str(idea_row["id"])
    if idea_row["status"] != "shipped" or not lane_e.impact_confirmed(conn, idea_uuid):
        return out
    made = {m["user_id"]: dict(m) for m in lane_e.induct_for_idea(conn, idea_uuid, actor=actor, now=now)}
    rules = tier_rules()
    for user_id in lane_e.credited_users(conn, idea_uuid):
        one = conn.execute(
            "SELECT id, tier FROM ones WHERE user_id = %s AND status = 'active' FOR UPDATE", (user_id,)
        ).fetchone()
        if one is None:
            continue  # removed by an admin: their call stands
        one_id, was = int(one["id"]), int(one["tier"])
        tier = tier_for(*person_totals(conn, user_id), rules)
        if user_id in made:
            made[user_id]["tier"] = max(tier, was)
        if tier <= was:
            continue  # a tier never falls on its own (rules/tiers.md)
        conn.execute("UPDATE ones SET tier = %s WHERE id = %s", (tier, one_id))
        conn.execute("UPDATE users SET tier = %s WHERE id = %s", (tier, user_id))
        if user_id in made:  # a new One starts at their measured tier: no moment for a rise they never saw
            audit(conn, actor, "ones.tier_set", f"one:{one_id}", {"tier": tier, "measurement_id": measurement_id},
                  before={"tier": was})  # fmt: skip
            continue
        conn.execute(
            "INSERT INTO one_glow_ups (one_id, proposal_id, measurement_id, tier_from, tier_to, created_at) "
            "VALUES (%s, NULL, %s, %s, %s, %s)",
            (one_id, measurement_id, was, tier, now),
        )
        audit(conn, actor, "ones.tier_rose", f"one:{one_id}",
              {"tier_from": was, "tier_to": tier, "measurement_id": measurement_id},
              before={"tier": was})  # fmt: skip
        out["tier_rises"].append({"user_id": user_id, "one_id": one_id, "tier_from": was, "tier_to": tier})
    out["inducted"] = sorted(made.values(), key=lambda m: m["one_id"])
    measures = one_measures(conn, idea_uuid)
    if measures:
        conn.execute(
            "UPDATE ones SET measures = %s WHERE idea_id = %s AND way_in = 'accepted_idea'",
            (Jsonb(measures), idea_row["idea_id"]),
        )
    return out


# --- The admin path (DEC-106): lane E's calls, reached from the admin page -----------------------------------------


def _lane_e(exc: LaneERefused, field: str | None = None) -> Refused:
    """Lane E's refusal in this package's shape, with the admin page's own words where lane E sends none."""
    words = {"forbidden": "You can't do this. Ask an admin.", "not_found": MSG_NOT_A_ONE}
    return Refused(exc.status, exc.code, exc.message or words.get(exc.code, ""), field=exc.field or field)


def mark_founding(
    conn: Conn, actor: str, body: dict[str, Any], now: dt.datetime | None = None
) -> dict[str, Any]:
    """An admin marks a Founding One by work email (L-ONES.rules/1, DEC-102): `wall.ones.mark_founding`."""
    now = now or now_utc()
    need(conn, actor, {"admin"})
    user_id = user_by_email(conn, body.get("email"), "email")
    already = conn.execute(
        "SELECT 1 FROM ones WHERE user_id = %s AND status = 'active' AND way_in = 'founding'", (user_id,)
    ).fetchone()
    if already is not None:
        raise Refused(409, "already_founding", "That person is already a Founding One.", field="email")
    try:
        return lane_e.mark_founding(conn, actor, user_id, now=now)
    except LaneERefused as exc:
        raise _lane_e(exc, "email") from None


def remove_one(conn: Conn, actor: str, one_id: Any, now: dt.datetime | None = None) -> dict[str, Any]:
    """An admin removes a One from the admin page's list (DEC-106): `wall.ones.remove_one`."""
    now = now or now_utc()
    need(conn, actor, {"admin"})
    try:
        oid = int(one_id)
    except (TypeError, ValueError):
        raise Refused(404, "not_found", MSG_NOT_A_ONE) from None
    row = conn.execute("SELECT user_id FROM ones WHERE id = %s AND status = 'active'", (oid,)).fetchone()
    if row is None:
        raise Refused(404, "not_found", MSG_NOT_A_ONE)
    try:
        return lane_e.remove_one(conn, actor, str(row["user_id"]), now=now)
    except LaneERefused as exc:
        raise _lane_e(exc) from None


def list_ones(conn: Conn) -> list[dict[str, Any]]:
    """Active Ones for the admin page, by number (staff only: names and work emails, to act on the right person)."""
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
