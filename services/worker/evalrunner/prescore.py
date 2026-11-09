"""prescore golden set (§4.6 step 2): one score per dimension in order and financial value within a level of the
band (both also enforced by the gateway, so a breach shows as an error), and each case's expected ranges hit."""

from __future__ import annotations

from typing import Any

from evalrunner.common import Context, read_jsonl
from gateway import AgentFailed, run_agent
from gateway.spec import load


def run(ctx: Context) -> dict[str, Any]:
    spec = load("prescore")
    cases: list[dict[str, Any]] = []
    within = checked = hits = expected = 0
    for case in read_jsonl("prescore.jsonl"):
        sent = ctx.fill(case["input"])
        row: dict[str, Any] = {"id": case["id"]}
        try:
            out = run_agent("prescore", sent, ctx.scope(), conn=ctx.conn, use_cache=False)
        except AgentFailed as exc:
            row["error"] = exc.code
            cases.append(row)
            continue
        got = {s["dimension"]: s["value"] for s in out.data["scores"]}
        band = sent["impact"].get("suggested_financial_band")
        if isinstance(band, int):
            checked += 1
            within += abs(got.get("financial_value", 0) - band) <= 1
        for dim, (lo, hi) in case["expected"].items():
            expected += 1
            hits += lo <= got.get(dim, 0) <= hi
        row["scores"] = got
        cases.append(row)
    errors = sum(1 for c in cases if "error" in c)
    metrics = {
        "cases": len(cases),
        "errors": errors,
        "financial_within_band": round(within / checked, 4) if checked else 1.0,
        "expected_range_hit": round(hits / expected, 4) if expected else 1.0,
    }
    gates = spec.raw.get("pass_gates") or {}
    model_gates = {
        "financial_within_band": metrics["financial_within_band"]
        >= gates.get("financial_within_band_min", 1.0),
        "expected_range_hit": metrics["expected_range_hit"] >= gates.get("expected_range_hit_min", 0.8),
    }
    harness_gates = {"no_errors": errors == 0}
    return {"agent": spec.name, "version": spec.version, "metrics": metrics, "model_gates": model_gates,
            "harness_gates": harness_gates, "cases": cases}  # fmt: skip
