"""Golden sets for the committee agents (§4.7): pitch-prep, collation and reason-writer. The gateway enforces each
agent's checks (eight slides, members that exist, no banned words), so a breach shows as an error here; the
model gates measure coverage and grounding on the real route."""

from __future__ import annotations

from typing import Any

from evalrunner.common import Context, read_jsonl
from gateway import AgentFailed, run_agent
from gateway.spec import load


def _run(ctx: Context, agent: str, golden: str, measure: Any) -> dict[str, Any]:
    spec = load(agent)
    cases: list[dict[str, Any]] = []
    scores: list[float] = []
    for case in read_jsonl(golden):
        sent = ctx.fill(case["input"])
        row: dict[str, Any] = {"id": case["id"]}
        try:
            out = run_agent(agent, sent, ctx.scope(), conn=ctx.conn, use_cache=False)
        except AgentFailed as exc:
            row["error"] = exc.code
            cases.append(row)
            continue
        scores.append(measure(sent, out.data))
        cases.append(row)
    errors = sum(1 for c in cases if "error" in c)
    quality = round(sum(scores) / len(scores), 4) if scores else 1.0
    gate_min = float(next(iter((spec.raw.get("pass_gates") or {"q": 1.0}).values())))
    return {"agent": spec.name, "version": spec.version,
            "metrics": {"cases": len(cases), "errors": errors, "quality": quality},
            "model_gates": {"quality": quality >= gate_min}, "harness_gates": {"no_errors": errors == 0},
            "cases": cases}  # fmt: skip


def _slides_in_order(sent: dict[str, Any], out: dict[str, Any]) -> float:
    return 1.0 if len(out["slides"]) == 8 else 0.0


def _coverage(sent: dict[str, Any], out: dict[str, Any]) -> float:
    wrote = {(a["member"], k) for a in sent["assessments"] for k in ("strengths", "concerns") if a.get(k)}
    got = {(m, k) for k in ("strengths", "concerns") for t in out[k] for m in t["members"]}
    return len(wrote & got) / len(wrote) if wrote else 1.0


def _grounded(sent: dict[str, Any], out: dict[str, Any]) -> float:
    return 1.0 if out["reason"] and out["what_would_change"] else 0.0


def run_pitch_prep(ctx: Context) -> dict[str, Any]:
    return _run(ctx, "pitch-prep", "pitch_prep.jsonl", _slides_in_order)


def run_collation(ctx: Context) -> dict[str, Any]:
    return _run(ctx, "collation", "collation.jsonl", _coverage)


def run_reason_writer(ctx: Context) -> dict[str, Any]:
    return _run(ctx, "reason-writer", "reason_writer.jsonl", _grounded)
