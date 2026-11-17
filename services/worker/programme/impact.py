"""What a shipped idea changed (L-IMPACT; J-ONE steps 2 and 6). The write side; lane E's Wall and S-ONE read it.

- Shipping schedules two measurements (`schedule`, called by `build.mark_shipped`): 30 and 90 days after, from
  rules/promises.md `impact.check_days` (L-IMPACT/1). These two due dates are the clocks: the Wall's live-fixes table
  shows "Due 18 Nov" from them, and the admin page lists what is due, late ones marked (BLD-A213).
- An admin enters a measurement for the team that runs the fix (`enter`; L-IMPACT/2, /3, /8 default). Values per
  measure, in the shape lane E's reader documents (`wall/impact.py`): `{"amount", "unit", "line"}`, plus an optional
  plain sentence. The 30-day one comes before the 90-day one. A change to the money figure clears Finance's
  confirmation.
- Money shows only once a second person confirms it for Finance (`finance_confirm`; L-IMPACT/3): an admin who did
  not enter the figures (BLD-A213; as BLD-126 did for deliveries).
- Every entry and confirmation runs the Ones' rules (`programme.ones.on_measurement`): lane E's induction, then the
  tiers (J-ONE steps 3 and 6).
- No Inbox item is posted when a measurement lands (BLD-A211): E-ENUMS.inbox has no kind for it. The sharer sees the
  figures on their idea's Shipped stage (L-IMPACT/5).
"""

from __future__ import annotations

import datetime as dt
import math
from typing import Any

from psycopg.types.json import Jsonb

from core.db import Conn
from programme import ones
from programme.common import Refused, audit, day_label, idea, need, now_utc, promise, text

MARKS = ("day_30", "day_90")
MARK_LABEL = {"day_30": "30 days", "day_90": "90 days"}
UNITS = {"time": "hours a month", "money": "rupees a year", "effort": "fewer steps"}
SCALE_NOUNS = ("branches", "teams", "distributors", "investors")  # L-IMPACT/2
MAX_AMOUNT = 10**12
LINE_MAX, SENTENCE_MAX = 80, 200

MSG_AMOUNT = "Enter a number of 0 or more."
MSG_LINE = "Keep this line under 80 characters."
MSG_SENTENCE = "Keep the sentence under 200 characters."


def _amount(raw: Any, field: str) -> float | None:
    if raw is None or raw == "":
        return None
    try:
        value = float(str(raw).replace(",", "").strip()) if isinstance(raw, str) else float(raw)
    except (TypeError, ValueError):
        raise Refused(422, "amount_not_valid", MSG_AMOUNT, field=field) from None
    if isinstance(raw, bool) or not math.isfinite(value) or not 0 <= value <= MAX_AMOUNT:
        raise Refused(422, "amount_not_valid", MSG_AMOUNT, field=field)
    return int(value) if value == int(value) else round(value, 2)


def _line(raw: Any, field: str) -> str | None:
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    return text(raw, field, min_chars=1, max_chars=LINE_MAX, message=MSG_LINE)


def parse(body: dict[str, Any]) -> dict[str, Any]:
    """The measurement form as `results` (L-IMPACT/2). At least one figure above zero: a measured difference."""
    results: dict[str, Any] = {}
    for key in ("time", "money", "effort", "scale"):
        part = body.get(key)
        if not isinstance(part, dict):
            continue
        amount = _amount(part.get("amount"), f"{key}.amount")
        if amount is None:
            continue
        if key == "scale":
            unit = part.get("unit")
            if unit not in SCALE_NOUNS:
                raise Refused(422, "scale_unit", "Choose who it reaches.", field="scale.unit")
        else:
            unit = UNITS[key]
        figure: dict[str, Any] = {"amount": amount, "unit": unit}
        if key != "money":  # the money tile's line is always "Finance confirmed", set by the reader
            line = _line(part.get("line"), f"{key}.line")
            if line:
                figure["line"] = line
        results[key] = figure
    if not results:
        raise Refused(422, "no_figures", "Enter at least one figure.", field="time.amount")
    if not any(float(f["amount"]) > 0 for f in results.values()):
        raise Refused(422, "no_difference", "Enter at least one figure above zero.", field="time.amount")
    sentence = body.get("sentence")
    if isinstance(sentence, str) and sentence.strip():
        results["sentence"] = text(
            sentence, "sentence", min_chars=1, max_chars=SENTENCE_MAX, message=MSG_SENTENCE
        )
    return results


def schedule(conn: Conn, idea_uuid: str, shipped_at: dt.datetime) -> None:
    """Two measurement points after shipping (L-IMPACT/1). Safe to call again: existing points are kept."""
    days = list(promise("impact", "check_days", [30, 90]))[: len(MARKS)]
    for mark, after in zip(MARKS, days, strict=False):
        conn.execute(
            "INSERT INTO delivery_measurements (idea_uuid, mark, due_at) VALUES (%s, %s, %s) "
            "ON CONFLICT (idea_uuid, mark) WHERE idea_uuid IS NOT NULL DO NOTHING",
            (idea_uuid, mark, shipped_at + dt.timedelta(days=int(after))),
        )


def _measurement(conn: Conn, row: dict[str, Any], mark: Any) -> dict[str, Any]:
    if mark not in MARKS:
        raise Refused(404, "not_found", "Choose the 30-day or the 90-day check.", field="mark")
    if row["status"] != "shipped":
        raise Refused(
            409, "not_shipped", "Only a shipped idea is measured. Mark it shipped first.", field="idea"
        )
    # An idea shipped before this path existed (or by the seed) gets its two points now.
    schedule(conn, str(row["id"]), row["status_changed_at"] or now_utc())
    m = conn.execute(
        "SELECT * FROM delivery_measurements WHERE idea_uuid = %s AND mark = %s FOR UPDATE", (row["id"], mark)
    ).fetchone()
    assert m is not None
    return dict(m)


def enter(
    conn: Conn, actor: str, ref: Any, mark: Any, body: dict[str, Any], now: dt.datetime | None = None
) -> dict[str, Any]:
    now = now or now_utc()
    need(conn, actor, {"admin"})
    results = parse(body)
    with conn.transaction():
        row = idea(conn, ref, lock=True)
        m = _measurement(conn, row, mark)
        if mark == "day_90":
            first = conn.execute(
                "SELECT filled_at FROM delivery_measurements WHERE idea_uuid = %s AND mark = 'day_30'",
                (row["id"],),
            ).fetchone()
            if first is None or first["filled_at"] is None:
                raise Refused(409, "day_30_first", "Enter the 30-day figures first.", field="mark")
        old_money = (m["results"] or {}).get("money")
        keep_finance = m["finance_confirmed_at"] is not None and old_money == results.get("money")
        conn.execute(
            "UPDATE delivery_measurements SET results = %s, filled_by = %s, filled_at = %s, "
            "finance_confirmed_by = CASE WHEN %s THEN finance_confirmed_by END, "
            "finance_confirmed_at = CASE WHEN %s THEN finance_confirmed_at END WHERE id = %s",
            (Jsonb(results), actor, now, keep_finance, keep_finance, m["id"]),
        )
        audit(conn, actor, "impact.measurement_entered", f"idea:{row['idea_id']}",
              {"measurement_id": m["id"], "mark": mark, "measures": sorted(k for k in results if k != "sentence"),
               "waits_for_finance": "money" in results and not keep_finance},
              before={"entered": m["filled_at"] is not None})  # fmt: skip
        changed = ones.on_measurement(conn, row, int(m["id"]), actor, now)
    return {"idea": row["idea_id"], "mark": mark, "waits_for_finance": "money" in results and not keep_finance,
            **changed}  # fmt: skip


def finance_confirm(
    conn: Conn, actor: str, ref: Any, mark: Any, now: dt.datetime | None = None
) -> dict[str, Any]:
    now = now or now_utc()
    need(conn, actor, {"admin"})
    with conn.transaction():
        row = idea(conn, ref, lock=True)
        m = _measurement(conn, row, mark)
        if m["filled_at"] is None or "money" not in (m["results"] or {}):
            raise Refused(409, "no_money_figure", "There is no money figure to confirm yet.", field="mark")
        if m["finance_confirmed_at"] is not None:
            raise Refused(
                409, "already_confirmed", "Finance has already confirmed this figure.", field="mark"
            )
        if str(m["filled_by"]) == actor:
            raise Refused(403, "own_entry", "Someone other than the person who entered the figures confirms them.",
                          field="mark")  # fmt: skip
        conn.execute(
            "UPDATE delivery_measurements SET finance_confirmed_by = %s, finance_confirmed_at = %s WHERE id = %s",
            (actor, now, m["id"]),
        )
        audit(conn, actor, "impact.finance_confirmed", f"idea:{row['idea_id']}",
              {"measurement_id": m["id"], "mark": mark})  # fmt: skip
        changed = ones.on_measurement(conn, row, int(m["id"]), actor, now)
    return {"idea": row["idea_id"], "mark": mark, "finance_confirmed": True, **changed}


# --- What the admin page lists ---------------------------------------------------------------------------------


def due(conn: Conn, now: dt.datetime) -> list[dict[str, Any]]:
    """Measurements not yet entered for shipped ideas, the soonest first: "Due 18 Nov" (L-IMPACT/4)."""
    rows = conn.execute(
        "SELECT m.id, m.mark, m.due_at, i.idea_id, i.title FROM delivery_measurements m JOIN ideas i ON i.id = "
        "m.idea_uuid WHERE m.filled_at IS NULL AND i.status = 'shipped' ORDER BY m.due_at, i.idea_id, m.mark"
    ).fetchall()
    return [
        {"id": int(r["id"]), "idea_ref": r["idea_id"], "title": r["title"] or "", "mark": r["mark"],
         "check": MARK_LABEL[r["mark"]], "due_at": r["due_at"].isoformat(),
         "due_label": f"Due {day_label(r['due_at'])}", "overdue": r["due_at"] <= now}
        for r in rows
    ]  # fmt: skip


def entered(conn: Conn) -> list[dict[str, Any]]:
    """Measurements entered, newest first, with whether money waits for Finance and who may confirm it."""
    rows = conn.execute(
        "SELECT m.id, m.mark, m.results, m.filled_at, m.filled_by, m.finance_confirmed_at, i.idea_id, i.title "
        "FROM delivery_measurements m JOIN ideas i ON i.id = m.idea_uuid WHERE m.filled_at IS NOT NULL "
        "ORDER BY m.filled_at DESC LIMIT 50"
    ).fetchall()
    out = []
    for r in rows:
        results = r["results"] or {}
        out.append(
            {"id": int(r["id"]), "idea_ref": r["idea_id"], "title": r["title"] or "", "mark": r["mark"],
             "check": MARK_LABEL[r["mark"]], "results": results, "entered_by": str(r["filled_by"]),
             "has_money": "money" in results, "finance_confirmed": r["finance_confirmed_at"] is not None}
        )  # fmt: skip
    return out
