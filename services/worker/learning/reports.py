"""Learning reports (§5.4, §5.6, §5.7, §5.8): counts and rates only, never idea text or names."""

from __future__ import annotations

import datetime as dt
import statistics
from typing import Any

from psycopg.types.json import Jsonb

from core.config import get_settings
from core.db import Conn
from core.logging import get_logger

log = get_logger("learning")

WINDOW = 200  # §5.6: the last 200 human decisions per action type
HIGH_BAND = 0.8
PROMOTE_AT = 0.95  # the product lead may switch a type to auto only at or above this (§5.6); off at launch
DROP_ALERT = 0.05  # §5.7: acceptance down 5 points in a week


def _save(conn: Conn, kind: str, period: str, data: dict[str, Any], now: dt.datetime) -> None:
    conn.execute(
        "INSERT INTO learning_reports (kind, period, data, built_at) VALUES (%s, %s, %s, %s) "
        "ON CONFLICT (kind, period) DO UPDATE SET data = EXCLUDED.data, built_at = EXCLUDED.built_at",
        (kind, period, Jsonb(data), now),
    )


def _alert(conn: Conn, action: str, after: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO audit_log (actor, action, entity, after) VALUES ('process:learning', %s, 'learning', %s)",
        (action, Jsonb(after)),
    )
    log.warning(action, **{k: v for k, v in after.items() if isinstance(v, (int, float, str))})


def rate(accepted: int, total: int) -> float | None:
    return round(accepted / total, 4) if total else None


# --- §5.6 Autonomy -----------------------------------------------------------------------------------------------


def _decided_items(conn: Conn, limit: int = 2000) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT r.id, r.proposal, r.confidence, coalesce(array_agg(c.field) FILTER (WHERE c.field IS NOT NULL), "
        "'{}') AS corrected FROM review_items r LEFT JOIN corrections c ON c.review_item_id = r.id "
        "WHERE r.item_type = 'idea' AND r.state IN ('decided', 'vetoed') AND r.final ->> 'action' = 'decide' "
        "GROUP BY r.id ORDER BY r.decided_at DESC NULLS LAST, r.id DESC LIMIT %s",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def acceptance(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """For each eligible action type (§5.6): of the last 200 high-confidence proposals, how many the desk accepted
    unchanged. Pure, so it can be tested without a database."""
    checks: dict[str, tuple[Any, str]] = {
        "accept_area_tags": (lambda p: bool((p.get("system") or {}).get("areas")), "system.areas"),
        "accept_scope": (lambda p: (p.get("system") or {}).get("scope") is not None, "system.scope"),
        "attach_to_cluster": (lambda p: bool(p.get("best_same")), "match"),
        "mark_as_new": (lambda p: not p.get("best_same"), "match"),
    }
    out: dict[str, dict[str, Any]] = {}
    for action, (applies, field) in checks.items():
        window = []
        for it in items:
            proposal = it.get("proposal") or {}
            conf = (it.get("confidence") or {}).get(field)
            if not applies(proposal) or (conf is not None and float(conf) < HIGH_BAND):
                continue
            window.append(field not in (it.get("corrected") or []))
            if len(window) >= WINDOW:
                break
        accepted = sum(window)
        r = rate(accepted, len(window))
        out[action] = {"window": len(window), "accepted": accepted, "rate": r,
                       "eligible": bool(r is not None and len(window) >= WINDOW and r >= PROMOTE_AT)}  # fmt: skip
    return out


def autonomy(conn: Conn, now: dt.datetime) -> dict[str, Any]:
    """Daily. Records the windows in `autonomy`; the mode never changes here (autonomy is off at launch)."""
    stats = acceptance(_decided_items(conn))
    with conn.transaction():
        for action, s in stats.items():
            conn.execute(
                "UPDATE autonomy SET window_accept_rate = %s, window_size = %s WHERE action_type = %s",
                (s["rate"], s["window"], action),
            )
        _save(conn, "autonomy", now.date().isoformat(), stats, now)
    return stats


# --- §5.7 Drift ----------------------------------------------------------------------------------------------------


def _week_acceptance(conn: Conn, start: dt.datetime, end: dt.datetime) -> float | None:
    row = conn.execute(
        "SELECT count(*) AS total, count(*) FILTER (WHERE NOT EXISTS (SELECT 1 FROM corrections c "
        "WHERE c.review_item_id = r.id)) AS clean FROM review_items r WHERE r.item_type = 'idea' "
        "AND r.final ->> 'action' = 'decide' AND r.decided_at >= %s AND r.decided_at < %s",
        (start, end),
    ).fetchone()
    return rate(int(row["clean"]), int(row["total"])) if row else None


def drift(conn: Conn, now: dt.datetime) -> dict[str, Any]:
    """Weekly dashboard (§5.7): acceptance this week and last, model cost a day, calls and failures by agent
    version, scan time and the share of scans that fell back to the slow path."""
    week = dt.timedelta(days=7)
    this, last = _week_acceptance(conn, now - week, now), _week_acceptance(conn, now - 2 * week, now - week)
    agents = [
        {"agent": r["agent"], "version": r["prompt_version"], "calls": int(r["calls"]),
         "failed": int(r["failed"]), "cost_inr": float(r["cost"] or 0)}
        for r in conn.execute(
            "SELECT agent, prompt_version, count(*) AS calls, count(*) FILTER (WHERE outcome NOT IN "
            "('ok', 'ok_after_retry', 'cached')) AS failed, sum(cost_inr) AS cost FROM llm_calls "
            "WHERE created_at >= %s GROUP BY agent, prompt_version ORDER BY agent, prompt_version",
            (now - week,),
        ).fetchall()
    ]  # fmt: skip
    cost_a_day = round(sum(a["cost_inr"] for a in agents) / 7, 2)
    scans = conn.execute(
        "SELECT extract(epoch FROM finished_at - started_at) AS s, attempts, state FROM scans "
        "WHERE finished_at >= %s AND started_at IS NOT NULL",
        (now - week,),
    ).fetchall()
    secs = sorted(float(r["s"]) for r in scans if r["s"] is not None)
    data = {
        "acceptance_this_week": this,
        "acceptance_last_week": last,
        "cost_a_day_inr": cost_a_day,
        "agents": agents,
        "scans": len(scans),
        "scan_seconds_median": round(statistics.median(secs), 1) if secs else None,
        "scan_seconds_p95": round(secs[min(len(secs) - 1, int(len(secs) * 0.95))], 1) if secs else None,
        "fallback_rate": rate(sum(1 for r in scans if int(r["attempts"] or 0) > 1 or r["state"] == "manual"),
                              len(scans)),
        "pre_score_gap": None,  # arrives with the committee flow's AI pre-score
    }  # fmt: skip
    budget = float(getattr(get_settings(), "llm_daily_budget_inr", 0) or 0)
    with conn.transaction():
        _save(conn, "drift", now.strftime("%G-W%V"), data, now)
        if this is not None and last is not None and last - this >= DROP_ALERT:
            _alert(conn, "alert.drift_acceptance", {"this_week": this, "last_week": last})
        if budget and cost_a_day > budget:
            _alert(conn, "alert.drift_cost", {"cost_a_day_inr": cost_a_day, "budget_inr": budget})
    return data


# --- §5.8 The canvas ----------------------------------------------------------------------------------------------


def canvas(conn: Conn, now: dt.datetime) -> dict[str, Any]:
    """Monthly (§5.8): for last month's full canvases, how often each question was left empty; time to complete;
    how many quick captures were enriched later. Changes to questions stay product-team decisions."""
    first = now.date().replace(day=1)
    start = dt.datetime.combine((first - dt.timedelta(days=1)).replace(day=1), dt.time(), tzinfo=dt.UTC)
    end = dt.datetime.combine(first, dt.time(), tzinfo=dt.UTC)
    rows = conn.execute(
        "SELECT capture_mode, strength, canvas, extract(epoch FROM submitted_at - created_at) AS s FROM ideas "
        "WHERE submitted_at >= %s AND submitted_at < %s",
        (start, end),
    ).fetchall()
    keys = ("one_line", "details", "who", "value", "ecosystem", "solution")
    full = [r for r in rows if r["capture_mode"] == "full"]
    skipped = {k: rate(sum(1 for r in full if not (r["canvas"] or {}).get(k)), len(full)) for k in keys}
    minutes = sorted(float(r["s"]) / 60 for r in full if r["s"] is not None)
    quick = [r for r in rows if r["capture_mode"] == "quick"]
    data = {
        "ideas": len(rows), "full": len(full), "quick": len(quick),
        "skip_rate": skipped,
        "minutes_to_complete_median": round(statistics.median(minutes), 1) if minutes else None,
        "quick_enriched": sum(1 for r in quick if (r["strength"] or 0) >= 3),
        "predicts_pick": None,  # needs the committee's picks to accumulate (coming soon)
    }  # fmt: skip
    with conn.transaction():
        _save(conn, "canvas", start.strftime("%Y-%m"), data, now)
    return data


# --- §5.4 Outcome calibration --------------------------------------------------------------------------------------


def quarter_of(day: dt.date) -> tuple[str, dt.date, dt.date]:
    q = (day.month - 1) // 3
    start = dt.date(day.year, q * 3 + 1, 1)
    end = dt.date(day.year + (q == 3), (q * 3 + 3) % 12 + 1, 1)
    return f"{day.year}-Q{q + 1}", start, end


def calibration(conn: Conn, now: dt.datetime, *, previous: bool = True) -> dict[str, Any]:
    """Quarterly (§5.4): for every delivery closed in the quarter, actual against target, by category and play.
    Proposals to adjust bands and multipliers are coming soon; the core committee will approve them."""
    day = now.date()
    if previous:
        day = quarter_of(day)[1] - dt.timedelta(days=1)
    period, start, end = quarter_of(day)
    rows = conn.execute(
        "SELECT d.id, d.outcome, m.results, coalesce(i.category, 'not_sure') AS category, "
        "coalesce(i.play, 'other') AS play FROM deliveries d "
        "JOIN delivery_measurements m ON m.delivery_id = d.id AND m.mark = 'day_90' "
        "LEFT JOIN ideas i ON d.subject_type = 'idea' AND i.idea_id = d.subject_id "
        "WHERE d.state = 'closed' AND d.closed_at >= %s AND d.closed_at < %s",
        (start, end),
    ).fetchall()

    def summary(group: list[dict[str, Any]]) -> dict[str, Any]:
        ratios = [float(r["results"]["actual_vs_target"]) for r in group
                  if (r["results"] or {}).get("actual_vs_target") is not None]  # fmt: skip
        return {
            "closed": len(group),
            "target_met": sum(1 for r in group if r["outcome"] == "target_met"),
            "median_actual_vs_target": round(statistics.median(ratios), 3) if ratios else None,
        }

    rows_d = [dict(r) for r in rows]
    data: dict[str, Any] = {"period": period, **summary(rows_d), "by_category": {}, "by_play": {}}
    for key, field in (("by_category", "category"), ("by_play", "play")):
        for value in sorted({r[field] for r in rows_d}):
            data[key][value] = summary([r for r in rows_d if r[field] == value])
    with conn.transaction():
        _save(conn, "calibration", period, data, now)
    return data
