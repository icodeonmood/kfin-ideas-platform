"""Judge golden set (AT-B5-04): precision and recall of "same", and every candidate labelled with a short reason
in input order (the order, cids and reason length are also enforced by the gateway's checks)."""

from __future__ import annotations

from typing import Any

from evalrunner.common import Context, read_jsonl
from gateway import AgentFailed, run_agent
from gateway.spec import load


def run(ctx: Context) -> dict[str, Any]:
    spec = load("judge")
    cases = []
    tp = fp = fn = labelled = total = 0
    for case in read_jsonl("judge.jsonl"):
        sent = ctx.fill(case["input"])
        sent.setdefault("past_corrections", [])
        expected: dict[str, str] = case["expected"]
        row: dict[str, Any] = {"id": case["id"]}
        try:
            out = run_agent("judge", sent, ctx.scope(), conn=ctx.conn, use_cache=False)
        except AgentFailed as exc:
            row["error"] = exc.code
            cases.append(row)
            continue
        got = {r["cid"]: r["label"] for r in out.data["results"]}
        for cid, want in expected.items():
            total += 1
            labelled += cid in got
            if got.get(cid) == "same" and want == "same":
                tp += 1
            elif got.get(cid) == "same":
                fp += 1
            elif want == "same":
                fn += 1
        row["labels"] = got
        cases.append(row)
    metrics = {
        "cases": len(cases),
        "errors": sum(1 for c in cases if "error" in c),
        "labels": total,
        "labelled_share": round(labelled / total, 4) if total else None,
        "same_precision": round(tp / (tp + fp), 4) if tp + fp else None,
        "same_recall": round(tp / (tp + fn), 4) if tp + fn else None,
    }
    gates = spec.raw.get("pass_gates") or {}
    model_gates = {
        "same_precision": (metrics["same_precision"] or 0) >= gates.get("same_precision_min", 0.85),
        "same_recall": (metrics["same_recall"] or 0) >= gates.get("same_recall_min", 0.75),
    }
    harness_gates = {
        "no_errors": metrics["errors"] == 0,
        "every_candidate_labelled": metrics["labelled_share"] == 1.0,
    }
    return {"agent": spec.name, "version": spec.version, "metrics": metrics, "model_gates": model_gates,
            "harness_gates": harness_gates, "cases": cases}  # fmt: skip
