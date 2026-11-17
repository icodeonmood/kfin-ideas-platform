"""Fake-mode outputs (LLM_MODE=fake): schema-valid and built from the tagged input, so dev, tests and the
end-to-end suite exercise every screen without a model or a key. These are NOT the agents' behaviour; real
quality is measured on the real route by `make eval` in UAT. Simple keyword rules let tests reach the block,
redirect and hold paths on purpose.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Callable
from typing import Any

from gateway import grounding
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
# Text that tempts a model to put a rupee figure on a vague cost: the fake does, with a quote that is not in the
# input, on both asks, so tests and the golden set reach the gateway's drop path (DEC-095).
_PLANT_FIGURE = re.compile(r"\ba lot of money\b", re.I)
# A cost "in salaries": the fake prices it with a salary that is not on the allowed list (DEC-097), on both asks.
_PLANT_ASSUMPTION = re.compile(r"\bcosts us a fortune\b", re.I)
_HOURS_A_DAY = re.compile(r"\b(\d+(?:\.\d+)?)\s*hours?\s+(?:a|per|every)\s+day\b", re.I)
_PEOPLE = re.compile(r"\b(\d+)\s+(?:people|persons|staff|colleagues)\b", re.I)
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


def _num(x: float) -> str:
    return f"{int(x):,}" if float(x).is_integer() else f"{x:g}"


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
    words = str(out.get("details") or "").split()
    opening = " ".join(words[:12])  # the person's own first words: the quote behind each fake suggestion
    evidence: dict[str, list[str]] = {}
    if not out.get("kind"):
        out["kind"] = _KIND_MAP.get(str(gk_kind), "problem")
        provenance["kind"] = "suggested"
        evidence["kind"] = [opening]
    if not out.get("one_line"):
        out["one_line"] = " ".join(words[:20]) or "An improvement idea"
        provenance["one_line"] = "suggested"
        evidence["one_line"] = [" ".join(words[:20])]
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
    evidence["neutral_summary"] = [opening]
    estimate = value.setdefault("estimate", {})
    details = str(out.get("details") or "")
    if _PLANT_FIGURE.search(details) and estimate.get("inr_saved_per_year") is None:
        estimate["inr_saved_per_year"] = 500000
        provenance["value.estimate.inr_saved_per_year"] = "suggested"
        evidence["value.estimate.inr_saved_per_year"] = ["saves us five lakh a year"]
    allowed = {a.get("id"): a for a in inputs.get("assumptions") or [] if isinstance(a, dict)}
    listed: list[dict[str, str]] = []
    hours, people = _HOURS_A_DAY.search(details), _PEOPLE.search(details)
    days = allowed.get("working_days_per_month")
    if (
        hours
        and people
        and days
        and estimate.get("hours_saved_per_month") is None
        and not estimate.get("note")
    ):
        # Plain arithmetic on the person's figures with one listed assumption (DEC-097).
        h, n, d = float(hours.group(1)), float(people.group(1)), float(days["value"])
        total = h * n * d
        estimate["hours_saved_per_month"] = int(total) if total.is_integer() else round(total, 1)
        estimate["note"] = (
            f"{_num(h)} hours a day × {_num(n)} people × {_num(d)} working days = {_num(total)} hours a month"
        )
        for path in ("value.estimate.hours_saved_per_month", "value.estimate.note"):
            provenance[path] = "suggested"
            evidence[path] = [hours.group(0), people.group(0)]
        listed.append({"id": "working_days_per_month", "says": str(days["says"])})
    if _PLANT_ASSUMPTION.search(details) and estimate.get("inr_saved_per_year") is None:
        estimate["inr_saved_per_year"] = 720000
        provenance["value.estimate.inr_saved_per_year"] = "suggested"
        evidence["value.estimate.inr_saved_per_year"] = [opening]
        listed.append({"id": "average_salary_per_month", "says": "₹30,000 salary a month"})
        if "months_per_year" in allowed:
            listed.append({"id": "months_per_year", "says": str(allowed["months_per_year"]["says"])})
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
    out["evidence"] = {k: v for k, v in evidence.items() if not any(grounding.trivial(q) for q in v)}
    out["assumptions"] = listed
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
    """From the members' neutral summaries only: the first as the metric, a unit from words in them, no numbers,
    and an objective in fixed words on the fix track (dev and tests only)."""
    members = [m for m in inputs.get("members") or [] if isinstance(m, dict)][:12]
    opts = inputs.get("options") or {}
    units = [str(u) for u in opts.get("units") or []] or ["cases a month"]
    text = " ".join(str(m.get("summary") or "") for m in members).lower()
    unit = next((u for hint, u in _UNIT_HINTS if hint in text and u in units), None)
    unit = unit or ("cases a month" if "cases a month" in units else units[0])
    products = [str(x) for x in opts.get("products") or []] or ["other"]
    features = [str(x) for x in opts.get("feature_types") or []] or ["kfintech-product"]
    first = members[0] if members else {}
    metric = _clip(_untagged(first.get("summary")), 20)
    return {
        "metric": metric if len(metric) >= 5 else "Cases handled",
        "unit": unit,
        "baseline": None,
        "target": None,
        "product": "other" if "other" in products else products[0],
        "feature_type": "kfintech-product" if "kfintech-product" in features else features[0],
        "objective": "The problem the members describe no longer happens."
        if inputs.get("track") == "fix"
        else None,
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


def prescore(spec: AgentSpec, inputs: dict[str, Any]) -> dict[str, Any]:
    """3 everywhere, financial value at the suggested band (dev only: fake mode never measures a model)."""
    band = (inputs.get("impact") or {}).get("suggested_financial_band")
    scores = []
    for name in inputs.get("scorecard") or {}:
        value = band if name == "financial_value" and isinstance(band, int) else 3
        scores.append({"dimension": name, "value": value, "rationale": "A middle score until the evidence is read.",
                       "evidence": ["impact" if name == "financial_value" else "problem"]})  # fmt: skip
    return {"scores": scores}


DECK = ["The problem", "Who it touches", "What it's worth", "Solved elsewhere, and why KFintech",
        "Proposed approach", "What it needs", "Risks", "The ask"]  # fmt: skip


def pitch_prep(spec: AgentSpec, inputs: dict[str, Any]) -> dict[str, Any]:
    """The deck template with the cluster's own words where they fit (dev only)."""
    c = inputs.get("cluster") or {}
    problem = _clip(_untagged((c.get("summary") or {}).get("problem")), 15) or "Describe the problem"
    first = [problem, "Say who raised it and how often"]
    slides = [{"title": t, "points": first if n == 0 else ["To be written by the presenters", "Find the evidence"]}
              for n, t in enumerate(DECK)]  # fmt: skip
    return {"slides": slides}


def collation(spec: AgentSpec, inputs: dict[str, Any]) -> dict[str, Any]:
    """One theme per distinct wording (exact text), with the members who wrote it (dev only)."""

    def themes(key: str) -> list[dict[str, Any]]:
        seen: dict[str, list[str]] = {}
        for a in inputs.get("assessments") or []:
            for text in a.get(key) or []:
                t = _clip(_untagged(text), 12) or "A point"
                seen.setdefault(t if len(t) >= 3 else "A point", []).append(str(a.get("member")))
        return [{"theme": t, "count": len(set(m)), "members": sorted(set(m))} for t, m in seen.items()][:20]

    conditions: dict[str, list[str]] = {}
    for a in inputs.get("assessments") or []:
        for text in a.get("conditions") or []:
            conditions.setdefault(_clip(_untagged(text), 40) or "A condition", []).append(
                str(a.get("member"))
            )
    return {"strengths": themes("strengths"), "concerns": themes("concerns"),
            "conditions": [{"text": t, "members": sorted(set(m))} for t, m in conditions.items()][:20]}  # fmt: skip


def reason_writer(spec: AgentSpec, inputs: dict[str, Any]) -> dict[str, Any]:
    """A reason built from the top strength and concern (dev only)."""
    themes = inputs.get("themes") or {}
    good = ((themes.get("strengths") or [{}])[0] or {}).get("theme") or "the idea's intent"
    bad = ((themes.get("concerns") or [{}])[0] or {}).get("theme") or "open questions"
    outcome = (inputs.get("outcome") or {}).get("outcome")
    reason = (
        f"The committee valued {_untagged(good).lower()}. It weighed this against {_untagged(bad).lower()}."
    )
    change = "Nothing to add." if outcome == "picked" else "More evidence on the concern above would help."
    return {
        "reason": reason,
        "what_would_change": change,
        "feedback_points": [f"Address: {_untagged(bad).lower()}"],
    }


# ---- draft-part (L-DRAFT.parts) ------------------------------------------------------------------------------------
_DRAFT_EMPTY: dict[str, Any] = {
    "title": None, "summary": None, "often": None, "who": [], "worth": [], "area": None, "reason": None,
    "evidence": [],
}  # fmt: skip
_OFTEN = re.compile(
    r"(?:(?:about|around|nearly|over|more than)\s+)?\d[\d,]*(?:\s+(?:to|-)\s+\d[\d,]*)?\s+(?:[a-z]+\s+){0,2}?"
    r"(?:a|per|every|each)\s+(?:day|week|month|year)",
    re.I,
)
_WORTH_CUES = {
    "saves_time": ("minutes", "minute", "hours", "hour", "by hand", "manually", "re-key", "rekey", "calls"),
    "saves_cost": ("cost", "costs", "money", "courier", "penalty", "lakh", "crore"),
    "earns_revenue": ("revenue", "fee", "fees", "sell", "paid", "charge"),
    "less_outside_tools": ("vendor", "outside tool", "third-party", "third party"),
}


def _neutral(text: str) -> str:
    """Tags become general words, as the prompt asks of a model."""
    return TAG_RE.sub(lambda m: "a colleague" if m.group(1) == "KFIN_EMPLOYEE" else "someone", text)


def _cue_quote(text: str, cue: str) -> str | None:
    """The cue with the words around it, word for word from the text, two words at least."""
    m = re.search(r"(?:\S+\s+){0,2}(?<!\w)" + re.escape(cue) + r"(?!\w)(?:\s+\S+){0,2}", text, re.I)
    if not m:
        return None
    quote = m.group(0).strip(" ,.;:!?\"'")
    return quote if len(quote.split()) >= 2 and not grounding.trivial(quote) else None


def _first_sentence(text: str) -> str:
    pieces = grounding.split_sentences(text)  # "Rs." and "e.g." do not end one
    return pieces[0] if pieces else text.strip()


def _clip_chars(text: str, limit: int) -> str:
    """At most `limit` characters, cut at a word boundary (the draft's summary limit, L-DRAFT.parts)."""
    if len(text) <= limit:
        return text
    cut = text[: limit + 1]
    return (cut.rsplit(" ", 1)[0] if " " in cut else text[:limit]).rstrip(" ,;:")


SUMMARY_MAX = 600
WHO_MAX = 8


def draft_part(spec: AgentSpec, inputs: dict[str, Any]) -> dict[str, Any]:
    """A plain stand-in for each part, built only from the words so it passes the gateway's checks: the first
    sentence for the title, a frequency phrase, cue words for who, worth and area. Words that plant "a lot of money"
    make it quote a figure nobody gave, on both asks, so tests reach the drop path (DEC-095)."""
    part = str(inputs.get("part") or "")
    words = [w for w in inputs.get("words") or [] if isinstance(w, dict) and isinstance(w.get("text"), str)]
    texts = [str(w["text"]) for w in words]
    out: dict[str, Any] = {"part": part, **copy.deepcopy(_DRAFT_EMPTY)}
    if not texts:
        return out
    whole = " ".join(texts)
    if part == "title":
        first = _first_sentence(texts[0])
        title = _neutral(first).rstrip(".!?। ")
        if len(title) > 70:
            title = title[:70].rsplit(" ", 1)[0]
        quote = " ".join(first.rstrip(".!?। ").split()[:12])
        if not quote or grounding.trivial(quote) or not title:
            return out
        summary = _clip_chars(" ".join(_neutral(_first_sentence(t)) for t in texts[:3]), SUMMARY_MAX)
        out.update(title=title[:1].upper() + title[1:], summary=summary, evidence=[quote])
        return out
    if part == "often":
        if _PLANT_FIGURE.search(whole):
            out.update(often="About 5 lakh rupees a month", evidence=["costs about 5 lakh a month"])
            return out
        for text in texts:
            m = _OFTEN.search(text)
            if m:
                phrase = m.group(0)
                out.update(often=_neutral(phrase[:1].upper() + phrase[1:]), evidence=[phrase])
                return out
        return out
    choices = [c for c in (inputs.get("options") or {}).get("choices") or [] if isinstance(c, dict)]
    if part in ("who", "area"):
        picked, quotes, said = [], [], []
        for c in choices:
            for cue in [*(c.get("cues") or []), str(c.get("label") or "").lower()]:
                q = next((q for t in texts if (q := _cue_quote(t, str(cue)))), None)
                if q:
                    picked.append(str(c["label"]))
                    if q not in quotes:
                        quotes.append(q)
                    said.append(str(cue))
                    break
        if not picked:
            return out
        if part == "area":
            picked, quotes, said = picked[:1], quotes[:1], said[:1]
        picked = picked[:WHO_MAX]  # who: at most 8 groups, as a person may pick (L-DRAFT.pins)
        reason = ("you mentioned " if part == "who" else "it's about ") + " and ".join(
            dict.fromkeys(said[:2])
        )
        out.update({part: picked if part == "who" else picked[0], "reason": reason, "evidence": quotes[:3]})
        return out
    if part == "value":
        worth, quotes = [], []
        for key, cues in _WORTH_CUES.items():
            q = next((q for cue in cues for t in texts if (q := _cue_quote(t, cue))), None)
            if q and len(quotes) < 3:
                worth.append(key)
                quotes.append(q)
        out.update(worth=worth or ["not_sure"], evidence=quotes[:3])
        return out
    return out


BUILDERS = {
    "gatekeeper": gatekeeper,
    "canvas-assist": canvas_assist,
    "judge": judge,
    "cluster-summary": cluster_summary,
    "attachment-digest": attachment_digest,
    "handover-draft": handover_draft,
    "role-themes": role_themes,
    "prescore": prescore,
    "pitch-prep": pitch_prep,
    "collation": collation,
    "reason-writer": reason_writer,
    "draft-part": draft_part,
}


def cluster_summary_corrected(spec: AgentSpec, inputs: dict[str, Any]) -> dict[str, Any]:
    """The second answer after the gateway reports problems: the same summary with a neutral name and description,
    the two fields shown to everyone. Copying members' words into them can carry something the card checks refuse
    (the name model reads some word runs as a person), which a real model would rewrite."""
    out = cluster_summary(spec, inputs)
    members = [m for m in inputs.get("members") or [] if isinstance(m, dict)]
    out["name"] = "Shared problem"
    out["description"] = f"A shared problem raised by {len(members)} colleagues."
    return out


# The corrected answer for agents whose built output can fail a content check that a model would fix on retry.
CORRECTED: dict[str, Callable[[AgentSpec, dict[str, Any]], dict[str, Any]]] = {
    "cluster-summary": cluster_summary_corrected
}


def output_for(spec: AgentSpec, inputs: dict[str, Any], *, retry: bool = False) -> dict[str, Any]:
    for example in spec.examples:
        if example.input == inputs:
            return copy.deepcopy(example.output)
    if retry and spec.name in CORRECTED:
        return CORRECTED[spec.name](spec, inputs)
    builder = BUILDERS.get(spec.name)
    if builder is not None:
        return builder(spec, inputs)
    return copy.deepcopy(spec.example(spec.fake_default).output)
