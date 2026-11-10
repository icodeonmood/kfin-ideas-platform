"""Learning from core committee decisions (§5.9, BLD-149) and scoring-band proposals (§3.4, BLD-150).

Read from lane B's committee records (scoring rounds with revealed medians, AI pre-scores, decisions). Counts and
aggregates only; never names, never idea text. Nothing changes a rule on its own (non-negotiable 5): each finding is a
report, and a material one becomes a proposal that the core committee approves or declines on the committee learning
page. Before an approval is recorded, the fairness check (§5.9 step 5) runs on lane B's fairness report; a sharp gap
holds the proposal and says why.

- **Agreement (weekly):** how often the AI pre-score would have put a group above the shortlist line, against what
  the committee did, overall and by deciding body (§5.9 step 4), and the average gap between the AI's rating and the
  committee median on each dimension (§5.4 step 3).
- **What the committee rewards (monthly):** over the trailing 12 months, a small logistic regression of picked
  versus declined on the core committee's revealed medians for the scorecard dimensions. With at least 30 decisions,
  the weights it implies are compared with `rules/scorecard.md`; 10 points or more apart on any dimension becomes a
  proposal for the chair.
- **Scoring bands (monthly):** the score that best separates shortlisted from parked or declined rounds, against
  `shortlist_threshold` in `rules/routing.md` (5 points or more apart, at least 30 rounds); and each evidence type's
  median 90-day result against target, against its confidence multiplier in `rules/scorecard.md` (0.1 or more
  apart, at least 5 closed deliveries). Each becomes a proposal for the core committee (§5.4 step 4, §3.4).

Coming soon: precedents fed to the pre-score and briefs (plan P8), the `guidance-distiller` notes, simulating a
proposal's effect on the fairness gaps, financial band edges (they need finance-confirmed annual benefit), and
writing an approved rule version into the company repo.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import numpy as np
from psycopg.types.json import Jsonb

from core.config import get_settings
from core.db import Conn
from core.logging import get_logger
from rules import load_rule

log = get_logger("learning.decisions")
MIN_DECISIONS = 30
WEIGHT_GAP = 10  # points on a 100 scale
LINE_GAP = 5  # score points
SMALL = 5
FAIRNESS_GAP = 0.25  # a 25-point difference in shortlist or pick rate between groups holds a proposal
MIN_OUTCOMES = 5  # closed deliveries of one evidence type before its multiplier is questioned
MULTIPLIER_GAP = 0.1
POSITIVE_ROUNDS = ("shortlisted", "nominated")
NEGATIVE_ROUNDS = ("parked", "declined")
COMING_SOON = [
    "precedents_in_prescore",
    "guidance_notes",
    "fairness_simulation",
    "band_edges",
    "apply_rule_version",
]
COMMITTEE = {"core_committee", "core_chair"}


# ---- pure functions (tests) --------------------------------------------------------------------------------------


def fit_logistic(
    x: np.ndarray, y: np.ndarray, l2: float = 1.0, iters: int = 3000, lr: float = 0.1
) -> np.ndarray:
    """Coefficients of an L2-regularised logistic regression on standardised features (intercept dropped)."""
    if x.size == 0:
        return np.zeros(0)
    mean = x.mean(axis=0)
    std = x.std(axis=0)
    std[std == 0] = 1.0
    z = (x - mean) / std
    n, k = z.shape
    w = np.zeros(k)
    b = 0.0
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-(z @ w + b)))
        grad_w = z.T @ (p - y) / n + l2 * w / n
        grad_b = float(np.mean(p - y))
        w -= lr * grad_w
        b -= lr * grad_b
    return w


def implied_weights(coefs: np.ndarray, dims: list[str]) -> dict[str, int]:
    """The positive part of each coefficient, scaled so the weights add up to 100 (readable, like the scorecard)."""
    pos = np.clip(coefs, 0, None)
    total = float(pos.sum())
    if total <= 0:
        return {d: 0 for d in dims}
    raw = [float(v) * 100 / total for v in pos]
    out = {d: round(v) for d, v in zip(dims, raw, strict=True)}
    drift = 100 - sum(out.values())  # rounding: give the remainder to the largest weight
    if drift and dims:
        top = max(dims, key=lambda d: out[d])
        out[top] += drift
    return out


def material_weights(current: dict[str, int], implied: dict[str, int], gap: int = WEIGHT_GAP) -> list[str]:
    """Dimensions whose implied weight differs from the scorecard's by `gap` points or more."""
    return sorted(d for d in current if abs(int(implied.get(d, 0)) - int(current[d])) >= gap)


def best_line(scores: list[float], above: list[bool], current: float) -> tuple[float, float, float]:
    """The whole-number score that best separates `above` from the rest (score >= line), the agreement at that line
    and at the current one. Ties go to the line nearest the current one."""
    if not scores:
        return current, 0.0, 0.0

    def agree(line: float) -> float:
        return sum((s >= line) == a for s, a in zip(scores, above, strict=True)) / len(scores)

    best = current
    best_rate = agree(current)
    for line in range(0, 101):
        rate = agree(float(line))
        if rate > best_rate + 1e-9 or (
            abs(rate - best_rate) <= 1e-9 and abs(line - current) < abs(best - current)
        ):
            best, best_rate = float(line), rate
    return best, best_rate, agree(current)


def ai_score(ratings: dict[str, float], weights: dict[str, int]) -> float:
    """The AI pre-score on the 0–100 scale, the way the scorecard adds up the committee's medians (no multiplier)."""
    total = sum(weights.values()) or 1
    return sum((ratings.get(d, 1.0) - 1) / 4 * 100 * w for d, w in weights.items()) / total


def observed_multiplier(ratios: list[float]) -> float:
    """What one kind of evidence actually delivered against its target: the median 90-day ratio, capped at 1.0 and
    rounded to 0.05 (a multiplier never rewards evidence above face value)."""
    if not ratios:
        return 0.0
    ordered = sorted(ratios)
    mid = len(ordered) // 2
    median = ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2
    return round(round(min(1.0, max(0.0, median)) * 20) / 20, 2)


def fairness_reasons(report: dict[str, Any], gap: float = FAIRNESS_GAP) -> list[str]:
    """Plain reasons a proposal is held: groups whose shortlist or pick rates differ sharply (lane B's report;
    suppressed groups, written as words, are left out)."""
    out = []
    for attr, label in (("by_lob", "lines of business"), ("by_location", "locations")):
        for field, what in (("shortlist_rate", "shortlist rate"), ("pick_rate", "pick rate")):
            rates = [float(g[field]) for g in report.get(attr, []) if isinstance(g.get(field), (int, float))]
            if len(rates) >= 2 and max(rates) - min(rates) >= gap:
                points = round((max(rates) - min(rates)) * 100)
                out.append(f"The {what} differs by {points} points across {label}")
    return out


# ---- reading the committee's records -----------------------------------------------------------------------------


def _scorecard_data() -> dict[str, Any]:
    return dict(load_rule(get_settings().company_repo_path, "scorecard").data)


def _scorecard() -> dict[str, int]:
    data = _scorecard_data()
    return {str(k): int(v.get("weight", 0)) for k, v in (data.get("dimensions") or {}).items()}


def _routing() -> dict[str, Any]:
    return dict(load_rule(get_settings().company_repo_path, "routing").data)


def _n(value: int) -> int | str:
    return value if value >= SMALL or value == 0 else "fewer than 5"


def _rate(values: list[bool]) -> float | str:
    return round(sum(values) / len(values), 3) if len(values) >= SMALL else "too few to show"


def _save(conn: Conn, kind: str, period: str, data: dict[str, Any], now: dt.datetime) -> None:
    conn.execute(
        "INSERT INTO learning_reports (kind, period, data, built_at) VALUES (%s, %s, %s, %s) "
        "ON CONFLICT (kind, period) DO UPDATE SET data = EXCLUDED.data, built_at = EXCLUDED.built_at",
        (kind, period, Jsonb(data), now),
    )


def _propose(conn: Conn, kind: str, period: str, payload: dict[str, Any]) -> bool:
    row = conn.execute(
        "INSERT INTO learning_proposals (kind, period, payload) VALUES (%s, %s, %s) "
        "ON CONFLICT DO NOTHING RETURNING id",
        (kind, period, Jsonb(payload)),
    ).fetchone()
    return row is not None


def hold_reasons(conn: Conn, now: dt.datetime) -> list[str]:
    from committee.reports import fairness

    return fairness_reasons(fairness(conn, now - dt.timedelta(days=365), now))


def agreement(conn: Conn, now: dt.datetime, period: str) -> dict[str, Any]:
    """Weekly: the AI pre-score against the committee's shortlist decision, and the average gap between the AI's
    rating and the committee median on each dimension (trailing 90 days; §5.9 step 4, §5.4 step 3)."""
    weights = _scorecard()
    line = float(_routing().get("shortlist_threshold", 65))
    rows = conn.execute(
        "SELECT r.id, coalesce(r.lob_id, 'core') AS grp, r.outcome, r.medians, a.dimension, a.value "
        "FROM scoring_rounds r JOIN ai_prescores a ON a.round_id = r.id "
        "WHERE r.outcome = ANY(%s) AND r.decided_at BETWEEN %s AND %s",
        (list(POSITIVE_ROUNDS + NEGATIVE_ROUNDS), now - dt.timedelta(days=90), now),
    ).fetchall()
    rounds: dict[str, dict[str, Any]] = {}
    for r in rows:
        x = rounds.setdefault(
            str(r["id"]),
            {"grp": str(r["grp"]), "outcome": str(r["outcome"]), "medians": r["medians"] or {}, "scores": {}},
        )
        x["scores"][str(r["dimension"])] = float(r["value"])
    by: dict[str, list[bool]] = {}
    gaps: dict[str, list[float]] = {d: [] for d in weights}
    for x in rounds.values():
        by.setdefault(x["grp"], []).append(
            (ai_score(x["scores"], weights) >= line) == (x["outcome"] in POSITIVE_ROUNDS)
        )
        for d in weights:
            if d in x["scores"] and isinstance(x["medians"].get(d), (int, float)):
                gaps[d].append(x["scores"][d] - float(x["medians"][d]))
    every = [v for vals in by.values() for v in vals]
    data = {
        "rounds": _n(len(every)),
        "agreement": _rate(every),
        "by_body": [{"group": g, "rounds": _n(len(v)), "agreement": _rate(v)} for g, v in sorted(by.items())],
        "dimension_gap": {
            d: round(sum(v) / len(v), 2) if len(v) >= SMALL else "too few to show" for d, v in gaps.items()
        },
        "line": line,
    }
    with conn.transaction():
        _save(conn, "agreement", period, data, now)
    return data


def rewards(conn: Conn, now: dt.datetime, period: str) -> dict[str, Any]:
    """Monthly: what the committee's picks and declines imply about the scorecard weights (trailing 12 months)."""
    current = _scorecard()
    dims = sorted(current)
    rows = conn.execute(
        "SELECT DISTINCT ON (d.id) d.outcome, r.medians FROM decisions d "
        "JOIN scoring_rounds r ON r.cluster_id = d.cluster_id AND r.medians IS NOT NULL AND r.body = 'core' "
        "WHERE d.body = 'core' AND d.outcome IN ('picked', 'declined') AND d.decided_at BETWEEN %s AND %s "
        "ORDER BY d.id, r.revealed_at DESC NULLS LAST",
        (now - dt.timedelta(days=365), now),
    ).fetchall()
    usable = [r for r in rows if all(r["medians"] and d in r["medians"] for d in dims)]
    data: dict[str, Any] = {"decisions": _n(len(usable)), "needed": MIN_DECISIONS, "current": current}
    picked = sum(1 for r in usable if r["outcome"] == "picked")
    if len(usable) >= MIN_DECISIONS and 0 < picked < len(usable):
        x = np.array([[float(r["medians"][d]) for d in dims] for r in usable])
        y = np.array([1.0 if r["outcome"] == "picked" else 0.0 for r in usable])
        implied = implied_weights(fit_logistic(x, y), dims)
        differs = material_weights(current, implied)
        data.update({"implied": implied, "differs": differs})
        if differs:
            reasons = hold_reasons(conn, now)
            payload = {"key": f"scorecard_weights:{period}", "current": current, "implied": implied,
                       "differs": differs, "decisions": len(usable), "fairness": reasons}  # fmt: skip
            with conn.transaction():
                _propose(conn, "scorecard_weights", period, payload)
    with conn.transaction():
        _save(conn, "committee_rewards", period, data, now)
    return data


def bands(conn: Conn, now: dt.datetime, period: str) -> dict[str, Any]:
    """Monthly (trailing 12 months): where the committee actually draws the shortlist line, from scoring rounds
    (§5.9), and how far each kind of evidence fell short of its target 90 days after delivery, against the
    scorecard's confidence multipliers, from calibration (§5.4 step 4). A material gap becomes a proposal."""
    since = now - dt.timedelta(days=365)
    fairness: list[str] | None = None

    def held() -> list[str]:
        nonlocal fairness
        if fairness is None:
            fairness = hold_reasons(conn, now)
        return fairness

    # The shortlist line.
    current = float(_routing().get("shortlist_threshold", 65))
    rows = conn.execute(
        "SELECT final_score, outcome FROM scoring_rounds WHERE final_score IS NOT NULL AND outcome = ANY(%s) "
        "AND decided_at BETWEEN %s AND %s",
        (list(POSITIVE_ROUNDS + NEGATIVE_ROUNDS), since, now),
    ).fetchall()
    scores = [float(r["final_score"]) for r in rows]
    above = [str(r["outcome"]) in POSITIVE_ROUNDS for r in rows]
    line_data: dict[str, Any] = {"rounds": _n(len(scores)), "needed": MIN_DECISIONS, "current": current}
    proposals: list[dict[str, Any]] = []
    if len(scores) >= MIN_DECISIONS:
        line, rate, now_rate = best_line(scores, above, current)
        line_data.update({"observed": line, "agreement_at_observed": round(rate, 3),
                          "agreement_at_current": round(now_rate, 3)})  # fmt: skip
        if abs(line - current) >= LINE_GAP:
            proposals.append({"key": f"scoring_band:line:{period}", "rule": "routing", "field": "shortlist_threshold",
                              "current": current, "proposed": line, "rounds": len(scores),
                              "agreement_now": round(now_rate, 3), "agreement_proposed": round(rate, 3)})  # fmt: skip

    # Confidence multipliers: each closed delivery's 90-day result against target, by the evidence type the
    # committee recorded when it scored the group.
    multipliers = {
        str(k): float(v) for k, v in (_scorecard_data().get("confidence_multiplier") or {}).items()
    }
    outcomes = conn.execute(
        "SELECT r.evidence_type, (m.results ->> 'actual_vs_target')::numeric AS ratio FROM deliveries d "
        "JOIN delivery_measurements m ON m.delivery_id = d.id AND m.mark = 'day_90' "
        "LEFT JOIN ideas i ON d.subject_type = 'idea' AND i.idea_id = d.subject_id "
        "JOIN LATERAL (SELECT evidence_type FROM scoring_rounds s "
        "  WHERE s.cluster_id = CASE WHEN d.subject_type = 'cluster' THEN d.subject_id ELSE i.cluster_id END "
        "  AND s.evidence_type IS NOT NULL AND s.decided_at IS NOT NULL ORDER BY s.decided_at DESC LIMIT 1) r ON true "
        "WHERE d.state = 'closed' AND d.closed_at BETWEEN %s AND %s AND m.results ? 'actual_vs_target'",
        (since, now),
    ).fetchall()
    by_type: dict[str, list[float]] = {}
    for o in outcomes:
        by_type.setdefault(str(o["evidence_type"]), []).append(float(o["ratio"]))
    mult_data: dict[str, Any] = {}
    for kind, current_m in sorted(multipliers.items()):
        ratios = by_type.get(kind, [])
        observed = observed_multiplier(ratios)
        mult_data[kind] = {"deliveries": _n(len(ratios)), "current": current_m,
                           "observed": observed if len(ratios) >= MIN_OUTCOMES else None}  # fmt: skip
        if len(ratios) >= MIN_OUTCOMES and abs(observed - current_m) >= MULTIPLIER_GAP - 1e-9:
            proposals.append({"key": f"scoring_band:multiplier:{kind}:{period}", "rule": "scorecard",
                              "field": f"confidence_multiplier.{kind}", "current": current_m, "proposed": observed,
                              "deliveries": len(ratios)})  # fmt: skip
    data = {"line": line_data, "multipliers": mult_data, "needed_outcomes": MIN_OUTCOMES}
    with conn.transaction():
        for payload in proposals:
            _propose(conn, "scoring_band", period, {**payload, "fairness": held()})
        _save(conn, "scoring_band", period, data, now)
    return data


# ---- the committee learning page ---------------------------------------------------------------------------------


def view(conn: Conn, viewer_id: str) -> dict[str, Any]:
    """Core committee only: the latest reports and the proposals that wait for them."""
    from ones.service import roles
    from ones.text import OnesRefused

    if not roles(conn, viewer_id) & COMMITTEE:
        raise OnesRefused(403, "forbidden")
    latest = {
        r["kind"]: {"period": r["period"], "data": r["data"], "built_at": r["built_at"].isoformat()}
        for r in conn.execute(
            "SELECT DISTINCT ON (kind) kind, period, data, built_at FROM learning_reports "
            "WHERE kind IN ('agreement', 'committee_rewards', 'scoring_band') ORDER BY kind, built_at DESC"
        ).fetchall()
    }
    proposals = [
        {"id": r["id"], "kind": r["kind"], "period": r["period"], "state": r["state"], "payload": r["payload"],
         "decided_at": r["decided_at"].isoformat() if r["decided_at"] else None}
        for r in conn.execute(
            "SELECT id, kind, period, state, payload, decided_at FROM learning_proposals "
            "WHERE kind IN ('scorecard_weights', 'scoring_band') ORDER BY created_at DESC LIMIT 20"
        ).fetchall()
    ]  # fmt: skip
    return {"reports": latest, "proposals": proposals, "coming_soon": COMING_SOON}
