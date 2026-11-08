"""Agent-specific checks on validated output (config `post_checks`). Each returns plain problems that are sent
back to the model on the one retry, so they quote tagged text at most and never a real value."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pii.detect import Directory, detect
from pii.tagger import TAG_RE

Check = Callable[[dict[str, Any], dict[str, Any], Directory | None], list[str]]
SUBMITTER_SECTIONS = ("kind", "one_line", "details", "who", "value", "ecosystem", "solution")


def _strings(node: Any) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [s for v in node.values() for s in _strings(v)]
    if isinstance(node, list):
        return [s for v in node for s in _strings(v)]
    return []


def gatekeeper(sent: dict[str, Any], out: dict[str, Any], d: Directory | None) -> list[str]:
    problems = []
    attachment = sent.get("mode") == "attachment"
    source = " ".join(_strings(sent.get("attachment_text" if attachment else "submission")))
    for i, span in enumerate(out["personal_data"]["spans"]):
        if span["quote"] not in source:
            problems.append(f"personal_data.spans[{i}].quote is not an exact substring of the input")
    for tag in out["investor_context_tags"]:
        if tag not in source:
            problems.append(f"investor_context_tags has {tag}, which is not in the input")
    if attachment != (out["kind"]["value"] == "not_applicable"):
        problems.append("kind.value must be not_applicable in attachment mode, and only there")
    return problems


def _diff(path: str, given: Any, got: Any, problems: list[str]) -> None:
    if given in (None, "", [], {}):
        return  # empty: the assistant may suggest
    if isinstance(given, dict):
        for k, v in given.items():
            _diff(f"{path}.{k}", v, got.get(k) if isinstance(got, dict) else None, problems)
        return
    if given != got:
        problems.append(f"{path} was given by the person and must be copied exactly")


def canvas_assist(sent: dict[str, Any], out: dict[str, Any], d: Directory | None) -> list[str]:
    problems: list[str] = []
    answers = sent.get("canvas_answers") or {}
    for key in SUBMITTER_SECTIONS:
        _diff(key, answers.get(key), out.get(key), problems)
    slice_ = sent.get("taxonomy_slice") or {}
    allowed = {x["id"] for group in slice_.values() if isinstance(group, list) for x in group if "id" in x}
    for key in ("lobs", "areas", "systems", "roles_affected"):
        for value in out["system"][key]:
            if value not in allowed:
                problems.append(f"system.{key} has {value}, which is not in taxonomy_slice")
    summary = out["neutral_summary"]
    if TAG_RE.search(summary):
        problems.append("neutral_summary must not contain tags")
    if len(summary.split()) > 25:
        problems.append("neutral_summary must be 25 words or fewer")
    if d is not None and detect(summary, d):
        problems.append(
            "neutral_summary must not name a person, client or organisation, or hold an identifier"
        )
    if out.get("one_line") and len(str(out["one_line"]).split()) > 20:
        problems.append("one_line must be 20 words or fewer")
    if len(out["strength"]["next_best"]) > 2:
        problems.append("strength.next_best holds at most two items")
    return problems


def judge(sent: dict[str, Any], out: dict[str, Any], d: Directory | None) -> list[str]:
    problems: list[str] = []
    cids = [str(c.get("cid")) for c in sent.get("candidates") or []]
    got = [r["cid"] for r in out["results"]]
    if got != cids:
        problems.append(
            "results must have exactly one entry per candidate, with the cids copied, in input order"
        )
    for i, r in enumerate(out["results"]):
        if len(r["reason"].split()) > 25:
            problems.append(f"results[{i}].reason must be 25 words or fewer")
    best = out["best_same"]
    if best is not None and not any(r["cid"] == best and r["label"] == "same" for r in out["results"]):
        problems.append("best_same must be a cid labelled same, or null")
    return problems


CHECKS: dict[str, Check] = {"gatekeeper": gatekeeper, "canvas-assist": canvas_assist, "judge": judge}


def run(name: str, sent: dict[str, Any], out: dict[str, Any], d: Directory | None) -> list[str]:
    check = CHECKS.get(name)
    return check(sent, out, d) if check else []
