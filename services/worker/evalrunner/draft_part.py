"""draft-part golden set (L-DRAFT.parts, BLD-C072): each answer, after the gateway, quotes only the person's own
words (never the English copy of a voice note, DEC-108), holds only their numbers, chooses only from the lists and
carries no tags in what the person reads. The expectations per case measure whether the part found what the words
say; `dropped` and `first_attempt_problems` measure the model before the gateway mends it (BLD-C035). Synthetic
cases only."""

from __future__ import annotations

import json
from typing import Any

from evalrunner.common import ROOT, Context, read_jsonl
from gateway import AgentFailed, grounding, run_agent
from gateway.checks import draft_part as check
from gateway.spec import load
from pii.tagger import TAG_RE

AGENT = ROOT / "agents" / "draft-part"
TEXT = ("title", "summary", "often", "reason")


def _inputs(case_input: Any) -> dict[str, Any]:
    if isinstance(case_input, str):  # "examples/01-title.json input (agents/draft-part)"
        name = case_input.split()[0].removeprefix("examples/")
        data: dict[str, Any] = json.loads((AGENT / "examples" / name).read_text(encoding="utf-8"))["input"]
        return data
    return dict(case_input)


def _met(expected: dict[str, Any], out: dict[str, Any], sent: dict[str, Any]) -> tuple[int, int]:
    met = total = 0
    for key, want in expected.items():
        total += 1
        if key == "title_filled":
            ok = bool(out.get("title")) == want
        elif key == "summary_max_sentences":
            ok = out.get("summary") is None or len(grounding.split_sentences(out["summary"])) <= want
        elif key == "often_contains":
            ok = isinstance(out.get("often"), str) and want in out["often"]
        elif key == "who_includes":
            ok = all(w in (out.get("who") or []) for w in want)
        elif key == "who_excludes":
            ok = not any(w in (out.get("who") or []) for w in want)
        elif key == "worth_includes":
            ok = all(w in (out.get("worth") or []) for w in want)
        elif key == "quotes_from_text_only":
            texts = " ".join(str(w.get("text")) for w in sent.get("words") or [])
            ok = all(q in texts for q in out.get("evidence") or [])
        elif key == "no_tags_in_text":
            ok = not any(isinstance(out.get(k), str) and TAG_RE.search(out[k]) for k in TEXT)
        else:  # a field equal to the expected value ("often": null, "area": "Investor service")
            ok = out.get(key) == want
        met += int(ok)
    return met, total


def run(ctx: Context) -> dict[str, Any]:
    spec = load("draft-part")
    cases: list[dict[str, Any]] = []
    ungrounded = out_of_list = tags = met = total = dropped = first_attempt = 0
    for case in read_jsonl("draft_part.jsonl"):
        sent = ctx.fill(_inputs(case["input"]))
        row: dict[str, Any] = {"id": case["id"]}
        try:
            result = run_agent("draft-part", sent, ctx.scope(), conn=ctx.conn, use_cache=False)
        except AgentFailed as exc:
            row["error"] = exc.code
            cases.append(row)
            continue
        out = result.data
        problems = check(result.sent, out, None)
        ungrounded += int(any("evidence" in p or "number" in p for p in problems))
        out_of_list += int(any("options.choices" in p for p in problems))
        tags += int(any(isinstance(out.get(k), str) and TAG_RE.search(out[k]) for k in TEXT))
        # The model before the gateway's repair: an answer the checks refused on the first ask (re-asked), and one
        # still unbacked after the re-ask (dropped). The checks after the gateway always hold; these do not.
        first_attempt += int(result.outcome == "ok_after_retry")
        dropped += int(bool(result.dropped))
        m, t = _met(case.get("expected") or {}, out, result.sent)
        met, total = met + m, total + t
        row.update({"met": m, "of": t, "dropped": result.dropped, "problems": len(problems),
                    "first_attempt_refused": result.outcome == "ok_after_retry"})  # fmt: skip
        cases.append(row)
    errors = sum(1 for c in cases if "error" in c)
    metrics = {
        "cases": len(cases),
        "errors": errors,
        "ungrounded_after_gateway": ungrounded,
        "out_of_list": out_of_list,
        "tags_in_text": tags,
        "dropped": dropped,
        "first_attempt_problems": first_attempt,
        "expectations": round(met / total, 4) if total else 1.0,
    }
    gates = spec.raw.get("pass_gates") or {}
    model_gates = {
        "ungrounded_after_gateway": ungrounded <= gates.get("ungrounded_after_gateway", 0),
        "out_of_list": out_of_list <= gates.get("out_of_list", 0),
        "tags_in_text": tags <= gates.get("tags_in_text", 0),
        "expectations": metrics["expectations"] >= gates.get("expectations_min", 0.8),
        "dropped": dropped <= gates.get("dropped_max", 1),
        "first_attempt_problems": first_attempt <= gates.get("first_attempt_problems_max", 3),
    }
    # The harness: no case may fail outright, and nothing the gateway lets through may break the rules, whatever
    # the route (the checks run on every answer, so this holds in fake mode too).
    harness_gates = {
        "no_errors": errors == 0,
        "checks_hold": ungrounded == 0 and out_of_list == 0 and tags == 0,
    }
    return {"agent": spec.name, "version": spec.version, "metrics": metrics, "model_gates": model_gates,
            "harness_gates": harness_gates, "cases": cases}  # fmt: skip
