"""Agent-specific checks on validated output (config `post_checks`). Each returns plain problems that are sent
back to the model on the one retry, so they quote tagged text at most and never a real value."""

from __future__ import annotations

import re
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
    allowed = {
        x["id"]
        for group in slice_.values()
        if isinstance(group, list)
        for x in group
        if isinstance(x, dict) and "id" in x
    }
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


def _card_safe(field: str, text: str, max_words: int, d: Directory | None, problems: list[str]) -> None:
    """Text shown to everyone (cluster descriptions on match cards): no tags, names or identifiers."""
    if TAG_RE.search(text):
        problems.append(f"{field} must not contain tags")
    if len(text.split()) > max_words:
        problems.append(f"{field} must be {max_words} words or fewer")
    if d is not None and detect(text, d):
        problems.append(f"{field} must not name a person, client or organisation, or hold an identifier")


def cluster_summary(sent: dict[str, Any], out: dict[str, Any], d: Directory | None) -> list[str]:
    problems: list[str] = []
    members = [m for m in sent.get("members") or [] if isinstance(m, dict)]
    refs = {str(m.get("ref")) for m in members}
    _card_safe("name", out["name"], 8, d, problems)  # the name goes into every contributor's message
    _card_safe("description", out["description"], 25, d, problems)
    for i, v in enumerate(out["variations"]):
        if v["member"] not in refs:
            problems.append(f"variations[{i}].member is not one of the member refs")
    for i, part in enumerate(out["solution"]):
        unknown = [r for r in part["credit"] if r not in refs]
        if unknown:
            problems.append(f"solution[{i}].credit names refs that are not members")
    for key, field in (("lobs", "lobs"), ("roles_affected", "roles_affected")):
        allowed = {x for m in members for x in m.get(key) or []}
        if any(x not in allowed for x in out[field]):
            problems.append(f"{field} may only use the members' own {field}")
    return problems


def attachment_digest(sent: dict[str, Any], out: dict[str, Any], d: Directory | None) -> list[str]:
    problems: list[str] = []
    pieces = [p for p in sent.get("text") or [] if isinstance(p, dict)]
    locations = {str(p.get("location")) for p in pieces}
    source = "\n".join(str(p.get("text") or "") for p in pieces)
    if len(out["summary"].split()) > 150:
        problems.append("summary must be 150 words or fewer")
    for i, c in enumerate(out["claims"]):
        if c["location"] not in locations:
            problems.append(f"claims[{i}].location must be copied exactly from one of the pieces")
        if c["figure"] is not None and c["figure"] not in source:
            problems.append(f"claims[{i}].figure must appear in the text exactly as written")
        if len(c["text"].split()) > 25:
            problems.append(f"claims[{i}].text must be 25 words or fewer")
    return problems


_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _numbers(text: str) -> set[float]:
    return {float(n.replace(",", "")) for n in _NUMBER.findall(TAG_RE.sub(" ", text))}


def handover_draft(sent: dict[str, Any], out: dict[str, Any], d: Directory | None) -> list[str]:
    """Values only from the options; numbers only if a member's summary gave them; metric, objective and notes are
    card-safe, with the colleague and client detector (BLD-138, BLD-141)."""
    problems: list[str] = []
    opts = sent.get("options") or {}
    for key, field in (("units", "unit"), ("products", "product"), ("feature_types", "feature_type")):
        if out[field] not in (opts.get(key) or []):
            problems.append(f"{field} must be one of options.{key}")
    members = [m for m in sent.get("members") or [] if isinstance(m, dict)]
    given = _numbers(" ".join(str(m.get("summary") or "") for m in members))
    for field in ("baseline", "target"):
        if out[field] is not None and float(out[field]) not in given:
            problems.append(f"{field} must be a number a member gave, or null")
    _card_safe("metric", out["metric"], 20, d, problems)
    if out["objective"] is not None:
        _card_safe("objective", out["objective"], 40, d, problems)
    if (sent.get("track") == "fix") != (out["objective"] is not None):
        problems.append("objective is for the fix track only, and the fix track needs one")
    for i, note in enumerate(out["notes"]):
        _card_safe(f"notes[{i}]", note, 25, d, problems)
    return problems


def role_themes(sent: dict[str, Any], out: dict[str, Any], d: Directory | None) -> list[str]:
    """Refs exist, each idea in one theme at most, and names and descriptions are card-safe (BLD-139)."""
    problems: list[str] = []
    refs = {str(i.get("ref")) for i in sent.get("ideas") or [] if isinstance(i, dict)}
    seen: set[str] = set()
    for n, theme in enumerate(out["themes"]):
        _card_safe(f"themes[{n}].name", theme["name"], 8, d, problems)
        _card_safe(f"themes[{n}].description", theme["description"], 25, d, problems)
        if any(r not in refs for r in theme["refs"]):
            problems.append(f"themes[{n}].refs names refs that are not in the input")
        if seen & set(theme["refs"]) or len(set(theme["refs"])) < len(theme["refs"]):
            problems.append(f"themes[{n}].refs repeats an idea already in a theme")
        seen |= set(theme["refs"])
    return problems


def prescore(sent: dict[str, Any], out: dict[str, Any], d: Directory | None) -> list[str]:
    problems: list[str] = []
    dims = list((sent.get("scorecard") or {}).keys())
    got = [s["dimension"] for s in out["scores"]]
    if got != dims:
        problems.append(
            "scores must have exactly one entry per scorecard dimension, in the scorecard's order"
        )
    band = (sent.get("impact") or {}).get("suggested_financial_band")
    for i, s in enumerate(out["scores"]):
        if len(s["rationale"].split()) > 40:
            problems.append(f"scores[{i}].rationale must be 40 words or fewer")
        if s["dimension"] == "financial_value" and isinstance(band, int) and abs(s["value"] - band) > 1:
            problems.append("financial_value must be within one level of suggested_financial_band")
    return problems


SLIDE_TITLES = 8
BANNED = re.compile(r"\b(rejected|duplicate|already solved|garage)\b", re.I)


def pitch_prep(sent: dict[str, Any], out: dict[str, Any], d: Directory | None) -> list[str]:
    problems: list[str] = []
    if len(out["slides"]) != SLIDE_TITLES:
        problems.append("slides must have exactly 8 entries, in the deck template's order")
    for i, s in enumerate(out["slides"]):
        for j, p in enumerate(s["points"]):
            if len(p.split()) > 15:
                problems.append(f"slides[{i}].points[{j}] must be 15 words or fewer")
    return problems


def collation(sent: dict[str, Any], out: dict[str, Any], d: Directory | None) -> list[str]:
    problems: list[str] = []
    members = {str(a.get("member")) for a in sent.get("assessments") or [] if isinstance(a, dict)}
    for key in ("strengths", "concerns"):
        for i, t in enumerate(out[key]):
            if not set(t["members"]) <= members:
                problems.append(f"{key}[{i}].members names someone who did not assess")
            if t["count"] != len(set(t["members"])):
                problems.append(f"{key}[{i}].count must equal the number of members listed")
    for i, c in enumerate(out["conditions"]):
        if not set(c["members"]) <= members:
            problems.append(f"conditions[{i}].members names someone who did not assess")
    return problems


def reason_writer(sent: dict[str, Any], out: dict[str, Any], d: Directory | None) -> list[str]:
    problems: list[str] = []
    if len(out["reason"].split()) > 90:
        problems.append("reason must be 90 words or fewer")
    for key in ("reason", "what_would_change"):
        if BANNED.search(out[key]):
            problems.append(f"{key} must not use the words rejected, duplicate, already solved or Garage")
    if any(BANNED.search(p) for p in out["feedback_points"]):
        problems.append(
            "feedback_points must not use the words rejected, duplicate, already solved or Garage"
        )
    if re.search(
        r"\bMember \d+\b", " ".join([out["reason"], out["what_would_change"], *out["feedback_points"]])
    ):
        problems.append("never name or count individual members")
    return problems


CHECKS: dict[str, Check] = {
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
}


def run(name: str, sent: dict[str, Any], out: dict[str, Any], d: Directory | None) -> list[str]:
    check = CHECKS.get(name)
    return check(sent, out, d) if check else []
