"""P6 `corrections_for`: what reviewers corrected in similar cases (§5.1). The five nearest past corrections
by the original card's embedding, optionally for one field, become examples for canvas assist or the judge."""

from __future__ import annotations

from typing import Any

from core.db import Conn, vector_literal


def corrections_for(
    conn: Conn, card_vector: list[float], field: str | None = None, k: int = 5
) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT field, proposed, final, note FROM corrections "
        "WHERE card_embedding IS NOT NULL AND (%s::text IS NULL OR field = %s) "
        "ORDER BY card_embedding <=> %s::vector LIMIT %s",
        (field, field, vector_literal(card_vector), k),
    ).fetchall()
    return [
        {"field": r["field"], "proposed": r["proposed"], "final": r["final"], "note": r["note"]} for r in rows
    ]
