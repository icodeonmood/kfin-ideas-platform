"""Render a cluster file (`clusters/CL-….md`, §2.2) and a clustering run file
(`learning/cluster-runs/RUN-….md`, §4.4 B step 10) from the database.

Cluster text is the cluster-summary agent's tagged output as the review desk approved it; it stays tagged in the
repo exactly like idea text. Run files hold numbers and codes only.
"""

from __future__ import annotations

from typing import Any

from okf.frontmatter import dump
from repo_writer.render import HISTORY_HEADING, HistoryRow, cell, esc, iso

KIND_WORDS = {"new": "new group", "grow": "grow", "merge": "merge", "split": "split"}
REJECT_WORDS = {
    "not_same_problem": "not the same problem",
    "too_broad": "too broad",
    "too_narrow": "too narrow",
    "wrong_cluster": "belongs with another group",
    "other": "other",
}


def render_cluster(
    cluster: dict[str, Any],
    members: list[str],
    credits: dict[str, str],
    *,
    history: list[HistoryRow],
    verified: list[dict[str, Any]],
    sections: dict[str, str] | None = None,
) -> str:
    """`sections` fills Evidence, Gates, Impact estimate and Preliminary review once qualify and scoring have run
    (§4.5 step 6, §4.6 step 10): counts, results and medians only."""
    extra = sections or {}
    """`credits` maps a member ref (M1…) to the contributor code that proposed that part of the fix."""
    summary: dict[str, Any] = cluster.get("summary") or {}
    retired = cluster.get("state") == "retired"
    meta: dict[str, Any] = {
        "type": "cluster",
        "title": cluster.get("title") or cluster["id"],
        "description": summary.get("description") or f"A group of {len(members)} ideas.",
        "tags": [lob.removeprefix("LOB-") for lob in cluster.get("lobs") or []],
        "status": "deprecated" if retired else "stable",
    }
    if verified:
        meta["verified"] = verified
    if cluster.get("generated_by"):
        meta["generated"] = {"by": cluster["generated_by"], "at": iso(cluster["updated_at"])}
    kfin: dict[str, Any] = {
        "id": cluster["id"],
        "stage": cluster["stage"],
        "members": members,
        "distinct_contributors": int(cluster.get("distinct_contributors") or 0),
        "lobs": list(cluster.get("lobs") or []),
        "scope": cluster.get("scope"),
        "route_to": cluster.get("route_to"),
        "visibility": "org",
    }
    if retired:
        kfin["merged_into"] = cluster.get("merged_into")
    meta["kfin"] = kfin

    variations = summary.get("variations") or []
    solution = summary.get("solution") or []
    questions = summary.get("open_questions") or []

    def who(refs: list[str]) -> str:
        return ", ".join(dict.fromkeys(credits.get(r, r) for r in refs))

    body = [
        "## Combined problem statement",
        esc(summary.get("problem")) or "Not written yet.",
        "",
        "## Variations raised",
        "\n".join(f"- {credits.get(v['member'], v['member'])}: {esc(v.get('note'))}" for v in variations)
        or "None beyond the combined statement.",
        "",
        "## Combined solution draft (with credit)",
        "\n".join(f"- {esc(p.get('text'))} (proposed by {who(p.get('credit') or [])})" for p in solution)
        or "No fix proposed yet.",
        "",
        "## Evidence",
        extra.get("Evidence", "Added when the group is qualified."),
        "",
        *(["## Gates", extra["Gates"], ""] if "Gates" in extra else []),
        "## Impact estimate",
        extra.get("Impact estimate", "Added when the group is qualified."),
        "",
        *(
            ["## Preliminary review", extra["Preliminary review"], ""]
            if "Preliminary review" in extra
            else []
        ),
        "## Open questions",
        "\n".join(f"- {esc(q)}" for q in questions) or "None recorded.",
        "",
        HISTORY_HEADING,
        "| When | Event | By | Note |",
        "|---|---|---|---|",
        *[f"| {r.when} | {r.event} | {r.by} | {r.note} |" for r in history],
        "",
    ]
    return dump(meta, "\n" + "\n".join(body))


def render_run(run: dict[str, Any], decisions: list[dict[str, Any]]) -> str:
    """`decisions`: one row per proposal of this run: kind, state, reject code (if any)."""
    counts: dict[str, Any] = run.get("counts") or {}
    params: dict[str, Any] = run.get("params") or {}
    by_kind = {k: sum(1 for d in decisions if d["kind"] == k) for k in KIND_WORDS}
    states = {
        s: sum(1 for d in decisions if d["state"] == s)
        for s in ("open", "approved", "rejected", "superseded")
    }
    codes: dict[str, int] = {}
    for d in decisions:
        if d.get("reject_code"):
            codes[d["reject_code"]] = codes.get(d["reject_code"], 0) + 1
    meta = {
        "type": "cluster-run",
        "title": f"Clustering run {run['id']}",
        "description": f"Weekly clustering run: {run.get('pool_size') or 0} ideas in the pool, {len(decisions)} proposals.",
        "tags": ["clustering"],
        "status": "stable",
        "generated": {"by": "process:cluster-batch", "at": iso(run["started_at"])},
        "kfin": {
            "id": run["id"],
            "state": run["state"],
            "pool_size": int(run.get("pool_size") or 0),
            "anchors": int(run.get("anchors") or 0),
            "params": {k: params[k] for k in sorted(params) if k != "manual_by"},
        },
    }
    rows = [
        "## Parameters",
        "| Setting | Value |",
        "|---|---|",
        *[f"| {cell(k)} | {cell(str(params[k]))} |" for k in sorted(params) if k != "manual_by"],
        "",
        "## Pool",
        f"- Ideas in the pool: {int(run.get('pool_size') or 0)}",
        f"- Approved groups used as anchors: {int(run.get('anchors') or 0)}",
        f"- Ideas not indexed yet (left out): {int(counts.get('unindexed') or 0)}",
        f"- Pairs found by the pair pass: {int(counts.get('pairs') or 0)}",
        f"- Members dropped by the outlier check: {int(counts.get('dropped') or 0)}",
        f"- Checks skipped because the assistant was unavailable: {int(counts.get('skipped_checks') or 0)}",
        "",
        "## Proposals by type",
        "| Type | Count |",
        "|---|---|",
        *[f"| {KIND_WORDS[k]} | {by_kind[k]} |" for k in KIND_WORDS],
        "",
        "## Decisions",
        "| Outcome | Count |",
        "|---|---|",
        *[f"| {s} | {n} |" for s, n in states.items()],
        "",
        "## Rejection reasons",
        "\n".join(f"- {REJECT_WORDS.get(c, c)}: {n}" for c, n in sorted(codes.items())) or "None.",
        "",
    ]
    return dump(meta, "\n" + "\n".join(rows))


def cluster_index_line(cluster_id: str, description: str) -> str:
    return f"* [{cluster_id}]({cluster_id}.md) - {cell(description)}"


def run_index_line(run_id: str, description: str) -> str:
    return f"* [{run_id}]({run_id}.md) - {cell(description)}"


__all__ = ["cluster_index_line", "render_cluster", "render_run", "run_index_line"]
