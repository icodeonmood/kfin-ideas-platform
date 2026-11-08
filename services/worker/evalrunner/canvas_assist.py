"""Canvas-assist golden set (AT-B4-08): properties checked by code, because suggestions vary in wording."""

from __future__ import annotations

import copy
from typing import Any

from evalrunner.common import Context, read_jsonl
from gateway import AgentFailed, run_agent
from gateway.checks import SUBMITTER_SECTIONS, _diff
from gateway.spec import load
from pii.detect import detect, directory
from pii.tagger import TAG_RE
from scan.inputs import taxonomy_slice

SKELETON: dict[str, Any] = {
    "kind": None,
    "one_line": None,
    "details": "",
    "who": {"segments": [], "frequency_or_reach": None, "today_alternative": None},
    "value": {
        "category": "not_sure",
        "play": None,
        "estimate": {
            "hours_saved_per_month": None, "inr_saved_per_year": None, "inr_revenue_one_time": None,
            "inr_revenue_per_year": None, "clients_who_would_pay": None, "note": None,
        },
        "basis": None,
    },
    "ecosystem": {"solved_elsewhere": None, "references": [], "our_advantage": None},
    "solution": {"approach": None, "needs": None, "risks": None},
    "attachments": [],
}  # fmt: skip
KIND_TO_GK = {
    "problem": "idea_problem",
    "problem_with_solution": "idea_solution",
    "business_idea": "business_idea",
}


def _merge(base: Any, extra: Any) -> Any:
    if isinstance(base, dict) and isinstance(extra, dict):
        return {k: _merge(base.get(k), extra.get(k)) if k in extra else base[k] for k in base} | {
            k: v for k, v in extra.items() if k not in base
        }
    return copy.deepcopy(extra)


def _inputs(case_input: Any) -> dict[str, Any]:
    spec = load("canvas-assist")
    if isinstance(case_input, str):  # "examples/01-quick-capture input (agents/canvas-assist)"
        name = case_input.split()[0].removeprefix("examples/") + ".json"
        return copy.deepcopy(spec.example(name).input)
    answers = _merge(SKELETON, case_input.get("canvas_answers") or {})
    text = " ".join(str(v) for v in (answers.get("one_line"), answers.get("details")) if v)
    return {
        "canvas_answers": answers,
        "taxonomy_slice": case_input.get("taxonomy_slice") or taxonomy_slice(text),
        "gatekeeper": case_input.get("gatekeeper")
        or {
            "kind": {"value": KIND_TO_GK.get(str(answers.get("kind")), "idea_problem"), "confidence": 0.8},
            "language": {"primary": "en", "mixed": False},
        },
        "past_corrections": case_input.get("past_corrections") or [],
    }


def _get(node: Any, path: str) -> Any:
    for key in path.split("."):
        node = node.get(key) if isinstance(node, dict) else None
    return node


def _properties(exp: dict[str, Any], sent: dict[str, Any], out: dict[str, Any], d: Any) -> dict[str, bool]:
    res: dict[str, bool] = {}
    answers = sent["canvas_answers"]
    for key, want in exp.items():
        if key == "submitter_fields_unchanged":
            problems: list[str] = []
            for section in SUBMITTER_SECTIONS:
                _diff(section, answers.get(section), out.get(section), problems)
            res[key] = not problems
        elif key == "one_line_max_words":
            res[key] = len(str(out.get("one_line") or "").split()) <= int(want)
        elif key.endswith("_include"):
            res[key] = set(want) <= set(_get(out, key.removesuffix("_include")) or [])
        elif key == "no_invented_inr":
            est_in = answers["value"]["estimate"]
            est_out = out["value"]["estimate"]
            res[key] = all(
                est_out[k] is None or est_in.get(k) is not None for k in est_out if k.startswith("inr_")
            )
        elif key == "flag_mentions":
            flags = " ".join(out.get("flags_for_reviewer") or []).lower()
            res[key] = all(w.lower() in flags for w in want)
        elif key.endswith("_max"):
            res[key] = float(
                (out.get("confidence") or {}).get(key.removeprefix("confidence.").removesuffix("_max"), 1)
            ) <= float(want)
        elif key == "neutral_summary_no_tags":
            res[key] = not TAG_RE.search(out["neutral_summary"])
        elif key == "neutral_summary_no_names":
            res[key] = not detect(out["neutral_summary"], d)
        elif key == "references_count":
            res[key] = len(out["ecosystem"]["references"]) == int(want)
        elif key.endswith("_suggested_in"):
            res[key] = _get(out, key.removesuffix("_suggested_in")) in want
        elif key.endswith("_may_suggest"):
            continue  # informational
        else:
            res[key] = _get(out, key) == want
    return res


def run(ctx: Context) -> dict[str, Any]:
    spec = load("canvas-assist")
    d = directory(ctx.conn)
    cases = []
    for case in read_jsonl("canvas_assist.jsonl"):
        sent = ctx.fill(_inputs(case["input"]))
        row: dict[str, Any] = {"id": case["id"]}
        try:
            out = run_agent("canvas-assist", sent, ctx.scope(), conn=ctx.conn, use_cache=False)
        except AgentFailed as exc:
            row["error"] = exc.code
            cases.append(row)
            continue
        data = out.data
        sent = out.sent  # compare with what the model saw (tagged), as the gateway does
        problems: list[str] = []
        for section in SUBMITTER_SECTIONS:
            _diff(section, sent["canvas_answers"].get(section), data.get(section), problems)
        allowed = {x["id"] for g in sent["taxonomy_slice"].values() if isinstance(g, list) for x in g}
        system_ids = [v for k in ("lobs", "areas", "systems", "roles_affected") for v in data["system"][k]]
        row["submitter_changes"] = len(problems)
        row["out_of_slice"] = sum(v not in allowed for v in system_ids)
        row["summary_leak"] = bool(TAG_RE.search(data["neutral_summary"])) or bool(
            detect(data["neutral_summary"], d)
        )
        row["properties"] = _properties(case.get("expected_properties") or {}, sent, data, d)
        row["outcome"] = out.outcome
        cases.append(row)

    ran = [c for c in cases if "error" not in c]
    area_cases = [c for c in ran if "system.areas_include" in c["properties"]]
    props = [v for c in ran for v in c["properties"].values()]
    metrics = {
        "cases": len(cases),
        "errors": len(cases) - len(ran),
        "submitter_field_changes": sum(c["submitter_changes"] for c in ran),
        "out_of_slice_ids": sum(c["out_of_slice"] for c in ran),
        "neutral_summary_leaks": sum(c["summary_leak"] for c in ran),
        "area_tag_accuracy": round(
            sum(c["properties"]["system.areas_include"] for c in area_cases) / len(area_cases), 4
        )
        if area_cases
        else None,
        "property_pass_rate": round(sum(props) / len(props), 4) if props else None,
    }
    gates = spec.raw.get("pass_gates") or {}
    model_gates = {
        "area_tag_accuracy": (metrics["area_tag_accuracy"] or 0) >= gates.get("area_tag_accuracy_min", 0.8),
    }
    harness_gates = {
        "no_errors": metrics["errors"] == 0,
        "submitter_field_changes": metrics["submitter_field_changes"]
        == gates.get("submitter_field_changes", 0),
        "out_of_slice_ids": metrics["out_of_slice_ids"] == gates.get("out_of_slice_ids", 0),
        "neutral_summary_leaks": metrics["neutral_summary_leaks"] == gates.get("neutral_summary_leaks", 0),
    }
    return {"agent": spec.name, "version": spec.version, "metrics": metrics, "model_gates": model_gates,
            "harness_gates": harness_gates, "cases": cases}  # fmt: skip
