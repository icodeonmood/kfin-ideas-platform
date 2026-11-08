"""Fake-mode outputs (LLM_MODE=fake): schema-valid and built from the tagged input, so dev, tests and the
end-to-end suite exercise every screen without a model or a key. These are NOT the agents' behaviour; real
quality is measured on the real route by `make eval` in UAT. Simple keyword rules let tests reach the block,
redirect and hold paths on purpose.
"""

from __future__ import annotations

import copy
import re
from typing import Any

from gateway.spec import AgentSpec
from pii.tagger import TAG_RE

_INVESTOR_WORDS = re.compile(r"\b(investor|customer|unitholder|unit holder|nominee|policyholder)s?\b", re.I)
_TICKET = re.compile(
    r"\b(password|laptop|vpn|login|access card|outlook)\b.{0,60}\b(not working|reset|locked|down|broken|issue)\b",
    re.I,
)
_HR = re.compile(r"\b(my (salary|appraisal|leave|manager)|increment|harass)", re.I)
_QUESTION = re.compile(r"^\s*(how|what|when|where|who|can|is|does)\b[^.?!]*\?\s*$", re.I)
_SPAM = re.compile(r"^\s*(test|asdf|qwerty|lorem ipsum)\b", re.I)
_SOLUTION = re.compile(r"\b(we should|we could|i propose|fix would|automate|build a|add a)\b", re.I)
_KIND_MAP = {
    "idea_problem": "problem",
    "idea_solution": "problem_with_solution",
    "business_idea": "business_idea",
}


def _texts(node: Any, path: str = "") -> list[tuple[str, str]]:
    if isinstance(node, str):
        return [(path or "text", node)]
    if isinstance(node, dict):
        return [t for k, v in node.items() for t in _texts(v, f"{path}.{k}" if path else k)]
    if isinstance(node, list):
        return [t for v in node for t in _texts(v, path)]
    return []


def gatekeeper(spec: AgentSpec, inputs: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(spec.example(spec.fake_default).output)
    attachment = inputs.get("mode") == "attachment"
    body = inputs.get("attachment_text" if attachment else "submission") or {}
    texts = _texts(body)
    spans, investor_tags = [], []
    for field, text in texts:
        for m in TAG_RE.finditer(text):
            if m.group(1) != "PERSON":
                continue
            window = text[max(0, m.start() - 40) : m.end() + 40]
            if _INVESTOR_WORDS.search(window):
                quote = text[m.start() : min(len(text), m.end() + 30)].strip()[:80]
                spans.append(
                    {
                        "field": field[:80],
                        "quote": quote,
                        "data_type": "tagged_person_as_investor",
                        "confidence": 0.9,
                        "reason": "Tagged person is described as an investor or customer",
                    }
                )
                investor_tags.append(m.group(0))
    out["personal_data"] = {"found": bool(spans), "confidence": 0.9 if spans else 0.05, "spans": spans[:20]}
    out["investor_context_tags"] = sorted(set(investor_tags))[:20]
    whole = " ".join(t for _, t in texts)
    if attachment:
        kind = ("not_applicable", 0.99)
    elif _SPAM.search(whole):
        kind = ("spam", 0.95)
    elif _TICKET.search(whole):
        kind = ("it_ticket", 0.9)
    elif _HR.search(whole):
        kind = ("hr_grievance", 0.85)
    elif _QUESTION.search(whole):
        kind = ("question", 0.85)
    elif _SOLUTION.search(whole):
        kind = ("idea_solution", 0.8)
    else:
        kind = ("idea_problem", 0.8)
    out["kind"] = {"value": kind[0], "confidence": kind[1]}
    out["abuse"] = {"value": False, "confidence": 0.98}
    out["language"] = {"primary": "en", "mixed": False}
    out["notes_for_reviewer"] = None
    return out


def _leaves(node: Any, path: str = "") -> list[tuple[str, Any]]:
    if isinstance(node, dict) and node:
        return [x for k, v in node.items() for x in _leaves(v, f"{path}.{k}" if path else k)]
    return [(path, node)]


def canvas_assist(spec: AgentSpec, inputs: dict[str, Any]) -> dict[str, Any]:
    answers = copy.deepcopy(inputs.get("canvas_answers") or {})
    gk = (inputs.get("gatekeeper") or {}).get("kind") or {}
    gk_kind = gk.get("value") if isinstance(gk, dict) else gk
    provenance: dict[str, str] = {}
    for path, value in _leaves({k: v for k, v in answers.items() if k != "attachments"}):
        if value not in (None, "", [], {}):
            provenance[path] = "submitter"
    out: dict[str, Any] = answers
    out.setdefault("details", "")
    if not out.get("kind"):
        out["kind"] = _KIND_MAP.get(str(gk_kind), "problem")
        provenance["kind"] = "suggested"
    if not out.get("one_line"):
        words = str(out.get("details") or "").split()
        out["one_line"] = " ".join(words[:20]) or "An improvement idea"
        provenance["one_line"] = "suggested"
    eco = out.setdefault("ecosystem", {})
    if not eco.get("solved_elsewhere"):
        eco["solved_elsewhere"] = (
            "dont_know"  # the schema needs a value; a person's blank reads as don't know
        )
        provenance["ecosystem.solved_elsewhere"] = "suggested"
    value = out.setdefault("value", {})
    if not value.get("category"):
        value["category"] = "not_sure"
        provenance["value.category"] = "suggested"
    out["neutral_summary"] = "An idea to improve a KFintech process."
    out.setdefault("attachments", [])
    slice_ = inputs.get("taxonomy_slice") or {}

    def first(key: str) -> list[str]:
        return [str(x["id"]) for x in (slice_.get(key) or [])[:1]]

    out["system"] = {
        "scope": "lob",
        "lobs": first("lobs"),
        "areas": first("areas"),
        "systems": [],
        "roles_affected": [],
    }
    out["provenance"] = provenance
    out["flags_for_reviewer"] = []
    out["confidence"] = {
        "value.category": 0.5,
        "value.play": 0.5,
        "system.scope": 0.5,
        "system.areas": 0.5,
        "system.systems": 0.5,
    }
    out["strength"] = {"score": 0, "next_best": ["Add what it is worth", "Add your evidence"]}
    return out


BUILDERS = {"gatekeeper": gatekeeper, "canvas-assist": canvas_assist}


def output_for(spec: AgentSpec, inputs: dict[str, Any]) -> dict[str, Any]:
    for example in spec.examples:
        if example.input == inputs:
            return copy.deepcopy(example.output)
    builder = BUILDERS.get(spec.name)
    if builder is not None:
        return builder(spec, inputs)
    return copy.deepcopy(spec.example(spec.fake_default).output)
