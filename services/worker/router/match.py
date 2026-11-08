"""P3 `match` (ARCHITECTURE §3.3): has this problem been raised, solved or declined before?

1. Graph: the card's glossary IDs (P2) → files that reference them → one more hop, in either direction.
2. Meaning: cosine over `chunks` (ideas, clusters, solutions, decisions), top 50 above the floor.
3. Keyword: `websearch_to_tsquery('simple', …)` over `tsv`, top 50.
4. Reciprocal rank fusion (k = 60); graph results rank 1 in their own list.
5. Trust boost (human 1.15, machine 1.0, unverified 0.9).
6. At least 3 solution and 3 decision slots when any exist above the cosine floor.
7. Cut to 20. Committee-only files stay in the reviewer's list; the submitter's list shows them as a placeholder
   with nothing but the fact that a related idea is with the review desk (§4.2 step 7, AT-B5-03).
All numbers come from `rules/thresholds.md` (`match`, `trust_boost`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from core.config import get_settings
from core.db import Conn, vector_literal
from embeddings import embed
from rules import load_rule

CARD_TYPES = ("idea", "cluster", "solution", "decision")
STOP = frozenset(
    ["the", "and", "for", "are", "but", "not", "you", "all", "any", "can", "had", "her", "was", "one", "our", "out", "has", "have", "this", "that", "with", "from", "they", "will", "what", "when", "your", "into", "than", "then", "them", "were", "been", "more", "some", "such", "only", "also", "very", "just", "over", "each", "about", "which", "would", "could", "should", "there", "their", "these", "those", "because", "every"]
)  # fmt: skip


@dataclass
class Candidate:
    repo_path: str
    kfin_id: str | None
    file_type: str
    stage: str | None
    visibility: str
    trust: str
    summary: str | None
    area_ids: list[str]
    lobs: list[str]
    score: float = 0.0
    cosine: float | None = None
    via: list[str] = field(default_factory=list)
    text: str = ""  # the trimmed chunk text, for the judge only (tagged); never shown to submitters

    @property
    def declined(self) -> bool:
        return self.file_type == "decision"


def _settings() -> tuple[dict[str, Any], dict[str, float]]:
    data = load_rule(get_settings().company_repo_path, "thresholds").data
    return dict(data["match"]), {k: float(v) for k, v in (data.get("trust_boost") or {}).items()}


def _graph(conn: Conn, gl_ids: list[str]) -> list[str]:
    if not gl_ids:
        return []
    paths = [
        r["repo_path"]
        for r in conn.execute(
            "SELECT DISTINCT repo_path FROM terms WHERE glossary_id = ANY(%s)", (gl_ids,)
        ).fetchall()
    ]
    targets = [f"id:{g}" for g in gl_ids] + paths
    hop1 = {
        r["from_path"]
        for r in conn.execute("SELECT from_path FROM links WHERE to_path = ANY(%s)", (targets,)).fetchall()
    }
    if not hop1:
        return []
    ids = [
        r["kfin_id"]
        for r in conn.execute(
            "SELECT kfin_id FROM repo_files WHERE repo_path = ANY(%s) AND kfin_id IS NOT NULL", (list(hop1),)
        ).fetchall()
    ]
    back = [f"id:{i}" for i in ids] + list(hop1)
    hop2 = {
        r["from_path"]
        for r in conn.execute("SELECT from_path FROM links WHERE to_path = ANY(%s)", (back,)).fetchall()
    }
    forward_ids = [
        r["to_path"].removeprefix("id:")
        for r in conn.execute(
            "SELECT to_path FROM links WHERE from_path = ANY(%s) AND to_path LIKE 'id:%%'", (list(hop1),)
        ).fetchall()
    ]
    forward = {
        r["repo_path"]
        for r in conn.execute(
            "SELECT repo_path FROM repo_files WHERE kfin_id = ANY(%s)", (forward_ids,)
        ).fetchall()
    }
    return sorted(hop1 | hop2 | forward)


def _keyword_query(text: str) -> str:
    text = re.sub(r"\[\s?\[[A-Z_]+_[0-9]+\]\s?\]", " ", text)  # tags carry no topic words
    words = [w for w in dict.fromkeys(re.findall(r"[A-Za-z][A-Za-z0-9]{2,}", text.lower())) if w not in STOP]
    return " or ".join(words[:40])


def match(
    conn: Conn,
    card_text: str,
    gl_ids: list[str],
    *,
    exclude_ids: tuple[str, ...] = (),
    card_vector: list[float] | None = None,
) -> list[Candidate]:
    """Up to `final_k` candidates for the reviewer's view, best first. Use `for_submitter` for the other view."""
    m, boost = _settings()
    floor, top_k, final_k, rrf_k = (
        float(m["cosine_floor"]),
        int(m["top_k_each"]),
        int(m["final_k"]),
        int(m["rrf_k"]),
    )
    vec = card_vector or embed([card_text])[0]
    excluded = [i for i in exclude_ids if i]

    graph = [p for p in _graph(conn, gl_ids)]
    # HNSW returns at most `ef_search` rows before the file-type filter; widen it and let pgvector keep
    # scanning until enough rows pass the filter (iterative scan, pgvector 0.8).
    with conn.transaction():
        conn.execute("SET LOCAL hnsw.ef_search = 400")
        conn.execute("SET LOCAL hnsw.iterative_scan = relaxed_order")
        vector_rows = conn.execute(
            "SELECT repo_path, 1 - (embedding <=> %s::vector) AS cos FROM chunks "
            "WHERE file_type = ANY(%s) AND repo_path IS NOT NULL ORDER BY embedding <=> %s::vector LIMIT %s",
            (vector_literal(vec), list(CARD_TYPES), vector_literal(vec), top_k * 4),
        ).fetchall()
    best_cos: dict[str, float] = {}
    for r in vector_rows:
        best_cos[r["repo_path"]] = max(best_cos.get(r["repo_path"], -1.0), float(r["cos"]))
    vector = [p for p, c in sorted(best_cos.items(), key=lambda kv: -kv[1]) if c >= floor][:top_k]
    query = _keyword_query(card_text)
    keyword = (
        [
            r["repo_path"]
            for r in conn.execute(
                "SELECT repo_path, max(ts_rank_cd(tsv, q)) AS rank FROM chunks, websearch_to_tsquery('simple', %s) q "
                "WHERE file_type = ANY(%s) AND repo_path IS NOT NULL AND tsv @@ q GROUP BY repo_path "
                "ORDER BY rank DESC LIMIT %s",
                (query, list(CARD_TYPES), top_k),
            ).fetchall()
        ]
        if query
        else []
    )

    scores: dict[str, float] = {}
    via: dict[str, list[str]] = {}
    for name, ranked, graph_list in (
        ("graph", graph, True),
        ("vector", vector, False),
        ("keyword", keyword, False),
    ):
        for rank, path in enumerate(ranked, start=1):
            scores[path] = scores.get(path, 0.0) + 1.0 / (rrf_k + (1 if graph_list else rank))
            via.setdefault(path, []).append(name)
    if not scores:
        return []
    rows = conn.execute(
        "SELECT f.repo_path, f.kfin_id, f.file_type, f.stage, f.visibility, f.trust, f.summary, f.area_ids, f.lobs, "
        "(SELECT text FROM chunks c WHERE c.repo_path = f.repo_path ORDER BY ordinal LIMIT 1) AS text "
        "FROM repo_files f WHERE f.repo_path = ANY(%s) AND f.file_type = ANY(%s)",
        (list(scores), list(CARD_TYPES)),
    ).fetchall()
    found = []
    for r in rows:
        if r["kfin_id"] in excluded:
            continue
        c = Candidate(
            repo_path=r["repo_path"], kfin_id=r["kfin_id"], file_type=r["file_type"], stage=r["stage"],
            visibility=r["visibility"], trust=r["trust"], summary=r["summary"], area_ids=list(r["area_ids"] or []),
            lobs=list(r["lobs"] or []), cosine=best_cos.get(r["repo_path"]), via=via[r["repo_path"]],
            text=(r["text"] or "")[:800],
        )  # fmt: skip
        c.score = scores[r["repo_path"]] * boost.get(c.trust, 1.0)
        found.append(c)
    found.sort(key=lambda c: (-c.score, c.repo_path))

    # Keep "solved" and "declined" visible: reserve slots for them when any clear the cosine floor.
    def reserved(kind: str, n: int) -> list[Candidate]:
        return [c for c in found if c.file_type == kind and (c.cosine or 0) >= floor][:n]

    keep = reserved("solution", int(m["reserve_solved"])) + reserved("decision", int(m["reserve_declined"]))
    for c in found:
        if len(keep) >= final_k:
            break
        if c not in keep:
            keep.append(c)
    keep.sort(key=lambda c: (-c.score, c.repo_path))
    return keep[:final_k]


Shown = Literal["card", "with_desk"]


def for_submitter(candidates: list[Candidate]) -> list[tuple[Shown, Candidate]]:
    """The submitter's list: committee-only files become a placeholder ("a related idea is with the review
    desk") carrying nothing from the file."""
    return [("with_desk" if c.visibility == "committee" else "card", c) for c in candidates]
