"""Render a decision file (`decisions/YYYY/DEC-YYYY-NNNN.md`, §2.2 and §4.7 step 9) from the database.

It holds the vote count, the collated strengths and concerns, conditions, the route and the reasons, never who
voted what (non-negotiable 6). Text is the tagged text the chair approved, as for every other repo file.
"""

from __future__ import annotations

from typing import Any

from okf.frontmatter import dump
from repo_writer.render import cell, esc, iso

OUTCOME_WORDS = {"picked": "Picked", "parked": "Parked", "declined": "Declined"}
VOTE_WORDS = {
    "accept": "accept",
    "accept_with_conditions": "accept with conditions",
    "park": "park",
    "decline": "decline",
}


def render_decision(d: dict[str, Any], sheet: dict[str, Any] | None, round_: dict[str, Any] | None) -> str:
    themes = (sheet or {}).get("themes") or {}
    meta: dict[str, Any] = {
        "type": "decision",
        "title": f"{OUTCOME_WORDS[d['outcome']]}: {d['cluster_id']}",
        "description": f"The 1% Club core committee's decision on {d['cluster_id']}: {OUTCOME_WORDS[d['outcome']].lower()}.",
        "tags": ["decision", d["outcome"]],
        "status": "stable",
        "verified": [{"by": f"human:{d['decided_by']}", "at": iso(d["decided_at"])}],
        "kfin": {
            "id": d["id"],
            "cluster": d["cluster_id"],
            "body": d["body"],
            "outcome": d["outcome"],
            "route": d.get("route"),
            "reason_code": d.get("reason_code"),
            "scorecard_version": (round_ or {}).get("scorecard_version"),
            "final_score": float(sheet["final_score"])
            if sheet and sheet.get("final_score") is not None
            else None,
            "dimension_medians": (sheet or {}).get("medians") or {},
            "members_present": int(d["members_present"]),
            "recused": int(d.get("recused") or 0),
            "override": {"used": bool(d.get("override_reason"))},
            "appeal_window_closes": iso(d["appeal_window_closes"]) if d.get("appeal_window_closes") else None,
        },
    }
    if d["outcome"] == "declined":
        at = d["decided_at"]
        # 12 months (§4.12); a decision on 29 February goes stale on 28 February.
        meta["stale_after"] = iso(
            at.replace(year=at.year + 1, day=28)
            if (at.month, at.day) == (2, 29)
            else at.replace(year=at.year + 1)
        )
    votes = d.get("votes") or {}
    body = [
        "## Decision",
        f"{OUTCOME_WORDS[d['outcome']]}"
        + (f", route: {d['route']}" if d.get("route") else "")
        + (f", reason: {d['reason_code']}" if d.get("reason_code") else "")
        + ".",
        "",
        "## Why",
        esc(d.get("plain_reason")) or "Recorded without a written reason.",
        "",
        "## What would change this decision",
        esc(d.get("what_would_change")) or "Not applicable.",
        "",
        "## Votes",
        "| Vote | Count |",
        "|---|---|",
        *[f"| {VOTE_WORDS.get(k, k)} | {int(v)} |" for k, v in votes.items()],
        "",
        "## Strengths the committee saw",
        "\n".join(f"- {esc(t['theme'])} ({int(t['count'])})" for t in themes.get("strengths") or [])
        or "Not collated.",
        "",
        "## Concerns",
        "\n".join(f"- {esc(t['theme'])} ({int(t['count'])})" for t in themes.get("concerns") or [])
        or "Not collated.",
        "",
        "## Conditions",
        "\n".join(f"- {esc(c)}" for c in d.get("conditions") or []) or "None.",
        "",
    ]
    return dump(meta, "\n" + "\n".join(body))


def decision_index_line(did: str, description: str) -> str:
    return f"* [{did}]({did}.md) - {cell(description)}"


def cluster_sections(
    gates: list[dict[str, Any]], impact: dict[str, Any] | None, round_: dict[str, Any] | None
) -> dict[str, str]:
    """The Evidence, Gates, Impact estimate and Preliminary review sections of a cluster file (§4.5 step 6,
    §4.6 step 10). Medians only: individual scores never reach the repo."""
    gate_words = {"evidence": "Evidence exists", "not_solved": "Not already running", "not_planned": "Not already planned",
                  "no_conflict": "No regulatory or IP conflict"}  # fmt: skip
    out: dict[str, str] = {}
    ev = next((g for g in gates if g["gate"] == "evidence"), None)
    if ev:
        e = ev.get("evidence") or {}
        out["Evidence"] = (
            f"- Contributors: {e.get('contributors', 0)}\n- Ideas with their own data: {len(e.get('own_data') or [])}\n"
            f"- Research files: {e.get('clean_files', 0)}\n- References: {e.get('references', 0)}"
        )
    if gates:
        out["Gates"] = "| Gate | Result | Confirmed by |\n|---|---|---|\n" + "\n".join(
            f"| {gate_words.get(g['gate'], g['gate'])} | {g.get('result') or 'pending'}"
            f"{' (' + str(g['detail']).replace('_', ' ') + ')' if g.get('detail') else ''} | {g.get('confirmed_by') or ''} |"
            for g in gates
        )
    if impact and impact.get("updated_by"):
        f = impact.get("fields") or {}
        nb = impact.get("annual_net_benefit")
        out["Impact estimate"] = (
            f"Starting from the contributors' own estimates; validated by {impact['updated_by']}.\n\n"
            + "\n".join(
                f"- {cell(k.replace('_', ' '))}: {v}" for k, v in f.items() if k != "dependency_names"
            )
            + (f"\n- Annual net benefit (computed): ₹{float(nb):,.0f}" if nb is not None else "")
            + (
                f"\n- Payback (computed): {impact['payback_months']} months"
                if impact.get("payback_months") is not None
                else ""
            )
        )
    if round_ and round_.get("state") in ("revealed", "decided"):
        med = round_.get("medians") or {}
        out["Preliminary review"] = (
            f"- Scorecard: {round_['scorecard_version']}\n- Final score: {round_.get('final_score')}\n"
            f"- Members: {len(round_.get('roster') or [])}\n- Outcome: {round_.get('outcome') or 'pending'}\n\n"
            "| Dimension | Median |\n|---|---|\n"
            + "\n".join(f"| {cell(k.replace('_', ' '))} | {v} |" for k, v in med.items())
        )
    return out
