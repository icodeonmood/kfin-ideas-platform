"""handover-draft golden set (BLD-138): the unit fits the members' own measure, numbers are never invented (the
gateway's checks refuse them, so an invented number shows up as an error), and only the fix track gets an
objective. Synthetic cases only."""

from __future__ import annotations

from typing import Any

from evalrunner.common import Context, read_jsonl
from gateway import AgentFailed, run_agent
from gateway.checks import _numbers
from gateway.spec import load


def run(ctx: Context) -> dict[str, Any]:
    spec = load("handover-draft")
    cases: list[dict[str, Any]] = []
    unit_ok = unit_checks = grounded = objective_ok = 0
    for case in read_jsonl("handover_draft.jsonl"):
        sent = ctx.fill(case["input"])
        expected = case["expected"]
        row: dict[str, Any] = {"id": case["id"]}
        try:
            out = run_agent("handover-draft", sent, ctx.scope(), conn=ctx.conn, use_cache=False)
        except AgentFailed as exc:
            row["error"] = exc.code
            cases.append(row)
            continue
        data = out.data
        if expected.get("unit"):
            unit_checks += 1
            unit_ok += int(data["unit"] == expected["unit"])
        source = " ".join(str(m.get("summary") or "") for m in sent["members"])
        given = _numbers(source)
        grounded += int(all(v is None or float(v) in given for v in (data["baseline"], data["target"])))
        objective_ok += int((sent["track"] == "fix") == (data["objective"] is not None))
        row.update({"unit": data["unit"], "baseline": data["baseline"], "target": data["target"]})
        cases.append(row)
    done = sum(1 for c in cases if "error" not in c)
    errors = len(cases) - done
    metrics = {
        "cases": len(cases),
        "errors": errors,
        "unit_accuracy": round(unit_ok / unit_checks, 4) if unit_checks else 1.0,
        "numbers_grounded": round(grounded / done, 4) if done else 1.0,
        "objective_rule": round(objective_ok / done, 4) if done else 1.0,
    }
    gates = spec.raw.get("pass_gates") or {}
    model_gates = {
        "unit_accuracy": metrics["unit_accuracy"] >= gates.get("unit_accuracy_min", 0.8),
        "numbers_grounded": metrics["numbers_grounded"] >= gates.get("numbers_grounded_min", 1.0),
        "objective_rule": metrics["objective_rule"] >= gates.get("objective_rule_min", 1.0),
    }
    harness_gates = {"no_errors": errors == 0}
    return {"agent": spec.name, "version": spec.version, "metrics": metrics, "model_gates": model_gates,
            "harness_gates": harness_gates, "cases": cases}  # fmt: skip
