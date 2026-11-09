"""Fairness and calibration reports (§3.8, §4.12 step 6, §5.4, §5.9 step 5), for admins and the core committee.

Names are removed and every count under 5 shows as "fewer than 5", so no person can be picked out of a small
group (BLD-223). The groups by LOB and location are suppressed on distinct people, not contributions, so one person
with several ideas cannot be read off. Periods are whole calendar quarters (IST), never free dates, so two
overlapping periods cannot be subtracted to expose a single event. Personal attributes are used only in aggregate: the contributor's LOB and location from the HR
directory (grade is "Coming soon": the HR export has no grade field yet).

- **Fairness** for a period: time-limit breaches by stage, overrides (capacity and below-threshold shortlists),
  recusals, identity reveals, appeals and their outcomes by deciding body, score-consistency flags, and
  shortlisting and acceptance rates by contributor LOB and location.
- **Calibration** for a period: the AI pre-score against the committee's medians per dimension (mean gap, share
  within one level, "AI differs" flags), and how often the review desk changed each kind of proposal.
Measured outcomes against estimates (§5.4) need the measure-and-close stage and are "Coming soon".
"""

from __future__ import annotations

import datetime as dt
import re
import statistics
from typing import Any
from zoneinfo import ZoneInfo

from core.db import Conn

SMALL = 5
IST = ZoneInfo("Asia/Kolkata")
QUARTER = re.compile(r"([0-9]{4})-Q([1-4])")


def _n(value: int) -> int | str:
    return value if value >= SMALL or value == 0 else "fewer than 5"


def _rate(part: int, whole: int) -> float | str:
    if whole < SMALL:
        return "too few to show"
    return round(part / whole, 3)


def _quarter_start(year: int, q: int) -> dt.datetime:
    if q == 5:
        year, q = year + 1, 1
    return dt.datetime(year, 3 * (q - 1) + 1, 1, tzinfo=IST)


def current_quarter(now: dt.datetime | None = None) -> str:
    local = (now or dt.datetime.now(dt.UTC)).astimezone(IST)
    return f"{local.year}-Q{(local.month - 1) // 3 + 1}"


def recent_quarters(count: int = 8, now: dt.datetime | None = None) -> list[str]:
    """The current quarter and the ones before it, newest first (the choices on the reports page)."""
    year, q = (int(x) for x in current_quarter(now).replace("Q", "").split("-"))
    out = []
    for _ in range(count):
        out.append(f"{year}-Q{q}")
        year, q = (year, q - 1) if q > 1 else (year - 1, 4)
    return out


def period(quarter: str | None, now: dt.datetime | None = None) -> tuple[dt.datetime, dt.datetime]:
    """A whole calendar quarter in IST, as KFintech reports (default: the current one, up to now)."""
    m = QUARTER.fullmatch(quarter or current_quarter(now))
    if not m:
        raise ValueError("bad_quarter")
    year, q = int(m.group(1)), int(m.group(2))
    start, end = _quarter_start(year, q), _quarter_start(year, q + 1)
    now = now or dt.datetime.now(dt.UTC)
    if start > now:
        raise ValueError("future_quarter")
    return start.astimezone(dt.UTC), min(end, now).astimezone(dt.UTC)


def fairness(conn: Conn, start: dt.datetime, end: dt.datetime) -> dict[str, Any]:
    breaches = conn.execute(
        "SELECT stage, count(*) AS n FROM sla_timers WHERE state = 'breached' AND escalated_at BETWEEN %s AND %s "
        "GROUP BY stage ORDER BY stage",
        (start, end),
    ).fetchall()
    overrides = conn.execute(
        "SELECT (SELECT count(*) FROM decisions WHERE override_reason IS NOT NULL AND decided_at BETWEEN %(s)s AND %(e)s) AS capacity, "
        "(SELECT count(*) FROM scoring_rounds WHERE below_threshold_reason IS NOT NULL AND decided_at BETWEEN %(s)s AND %(e)s) AS below",
        {"s": start, "e": end},
    ).fetchone()
    recusals = conn.execute(
        "SELECT count(*) AS n FROM coi_flags WHERE status = 'recused' AND updated_at BETWEEN %s AND %s",
        (start, end),
    ).fetchone()
    reveals = conn.execute(
        "SELECT count(*) AS n FROM audit_log WHERE action LIKE '%%reveal%%' AND at BETWEEN %s AND %s",
        (start, end),
    ).fetchone()
    appeals = conn.execute(
        "SELECT d.body, coalesce(a.outcome, 'open') AS outcome, count(*) AS n FROM appeals a "
        "JOIN decisions d ON d.id = a.decision_id WHERE a.filed_at BETWEEN %s AND %s GROUP BY 1, 2 ORDER BY 1, 2",
        (start, end),
    ).fetchall()
    flags = conn.execute(
        "SELECT count(*) FILTER (WHERE flags <> '{}'::jsonb) AS flagged, count(*) AS rounds FROM scoring_rounds "
        "WHERE revealed_at BETWEEN %s AND %s",
        (start, end),
    ).fetchone()

    def by(attr: str) -> list[dict[str, Any]]:
        # One row per contributor and cluster that reached scoring in the period; outcome from the furthest stage.
        rows = conn.execute(
            f"""
            WITH people AS (
              SELECT DISTINCT r.cluster_id, m.user_id
              FROM scoring_rounds r
              JOIN ideas i ON i.cluster_id = r.cluster_id
              JOIN contributor_map m ON m.contributor_code = i.contributor_code
              WHERE r.revealed_at BETWEEN %s AND %s
            )
            SELECT coalesce(u.{attr}, 'not recorded') AS grp, count(*) AS scored, count(DISTINCT p.user_id) AS people,
                   count(*) FILTER (WHERE EXISTS (SELECT 1 FROM scoring_rounds s WHERE s.cluster_id = p.cluster_id
                                                  AND s.outcome = 'shortlisted')) AS shortlisted,
                   count(*) FILTER (WHERE EXISTS (SELECT 1 FROM decisions d WHERE d.cluster_id = p.cluster_id
                                                  AND d.outcome = 'picked')) AS picked
            FROM people p JOIN users u ON u.id = p.user_id GROUP BY 1 ORDER BY 1
            """,  # noqa: S608 - attr is one of two fixed column names
            (start, end),
        ).fetchall()
        out = []
        for r in rows:
            few = int(r["people"]) < SMALL  # suppress on people, so one person's many ideas show nothing
            out.append(
                {
                    "group": r["grp"],
                    "scored": "fewer than 5" if few else _n(int(r["scored"])),
                    "shortlist_rate": "too few to show"
                    if few
                    else _rate(int(r["shortlisted"]), int(r["scored"])),
                    "pick_rate": "too few to show" if few else _rate(int(r["picked"]), int(r["scored"])),
                }
            )
        return out

    return {
        "period": {"from": start.isoformat(), "to": end.isoformat()},
        "breaches": [{"stage": r["stage"], "count": _n(int(r["n"]))} for r in breaches],
        "overrides": {"capacity_line": _n(int(overrides["capacity"])), "shortlisted_below_threshold": _n(int(overrides["below"]))} if overrides else {},
        "recusals": _n(int(recusals["n"])) if recusals else 0,
        "identity_reveals": _n(int(reveals["n"])) if reveals else 0,
        "appeals": [{"body": r["body"], "outcome": r["outcome"], "count": _n(int(r["n"]))} for r in appeals],
        "score_consistency": {"rounds": _n(int(flags["rounds"])), "with_flags": _n(int(flags["flagged"]))} if flags else {},
        "by_lob": by("lob_id"),
        "by_location": by("location"),
        "coming_soon": ["by_grade", "manager_chain_conflicts"],
    }  # fmt: skip


def calibration(conn: Conn, start: dt.datetime, end: dt.datetime) -> dict[str, Any]:
    rows = conn.execute(
        "SELECT r.id, r.medians, a.dimension, a.value FROM scoring_rounds r JOIN ai_prescores a ON a.round_id = r.id "
        "WHERE r.revealed_at BETWEEN %s AND %s AND r.medians IS NOT NULL",
        (start, end),
    ).fetchall()
    per: dict[str, list[float]] = {}
    for r in rows:
        med = (r["medians"] or {}).get(r["dimension"])
        if med is not None:
            per.setdefault(r["dimension"], []).append(float(r["value"]) - float(med))
    ai = [
        {"dimension": d, "rounds": _n(len(gaps)),
         "mean_gap": round(statistics.fmean(gaps), 2) if len(gaps) >= SMALL else "too few to show",
         "within_one_level": _rate(sum(1 for g in gaps if abs(g) <= 1), len(gaps)),
         "ai_differs": _n(sum(1 for g in gaps if abs(g) >= 2))}
        for d, gaps in sorted(per.items())
    ]  # fmt: skip
    corrections = conn.execute(
        "SELECT c.field, count(*) AS changed FROM corrections c WHERE c.created_at BETWEEN %s AND %s GROUP BY 1 ORDER BY 1",
        (start, end),
    ).fetchall()
    decided = conn.execute(
        "SELECT count(*) AS n FROM review_items WHERE item_type = 'idea' AND decided_at BETWEEN %s AND %s",
        (start, end),
    ).fetchone()
    total = int(decided["n"]) if decided else 0
    return {
        "period": {"from": start.isoformat(), "to": end.isoformat()},
        "prescore_vs_committee": ai,
        "desk_corrections": [
            {
                "field": r["field"],
                "changed": _n(int(r["changed"])),
                "share_of_reviews": _rate(int(r["changed"]), total),
            }
            for r in corrections
        ],
        "reviews": _n(total),
        "coming_soon": ["measured_vs_estimated_value", "priority_class_agreement"],
    }
