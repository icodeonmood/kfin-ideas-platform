"""cluster-summary golden set (§4.4 B step 7): credits go to the members who proposed a fix, and every member
with a fix is credited; names, descriptions, refs, LOBs and roles are also enforced by the gateway's checks, so
a case that fails them shows up as an error here."""

from __future__ import annotations

from typing import Any

from evalrunner.common import Context, read_jsonl
from gateway import AgentFailed, run_agent
from gateway.spec import load


def run(ctx: Context) -> dict[str, Any]:
    spec = load("cluster-summary")
    cases: list[dict[str, Any]] = []
    credited_ok = credited_all = covered = with_fix = name_ok = name_checks = 0
    for case in read_jsonl("cluster_summary.jsonl"):
        sent = ctx.fill(case["input"])
        expected = case["expected"]
        row: dict[str, Any] = {"id": case["id"]}
        try:
            out = run_agent("cluster-summary", sent, ctx.scope(), conn=ctx.conn, use_cache=False)
        except AgentFailed as exc:
            row["error"] = exc.code
            cases.append(row)
            continue
        fixers = set(expected["fix_refs"])
        credits = {r for part in out.data["solution"] for r in part["credit"]}
        credited_all += len(credits)
        credited_ok += len(credits & fixers)
        with_fix += len(fixers)
        covered += len(fixers & credits)
        if "name_must_not_contain" in expected or "keep_name" in expected:
            name_checks += 1
            bad = expected.get("name_must_not_contain")
            keep = expected.get("keep_name")
            name_ok += int(
                (not bad or bad not in out.data["name"]) and (not keep or out.data["name"] == keep)
            )
        row.update({"credits": sorted(credits), "lobs": out.data["lobs"]})
        cases.append(row)
    errors = sum(1 for c in cases if "error" in c)
    metrics = {
        "cases": len(cases),
        "errors": errors,
        "credit_accuracy": round(credited_ok / credited_all, 4) if credited_all else 1.0,
        "member_coverage": round(covered / with_fix, 4) if with_fix else 1.0,
        "name_rules": round(name_ok / name_checks, 4) if name_checks else 1.0,
    }
    gates = spec.raw.get("pass_gates") or {}
    model_gates = {
        "credit_accuracy": metrics["credit_accuracy"] >= gates.get("credit_accuracy_min", 0.9),
        "member_coverage": metrics["member_coverage"] >= gates.get("member_coverage_min", 0.8),
        "name_rules": metrics["name_rules"] == 1.0,
    }
    harness_gates = {"no_errors": errors == 0}
    return {"agent": spec.name, "version": spec.version, "metrics": metrics, "model_gates": model_gates,
            "harness_gates": harness_gates, "cases": cases}  # fmt: skip
