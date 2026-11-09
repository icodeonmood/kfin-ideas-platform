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


_WORD = re.compile(r"[a-z][a-z0-9]{2,}")
_COMMON = frozenset(
    [
        "the",
        "and",
        "for",
        "with",
        "from",
        "that",
        "this",
        "are",
        "was",
        "were",
        "have",
        "has",
        "into",
        "their",
        "they",
        "our",
        "ops",
    ]
)


def _words(*texts: Any) -> set[str]:
    return {w for t in texts for w in _WORD.findall(str(t or "").lower()) if w not in _COMMON}


def judge(spec: AgentSpec, inputs: dict[str, Any]) -> dict[str, Any]:
    """Word overlap stands in for meaning: same at Jaccard 0.35+, related at 0.15+ (dev and tests only)."""
    card = inputs.get("card") or {}
    mine = _words(card.get("one_line"), card.get("details"))
    results = []
    for c in inputs.get("candidates") or []:
        theirs = _words(c.get("title"), c.get("summary"))
        overlap = len(mine & theirs) / max(1, len(mine | theirs))
        label = "same" if overlap >= 0.35 else "related" if overlap >= 0.15 else "different"
        reason = {
            "same": "Describes the same problem in the same process.",
            "related": "Touches the same process but a different cause.",
            "different": "A different problem.",
        }[label]
        results.append(
            {"cid": c["cid"], "label": label, "reason": reason, "confidence": round(0.5 + overlap / 2, 2)}
        )
    same = [r for r in results if r["label"] == "same"]
    best = max(same, key=lambda r: r["confidence"])["cid"] if same else None
    return {"results": results, "best_same": best}


def _clip(text: Any, words: int) -> str:
    return " ".join(str(text or "").split()[:words])


def _untagged(text: Any) -> str:
    return " ".join(TAG_RE.sub("", str(text or "")).split())


def cluster_summary(spec: AgentSpec, inputs: dict[str, Any]) -> dict[str, Any]:
    """Built from the members' own words: the first member's one-line as the name, each later member as a
    variation, every proposed fix credited to its member (dev and tests only)."""
    members = [m for m in inputs.get("members") or [] if isinstance(m, dict)][:30]
    existing = inputs.get("existing") or {}
    first = members[0] if members else {}
    name = _clip(existing.get("name") or _untagged(first.get("one_line")) or "Shared problem", 8)
    lobs = sorted({x for m in members for x in m.get("lobs") or []})[:12]
    roles = sorted({x for m in members for x in m.get("roles_affected") or []})[:12]
    problem = " ".join(str(m.get("one_line") or "").strip().rstrip(".") + "." for m in members[:5])
    return {
        "name": name if len(name) >= 3 else "Shared problem",
        "description": _clip(
            f"{_untagged(first.get('one_line')) or 'A shared problem'}; raised by {len(members)} colleagues.",
            25,
        ),
        "problem": problem if len(problem) >= 20 else "Several colleagues describe the same problem.",
        "variations": [
            {"member": m["ref"], "note": _clip(m.get("one_line"), 30) or "Same problem."} for m in members[1:]
        ],
        "solution": [{"text": _clip(m["fix"], 90), "credit": [m["ref"]]} for m in members if m.get("fix")][
            :4
        ],
        "lobs": lobs,
        "roles_affected": roles,
        "open_questions": ["How often does this happen across the LOBs named?"],
    }


_FIGURE = re.compile(r"\d[\d,]*(?:\.\d+)?%?")


def attachment_digest(spec: AgentSpec, inputs: dict[str, Any]) -> dict[str, Any]:
    """The first lines of the file as the summary; numbers copied as written, with their locations (dev only)."""
    pieces = [p for p in inputs.get("text") or [] if isinstance(p, dict) and p.get("text")]
    file = inputs.get("file") or {}
    claims: list[dict[str, Any]] = []
    for p in pieces:
        plain = _untagged(p["text"])  # a number inside a tag is not a figure
        m = _FIGURE.search(plain)
        if m and len(claims) < 8 and len(plain) >= 3:
            claims.append(
                {"text": _clip(plain, 25), "figure": m.group(0), "location": str(p["location"])[:80]}
            )
    words = " ".join(str(p["text"]) for p in pieces[:3])
    summary = _clip(words, 60) or "The file has no readable text."
    kind = "image" if file.get("ocr") else "data" if file.get("kind") in ("xlsx", "csv") else "document"
    return {"summary": summary if len(summary) >= 10 else "The file has no readable text.", "claims": claims,
            "kind_of_evidence": kind}  # fmt: skip


_UNIT_HINTS = (
    ("minute", "minutes per case"), ("hour", "hours a month"), ("days", "days to complete"),
    ("call", "calls a month"), ("error", "errors a month"), ("per cent", "per cent"), ("%", "per cent"),
    ("rupee", "rupees a month"), ("₹", "rupees a month"),
)  # fmt: skip


def handover_draft(spec: AgentSpec, inputs: dict[str, Any]) -> dict[str, Any]:
    """The first member's one-line as the metric, a unit from words in the text, no numbers (dev and tests only)."""
    members = [m for m in inputs.get("members") or [] if isinstance(m, dict)][:12]
    opts = inputs.get("options") or {}
    units = [str(u) for u in opts.get("units") or []] or ["cases a month"]
    text = " ".join(f"{m.get('one_line') or ''} {m.get('details') or ''}" for m in members).lower()
    unit = next((u for hint, u in _UNIT_HINTS if hint in text and u in units), None)
    unit = unit or ("cases a month" if "cases a month" in units else units[0])
    products = [str(x) for x in opts.get("products") or []] or ["other"]
    features = [str(x) for x in opts.get("feature_types") or []] or ["kfintech-product"]
    first = members[0] if members else {}
    metric = _clip(_untagged(first.get("one_line")), 20)
    fix = _untagged(first.get("fix") or first.get("one_line"))
    return {
        "metric": metric if len(metric) >= 5 else "Cases handled",
        "unit": unit,
        "baseline": None,
        "target": None,
        "product": "other" if "other" in products else products[0],
        "feature_type": "kfintech-product" if "kfintech-product" in features else features[0],
        "objective": _clip(f"Done when this is fixed: {fix}", 40) if inputs.get("track") == "fix" else None,
        "notes": ["What number should we aim for, and who measures it?"],
    }


def role_themes(spec: AgentSpec, inputs: dict[str, Any]) -> dict[str, Any]:
    """Ideas grouped by their first area tag; a theme for each area with two or more ideas (dev and tests only)."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for idea in [i for i in inputs.get("ideas") or [] if isinstance(i, dict)][:40]:
        area = str((idea.get("areas") or ["Other"])[0])
        groups.setdefault(area, []).append(idea)
    themes: list[dict[str, Any]] = []
    for area, ideas in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        if len(ideas) < 2 or len(themes) == 4:
            continue
        name = _clip(f"Recurring {_untagged(area).lower()} friction", 8)
        themes.append({
            "name": name if len(name) >= 3 else "Recurring friction",
            "description": f"{len(ideas)} ideas raise the same kind of {_untagged(area).lower()} problem.",
            "refs": [str(i["ref"]) for i in ideas],
        })  # fmt: skip
    return {"themes": themes}


BUILDERS = {
    "gatekeeper": gatekeeper,
    "canvas-assist": canvas_assist,
    "judge": judge,
    "cluster-summary": cluster_summary,
    "attachment-digest": attachment_digest,
    "handover-draft": handover_draft,
    "role-themes": role_themes,
}


def output_for(spec: AgentSpec, inputs: dict[str, Any]) -> dict[str, Any]:
    for example in spec.examples:
        if example.input == inputs:
            return copy.deepcopy(example.output)
    builder = BUILDERS.get(spec.name)
    if builder is not None:
        return builder(spec, inputs)
    return copy.deepcopy(spec.example(spec.fake_default).output)
