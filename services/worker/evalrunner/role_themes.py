"""role-themes golden set (BLD-139): ideas put in the same theme belong together (pair precision), ideas in an
expected theme land in some theme (coverage), and a role where nothing recurs gets no theme. Card safety, refs and
"one theme per idea" are enforced by the gateway's checks, so a case that fails them shows up as an error here."""

from __future__ import annotations

from itertools import combinations
from typing import Any

from evalrunner.common import Context, read_jsonl
from gateway import AgentFailed, run_agent
from gateway.spec import load


def _pairs(groups: list[list[str]]) -> set[frozenset[str]]:
    return {frozenset(p) for g in groups for p in combinations(sorted(set(g)), 2)}


def run(ctx: Context) -> dict[str, Any]:
    spec = load("role-themes")
    cases: list[dict[str, Any]] = []
    pairs_ok = pairs_all = covered = expected_all = empty_ok = empty_cases = 0
    for case in read_jsonl("role_themes.jsonl"):
        sent = ctx.fill(case["input"])
        want = [list(g) for g in case["expected"]["groups"]]
        row: dict[str, Any] = {"id": case["id"]}
        try:
            out = run_agent("role-themes", sent, ctx.scope(), conn=ctx.conn, use_cache=False)
        except AgentFailed as exc:
            row["error"] = exc.code
            cases.append(row)
            continue
        got = [t["refs"] for t in out.data["themes"]]
        mine, theirs = _pairs(got), _pairs(want)
        pairs_all += len(mine)
        pairs_ok += len(mine & theirs)
        placed = {r for g in got for r in g}
        expected_refs = {r for g in want for r in g}
        expected_all += len(expected_refs)
        covered += len(expected_refs & placed)
        if not want:
            empty_cases += 1
            empty_ok += int(not got)
        row.update({"themes": len(got)})
        cases.append(row)
    errors = sum(1 for c in cases if "error" in c)
    metrics = {
        "cases": len(cases),
        "errors": errors,
        "pair_precision": round(pairs_ok / pairs_all, 4) if pairs_all else 1.0,
        "coverage": round(covered / expected_all, 4) if expected_all else 1.0,
        "no_forced_themes": round(empty_ok / empty_cases, 4) if empty_cases else 1.0,
    }
    gates = spec.raw.get("pass_gates") or {}
    model_gates = {
        "pair_precision": metrics["pair_precision"] >= gates.get("pair_precision_min", 0.8),
        "coverage": metrics["coverage"] >= gates.get("coverage_min", 0.6),
        "no_forced_themes": metrics["no_forced_themes"] == 1.0,
    }
    harness_gates = {"no_errors": errors == 0}
    return {"agent": spec.name, "version": spec.version, "metrics": metrics, "model_gates": model_gates,
            "harness_gates": harness_gates, "cases": cases}  # fmt: skip
