"""attachment-digest golden set (§4.2 attachments step 6): figures copied exactly from the file, locations copied
from the pieces (both also enforced by the gateway's checks, so a breach shows up as an error), and the figures
a reader would expect actually found."""

from __future__ import annotations

from typing import Any

from evalrunner.common import Context, read_jsonl
from gateway import AgentFailed, run_agent
from gateway.spec import load


def run(ctx: Context) -> dict[str, Any]:
    spec = load("attachment-digest")
    cases: list[dict[str, Any]] = []
    figures = faithful = located = claims = expected = found = 0
    for case in read_jsonl("attachment_digest.jsonl"):
        sent = ctx.fill(case["input"])
        row: dict[str, Any] = {"id": case["id"]}
        try:
            out = run_agent("attachment-digest", sent, ctx.scope(), conn=ctx.conn, use_cache=False)
        except AgentFailed as exc:
            row["error"] = exc.code
            cases.append(row)
            continue
        source = "\n".join(p["text"] for p in sent["text"])
        locations = {p["location"] for p in sent["text"]}
        got = [c["figure"] for c in out.data["claims"] if c["figure"]]
        figures += len(got)
        faithful += sum(1 for f in got if f in source)
        claims += len(out.data["claims"])
        located += sum(1 for c in out.data["claims"] if c["location"] in locations)
        want = case["expected"]["figures"]
        expected += len(want)
        found += sum(1 for f in want if any(f in g for g in got))
        row["figures"] = got
        cases.append(row)
    errors = sum(1 for c in cases if "error" in c)
    metrics = {
        "cases": len(cases),
        "errors": errors,
        "figure_fidelity": round(faithful / figures, 4) if figures else 1.0,
        "location_accuracy": round(located / claims, 4) if claims else 1.0,
        "expected_figure_recall": round(found / expected, 4) if expected else 1.0,
    }
    gates = spec.raw.get("pass_gates") or {}
    model_gates = {
        "figure_fidelity": metrics["figure_fidelity"] >= gates.get("figure_fidelity_min", 1.0),
        "location_accuracy": metrics["location_accuracy"] >= gates.get("location_accuracy_min", 1.0),
        "expected_figure_recall": metrics["expected_figure_recall"]
        >= gates.get("expected_figure_recall_min", 0.6),
    }
    harness_gates = {"no_errors": errors == 0}
    return {"agent": spec.name, "version": spec.version, "metrics": metrics, "model_gates": model_gates,
            "harness_gates": harness_gates, "cases": cases}  # fmt: skip
