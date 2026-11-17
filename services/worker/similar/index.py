"""One search chunk per shared idea, built from its database row (L-SIMILAR.rules/1, BLD-C091, DEC-106).

The chunk is what everyone may already see of the idea: its masked title and short summary (P-PRODUCT.privacy),
masked again here. Never the sharer's messages, answers or files. Shared ideas that are not withdrawn, and ideas
merged into others (a hit on one resolves to the surviving idea), are indexed; drafts and withdrawn ideas are not.
`sync` re-embeds only the ideas whose text changed, refreshes the stage and area of the rest, and drops chunks of
ideas that left. Before every match it reads only the ideas changed since their chunk was written, or with no chunk
yet (`full=False`); the indexer's loop sweeps every shared idea (`full=True`) and catches anything that slipped past
the timestamps (BLD-C098).
"""

from __future__ import annotations

import hashlib
from typing import Any

from core.db import Conn, vector_literal
from embeddings import embed
from similar.preview import mask_text

ELIGIBLE = "i.idea_id IS NOT NULL AND i.shared_at IS NOT NULL AND i.status NOT IN ('draft', 'withdrawn')"
BATCH = 32


def chunk_text(row: dict[str, Any]) -> str:
    """The masked title and short summary (the old ideas' neutral summary when the new column is empty)."""
    summary = row.get("summary") or row.get("neutral_summary")
    return "\n\n".join(t for t in (mask_text(row.get("title")).strip(), mask_text(summary).strip()) if t)


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sync(conn: Conn, *, full: bool = False) -> dict[str, int]:
    """Bring the idea chunks in line with the ideas table. Returns counts, never text.

    `full=False` (each match run): only ideas updated after their chunk, or with none. `full=True` (the indexer's
    loop): every shared idea. A row whose text is unchanged gets its stage and area refreshed and its chunk's time
    moved on, so it is not read again until the idea changes."""
    changed = "" if full else " AND (c.idea_uuid IS NULL OR i.updated_at > c.updated_at)"
    rows = conn.execute(
        "SELECT i.id, i.status, i.area, i.title, i.summary, i.canvas->>'neutral_summary' AS neutral_summary, "  # noqa: S608
        "c.idea_uuid AS chunk, c.text_hash, c.stage, c.area_ids, i.updated_at > c.updated_at AS behind "
        f"FROM ideas i LEFT JOIN chunks c ON c.idea_uuid = i.id WHERE {ELIGIBLE}{changed}"
    ).fetchall()
    stale: list[tuple[dict[str, Any], str]] = []
    empty: list[str] = []
    refreshed = 0
    for r in rows:
        text = chunk_text(dict(r))
        areas = [r["area"]] if r["area"] else []
        if not text:
            empty.append(str(r["id"]))
        elif r["text_hash"] != text_hash(text):
            stale.append((dict(r), text))
        elif r["behind"] or r["stage"] != r["status"] or list(r["area_ids"] or []) != areas:
            conn.execute(
                "UPDATE chunks SET stage = %s, area_ids = %s, updated_at = now() WHERE idea_uuid = %s",
                (r["status"], areas, r["id"]),
            )
            refreshed += 1
    for start in range(0, len(stale), BATCH):
        part = stale[start : start + BATCH]
        vectors = embed([text for _, text in part])
        for (r, text), vec in zip(part, vectors, strict=True):
            conn.execute(
                "INSERT INTO chunks (idea_uuid, file_type, section, ordinal, text, embedding, trust, stage, area_ids, "
                "visibility, text_hash) VALUES (%s, 'idea', 'card', 0, %s, %s::vector, 'unverified', %s, %s, 'org', %s) "
                "ON CONFLICT (idea_uuid) WHERE idea_uuid IS NOT NULL DO UPDATE SET text = EXCLUDED.text, "
                "embedding = EXCLUDED.embedding, stage = EXCLUDED.stage, area_ids = EXCLUDED.area_ids, "
                "text_hash = EXCLUDED.text_hash, updated_at = now()",
                (r["id"], text, vector_literal(vec), r["status"], [r["area"]] if r["area"] else [], text_hash(text)),
            )  # fmt: skip
    gone = conn.execute(
        "DELETE FROM chunks c WHERE c.idea_uuid IS NOT NULL AND (c.idea_uuid = ANY(%s::uuid[]) OR NOT EXISTS "  # noqa: S608
        f"(SELECT 1 FROM ideas i WHERE i.id = c.idea_uuid AND {ELIGIBLE}))",
        (empty,),
    ).rowcount
    return {"embedded": len(stale), "refreshed": refreshed, "removed": max(0, gone), "read": len(rows)}
