"""Render an appeal file (`appeals/YYYY/APL-YYYY-NNNN.md`, §2.2 and §4.12 step 5) and the appeals index with its
statistics (§4.12 step 6). The appellant is a contributor code and the panel a size: never a name. Text is the
tagged text the colleagues and the panel wrote, as for every other repo file."""

from __future__ import annotations

from typing import Any

from okf.frontmatter import dump
from repo_writer.render import cell, esc, iso

GROUND_WORDS = {
    "process_not_followed": "The process was not followed",
    "misunderstood_or_wrongly_merged": "Misunderstood or wrongly grouped",
    "new_evidence": "New evidence",
}
OUTCOME_WORDS = {"upheld": "Upheld", "re_score": "Back to scoring", "overturned": "Overturned"}
OUTCOME_META = {"upheld": "upheld", "re_score": "re-score", "overturned": "overturned"}  # §2.2 spelling
BODY_WORDS = {"lob": "A LOB committee", "core": "The core committee"}


def render_appeal(a: dict[str, Any], decision: dict[str, Any]) -> str:
    outcome = a.get("outcome")
    words = OUTCOME_WORDS.get(outcome or "", "Waiting for the panel")
    meta: dict[str, Any] = {
        "type": "appeal",
        "title": f"Appeal {a['id']} on {a['decision_id']}",
        "description": f"An appeal on {a['decision_id']} ({a['cluster_id']}): {words.lower()}.",
        "tags": ["appeal", OUTCOME_META.get(outcome or "", "open")],
        "status": "stable" if a["state"] == "decided" else "draft",
        "kfin": {
            "id": a["id"],
            "appellant": a["appellant_code"],
            "decision": a["decision_id"],
            "cluster": a["cluster_id"],
            "grounds": list(a["grounds"]),
            "panel": {"size": len(a["panel"]), "heard_by": a["heard_by"]},
            "hearing": {"requested": bool(a.get("hearing_requested"))},
            "outcome": OUTCOME_META.get(outcome or ""),
            "filed_at": iso(a["filed_at"]),
        },
    }
    if a.get("decided_by") and a.get("decided_at"):
        meta["verified"] = [{"by": f"human:{a['decided_by']}", "at": iso(a["decided_at"])}]
    year = str(a["decision_id"]).split("-")[1]
    body = [
        "## The decision appealed",
        f"[{a['decision_id']}](../../decisions/{year}/{a['decision_id']}.md): "
        f"{BODY_WORDS.get(str(decision.get('body')), 'The committee')} {decision.get('outcome', '')} "
        f"{a['cluster_id']}.",
        "",
        "## Grounds",
        "\n".join(f"- {GROUND_WORDS.get(g, cell(g))}" for g in a["grounds"]),
        "",
        "## Statement",
        esc(a["statement"]),
        "",
        "## Evidence links",
        "\n".join(f"- {cell(link)}" for link in a.get("links") or []) or "None given.",
        "",
        "## Outcome",
        words + ".",
        "",
        "## Reasons",
        esc(a.get("reasons")) or "Not decided yet.",
        "",
    ]
    return dump(meta, "\n" + "\n".join(body))


def appeal_index_line(aid: str, description: str) -> str:
    return f"* [{aid}]({aid}.md) - {cell(description)}"


def appeals_index(stats: list[dict[str, Any]], years: list[str]) -> str:
    """`appeals/index.md`: appeals filed and their outcomes by deciding body, counts only (§4.12 step 6)."""

    def n(v: Any) -> str:  # the same suppression as the fairness report: no one picked out of a small group
        return str(int(v)) if int(v) == 0 or int(v) >= 5 else "fewer than 5"

    rows = [
        f"| {BODY_WORDS.get(str(s['body']), cell(s['body']))} | {n(s['filed'])} | {n(s['open'])} | "
        f"{n(s['upheld'])} | {n(s['re_score'])} | {n(s['overturned'])} |"
        for s in stats
    ]
    lines = [
        "# Appeals",
        "",
        "`appeals/YYYY/APL-YYYY-NNNN.md` — appeals, panels and outcomes.",
        "",
        "## Statistics",
        "",
        'Counts only, names removed; any count under 5 shows as "fewer than 5". Updated with every appeal.',
        "",
        "| Decided by | Filed | Open | Upheld | Back to scoring | Overturned |",
        "|---|---|---|---|---|---|",
        *(rows or ["| — | 0 | 0 | 0 | 0 | 0 |"]),
        "",
        "## By year",
        "",
        *[f"* [{y}]({y}/) - appeals filed in {y}" for y in years],
    ]
    return "\n".join(lines) + "\n"
