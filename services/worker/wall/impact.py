"""What shipped ideas changed, read side (L-IMPACT, S-WALL.impact, S-ONE "Impact so far").

Measurements live in `delivery_measurements` keyed by `idea_uuid` (cut-over): one row per mark (`day_30`,
`day_90`), `filled_at` once the team that runs the fix entered it, `finance_confirmed_at` once Finance confirmed the
money. The rules read here:

- A figure counts once it is entered (L-IMPACT/3: the team that runs the fix enters it; the pack has no sponsor
  step). Money counts, anywhere, only once Finance has confirmed it (L-IMPACT/3); unconfirmed money is never shown.
- The latest measured figure wins, measure by measure (L-IMPACT/4): a 90-day row that did not re-measure money
  leaves the 30-day money standing.
- Wall totals are sums over shipped fixes on the Wall; "Fixes shipped and measured" counts those with at least one
  entered measurement (L-IMPACT/6). Adoption by other teams (L-IMPACT/7) has no record yet and adds nothing.

`results` shape. The writer (lane A's admin form, L-IMPACT/8) should write, per measure,
`{"amount": <number>, "unit": "<unit>", "line": "<the line under the figure>"}` and an optional `"sentence"`:
  time   unit "hours a month" (or "hours a year", "days a year")     line e.g. "Fewer bounced-debit cases"
  money  unit "rupees a year" or "rupees a month", amount in rupees  (line is always "Finance confirmed")
  effort unit e.g. "fewer steps"                                     line e.g. "Per new mandate"
  scale  unit the noun reached, e.g. "branches", "distributors"      line e.g. "Using it every day"
The synthetic seed's older form, `{"value": "620", "line": "hours a month"}` (figure as text, unit in `line`; when
the figure already carries its words, as `{"value": "2 fewer steps", "line": "per online form"}`, `line` is the line
under it), is read too, as are the Ones' own `measures` from before the cut-over (`{"value": 620, "unit": …}`).
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from typing import Any

from core.db import Conn
from wall.common import day_label, indian, on_wall_sql, public_text, rupees, rupees_text

MEASURES = ("time", "money", "effort", "scale")
BEING_MEASURED = "Being measured"  # S-WALL.impact live-fixes table, a fix before its 30-day mark
FINANCE_CONFIRMED = "Finance confirmed"  # S-ONE "Impact so far", the Money tile

_NUM = re.compile(r"(\d[\d,]*(?:\.\d+)?)")
_AMOUNT_ONLY = re.compile(r"^\s*₹?\s*\d[\d,]*(?:\.\d+)?\s*%?")  # the number at the head of a figure


@dataclass(frozen=True)
class Figure:
    key: str
    amount: float | None  # a number to add up, when there is one
    unit: str
    display: str  # "620 hours a month", "₹18 lakh a year"
    line: str | None  # the line under it on S-ONE


def _number(text: Any) -> float | None:
    if isinstance(text, int | float):
        return float(text)
    m = _NUM.search(str(text or ""))
    return float(m.group(1).replace(",", "")) if m else None


def _rupee_amount(text: Any) -> float | None:
    """'₹18 lakh' → 1,800,000; '₹1.2 crore' → 12,000,000; '₹45,000' → 45,000; a number stays as it is."""
    n = _number(text)
    if n is None or isinstance(text, int | float):
        return n
    words = str(text).lower()
    if "crore" in words or re.search(r"\bcr\b", words):
        return n * 1e7
    if "lakh" in words or "lac" in words:
        return n * 1e5
    return n


def figure(key: str, raw: Any) -> Figure | None:
    """One measure as the screens show it, from either stored form (module docstring)."""
    if not isinstance(raw, dict):
        return None
    if raw.get("unit"):
        unit = str(raw["unit"]).strip()
        source = raw.get("amount", raw.get("value"))
        amount = _rupee_amount(source) if key == "money" else _number(source)
        if amount is None:
            return None
        if key == "money":
            period = "a month" if "month" in unit else "a year"
            display = f"{rupees_text(amount)} {period}"
        else:
            display = f"{indian(amount)} {unit}"
        line = str(raw.get("line") or "").strip() or None
        return Figure(key, amount, unit, display, line)
    value, unit = str(raw.get("value") or "").strip(), str(raw.get("line") or "").strip()
    if not value:
        return None
    amount = _rupee_amount(value) if key == "money" else _number(value)
    words = _AMOUNT_ONLY.sub("", value).strip()
    if key != "money" and words:
        # The figure already says what it counts ("2 fewer steps"), so `line` is what goes under it ("per online
        # form" → "Per online form"), as S-ONE draws "3 fewer steps" / "Per new mandate".
        line = unit[:1].upper() + unit[1:] if unit else None
        return Figure(key, amount, words, value, line)
    return Figure(key, amount, unit, f"{value} {unit}".strip(), None)


def hours_a_month(f: Figure) -> float:
    if f.amount is None:
        return 0.0
    unit = f.unit.lower()
    if "day" in unit:
        return f.amount * 8 / (12 if "year" in unit else 1)  # an 8-hour working day
    if "hour" in unit:
        return f.amount / 12 if "year" in unit else f.amount
    return 0.0


def rupees_a_year(f: Figure) -> float:
    if f.amount is None:
        return 0.0
    return f.amount * 12 if "month" in f.unit.lower() else f.amount


def scale_noun(f: Figure) -> str:
    words = f.unit.lower().split()
    return words[0] if words else "people"


# --- Per idea -----------------------------------------------------------------------------------------------------


def measurement_rows(conn: Conn, idea_uuids: list[Any]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    if not idea_uuids:
        return out
    for r in conn.execute(
        "SELECT idea_uuid, mark, due_at, results, filled_at, finance_confirmed_at FROM delivery_measurements "
        "WHERE idea_uuid = ANY(%s::uuid[]) ORDER BY idea_uuid, (mark = 'day_90') DESC, filled_at DESC NULLS LAST",
        ([str(u) for u in idea_uuids],),
    ).fetchall():
        out.setdefault(str(r["idea_uuid"]), []).append(dict(r))
    return out


def latest_figures(rows: list[dict[str, Any]]) -> dict[str, Figure]:
    """The latest entered figure for each measure (L-IMPACT/4); money only once Finance confirmed it."""
    out: dict[str, Figure] = {}
    for r in rows:  # day_90 before day_30
        if r["filled_at"] is None:
            continue
        results = r["results"] or {}
        for key in MEASURES:
            if key in out or key not in results:
                continue
            if key == "money" and r["finance_confirmed_at"] is None:
                continue
            f = figure(key, results[key])
            if f is not None:
                out[key] = f
    return out


def as_impact(figures: dict[str, Figure]) -> dict[str, Any]:
    """E-ENTITIES Impact: the four tiles of S-ONE ("620 hours a month" / its line). Public text is re-checked."""
    out: dict[str, Any] = {}
    for key in MEASURES:
        f = figures.get(key)
        if f is None or public_text(f.display) is None:
            continue
        if key == "money":
            out[key] = {"value": f.display, "line": FINANCE_CONFIRMED, "finance_confirmed": True}
        else:
            out[key] = {"value": f.display, "line": public_text(f.line) or ""}
    return out


def idea_impact(conn: Conn, idea_uuid: Any) -> dict[str, Any]:
    return as_impact(latest_figures(measurement_rows(conn, [idea_uuid]).get(str(idea_uuid), [])))


def figures_from_measures(measures: dict[str, Any] | None) -> dict[str, Figure]:
    """A One's own `measures` from before the cut-over (money only with its Finance flag)."""
    out: dict[str, Figure] = {}
    for key in MEASURES:
        raw = (measures or {}).get(key)
        if key == "money" and not (isinstance(raw, dict) and raw.get("finance_confirmed")):
            continue
        f = figure(key, raw)
        if f is not None:
            out[key] = f
    return out


# --- The Wall: totals and live fixes ---------------------------------------------------------------------------------


def _shipped(conn: Conn) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in conn.execute(
            "SELECT i.id, i.idea_id, i.title, coalesce(i.status_changed_at, i.updated_at) AS shipped_at, "  # noqa: S608 (fragments are this package's own)
            "bt.name AS team FROM ideas i LEFT JOIN build_teams bt ON bt.idea_uuid = i.id "
            f"WHERE i.status = 'shipped' AND i.idea_id IS NOT NULL AND {on_wall_sql('i')} "
            "ORDER BY shipped_at DESC, i.idea_id"
        ).fetchall()
    ]


def totals(conn: Conn) -> dict[str, Any]:
    ideas = _shipped(conn)
    rows = measurement_rows(conn, [i["id"] for i in ideas])
    hours = money = 0.0
    measured = 0
    reached: dict[str, float] = {}
    for idea in ideas:
        mine = rows.get(str(idea["id"]), [])
        if any(r["filled_at"] is not None for r in mine):
            measured += 1
        figs = latest_figures(mine)
        if "time" in figs:
            hours += hours_a_month(figs["time"])
        if "money" in figs:
            money += rupees_a_year(figs["money"])
        if "scale" in figs and figs["scale"].amount is not None:
            noun = scale_noun(figs["scale"])
            reached[noun] = reached.get(noun, 0.0) + figs["scale"].amount
    noun, count = max(reached.items(), key=lambda kv: (kv[1], kv[0])) if reached else ("distributors", 0.0)
    return {
        "hours_month": round(hours),
        "money_year": round(money),
        "fixes_measured": measured,
        "reached": {"count": round(count), "noun": noun},
    }


def tiles(t: dict[str, Any]) -> list[dict[str, str]]:
    """The four tiles, screen-ready (S-WALL.impact/4): the number on one line, any "lakh" as its suffix, the unit in
    the label. Labels are the board's; the reached noun follows the data."""
    money_value, money_suffix = rupees(t["money_year"])
    noun = str(t["reached"]["noun"])
    return [
        {"key": "hours_month", "value": indian(t["hours_month"]), "suffix": "", "label": "Hours saved a month"},
        {"key": "money_year", "value": money_value, "suffix": money_suffix, "label": "Saved a year, Finance confirmed"},
        {"key": "fixes_measured", "value": indian(t["fixes_measured"]), "suffix": "", "label": "Fixes shipped and measured"},
        {"key": "reached", "value": indian(t["reached"]["count"]), "suffix": "",
         "label": f"{noun[:1].upper()}{noun[1:]} reached by a shipped fix"},
    ]  # fmt: skip


def live_fixes(conn: Conn, now: dt.datetime) -> list[dict[str, Any]]:
    """S-WALL.impact's table (L-WALL.impact/2): what it is, the measured change, when it was measured (green at 90
    days, amber at 30, grey pending with its due date) and the team that runs it. Measured at 90 first."""
    ideas = _shipped(conn)
    rows = measurement_rows(conn, [i["id"] for i in ideas])
    out = []
    for idea in ideas:
        what = public_text(idea["title"])
        if what is None:
            continue
        mine = rows.get(str(idea["id"]), [])
        filled = [r for r in mine if r["filled_at"] is not None]
        if any(r["mark"] == "day_90" for r in filled):
            measured, label = "90d", "90 days"
        elif filled:
            measured, label = "30d", "30 days"
        else:
            measured, label = "pending", BEING_MEASURED
        change = BEING_MEASURED
        if filled:
            latest = filled[0]
            figs = latest_figures(filled)
            first = next((figs[k].display for k in MEASURES if k in figs), None)
            change = public_text((latest["results"] or {}).get("sentence")) or public_text(first) or ""
        due = None
        if measured == "pending":
            pending = sorted(r["due_at"] for r in mine if r["filled_at"] is None and r["due_at"] is not None)
            if pending:
                due = pending[0]
                label = f"Due {day_label(due, year=False)}"
        out.append(
            {
                "id": idea["idea_id"], "what": what, "change": change, "measured": measured,
                "measured_label": label, "due": due.isoformat() if due else None,
                "team": public_text(idea["team"]) or "", "_shipped": idea["shipped_at"],
            }
        )  # fmt: skip
    rank = {"90d": 0, "30d": 1, "pending": 2}
    out.sort(key=lambda f: (rank[f["measured"]], -f["_shipped"].timestamp() if f["_shipped"] else 0, f["id"]))
    for f in out:
        f.pop("_shipped")
    return out


def wall_impact(conn: Conn, now: dt.datetime) -> dict[str, Any]:
    """`GET /wall/impact` (A-API.wall): `{ totals: ImpactTotals, tiles, live: LiveFix[] }`."""
    t = totals(conn)
    return {"totals": t, "tiles": tiles(t), "live": live_fixes(conn, now)}
