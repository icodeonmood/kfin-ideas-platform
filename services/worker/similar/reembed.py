"""python -m similar.reembed [--dry-run]   Rebuild every stored vector with the configured embedder (L-SIMILAR,
BLD-080, BLD-C210).

Run it in a one-off container while the worker service is stopped, so matching never sees mixed vectors. When a
server moves from EMBEDDINGS_MODE=hash to bge-m3, the vectors already stored were made by the old model; mixing
them with new ones makes matching meaningless, with no error. This command rebuilds all three kinds, from text the
database already holds:

- `chunks.embedding`: every chunk (company-repo, idea and file chunks alike) is re-embedded from its own stored
  `text`, which is exactly what its writer embedded (index/indexer.py, similar/index.py, attachments/deep.py).
  Only the vector changes: `text_hash`, `stage`, `area_ids` and `updated_at` stay, so `similar.index.sync` sees no
  change. The git indexer is not called, so no company repo is needed. A chunk with no text is left and counted.
- `corrections.card_embedding`: the card the review desk embedded is reached through the correction's review item
  and its idea (review/service.py `_card_text`: the confirmed card's one line and details, tagged values only) and
  re-embedded masked again, as the idea chunk is (`similar.preview.mask_text`). Raw or unmasked words are never
  embedded. A correction whose card cannot be reached is cleared to NULL; `corrections_for` skips NULL.
- `clusters.centroid`: recomputed with the cluster code's own member lookup and normalised mean
  (cluster/proposals.py `_members_of` and `_vectors`, cluster/linkage.py `centroid`), from the members' new vectors.
  A cluster with no member vector is cleared to NULL, as `_refresh_cluster` does; every reader skips NULL.

The embedder is loaded and tried on one synthetic sentence before any row is read; if it fails, nothing changes.
Batches of 32 commit as they go, so a stopped run is simply run again: every row is re-done. Output, logs and the
one `audit_log` row (`embeddings.rebuilt`, non-negotiable 9) carry the mode and counts only, never text.
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from psycopg.types.json import Jsonb

import embeddings
from cluster.linkage import centroid
from cluster.proposals import _members_of, _vectors
from core.config import get_settings
from core.db import Conn, connect, vector_literal
from core.logging import get_logger
from review.service import _card_text
from similar.preview import mask_text

log = get_logger("similar.reembed")
BATCH = 32
ACTOR = "process:reembed"
ENTITY = "embeddings"
PROBE = "SIP registrations slip by a day because every form is re-checked by hand."  # synthetic, never a card
HELP = (
    "Rebuild every stored vector (search chunks, the review desk's corrections, cluster centroids) with the "
    "configured EMBEDDINGS_MODE, for example after moving a server from hash to bge-m3. Run it in a one-off "
    "container while the worker service is stopped, so matching never sees mixed vectors. It checks the embedder "
    "loads before it reads any row, and changes nothing if it does not. A stopped run is simply run again."
)


@dataclass
class Counts:
    chunks_repo: int = 0
    chunks_idea: int = 0
    chunks_file: int = 0
    chunks_skipped: int = 0
    corrections_reembedded: int = 0
    corrections_cleared: int = 0
    centroids_recomputed: int = 0
    centroids_cleared: int = 0


class EmbedderNotReady(RuntimeError):
    """The configured embedder did not load, or gave something other than one 1,024-dimension vector."""


def preflight() -> None:
    """Load the configured embedder and embed one synthetic sentence; raise EmbedderNotReady if that fails."""
    try:
        vectors = embeddings.embed([PROBE])
    except Exception as exc:  # no WITH_BGE library, EMBEDDINGS_MODEL_PATH unset, files missing, unknown mode
        raise EmbedderNotReady(f"{type(exc).__name__}: {exc}") from exc
    if (
        len(vectors) != 1
        or len(vectors[0]) != embeddings.DIMENSIONS
        or not all(math.isfinite(x) for x in vectors[0])
    ):
        raise EmbedderNotReady(f"the embedder did not return one {embeddings.DIMENSIONS}-dimension vector")


def _kind(row: dict[str, Any]) -> str:
    """repo: a company-repo file; file: an attachment; idea: a shared idea's row (chunks_one_source)."""
    if row["idea_uuid"] is not None:
        return "idea"
    return "file" if row["attachment_id"] is not None else "repo"


def _chunks(conn: Conn, counts: Counts, dry_run: bool) -> None:
    last = 0
    while rows := conn.execute(
        "SELECT id, text, repo_path, attachment_id, idea_uuid FROM chunks WHERE id > %s ORDER BY id LIMIT %s",
        (last, BATCH),
    ).fetchall():
        last = int(rows[-1]["id"])
        todo = [r for r in rows if (r["text"] or "").strip()]
        if todo and not dry_run:
            vectors = embeddings.embed([r["text"] for r in todo])
            with conn.transaction():
                for r, vec in zip(todo, vectors, strict=True):
                    conn.execute(
                        "UPDATE chunks SET embedding = %s::vector WHERE id = %s",
                        (vector_literal(vec), r["id"]),
                    )
        counts.chunks_skipped += len(rows) - len(todo)
        for r in todo:
            kind = _kind(r)
            setattr(counts, f"chunks_{kind}", getattr(counts, f"chunks_{kind}") + 1)


def card_text(canvas: Any) -> str:
    """The text the review desk embedded for a correction, masked again. Empty when the card cannot be reached."""
    if not isinstance(canvas, dict):
        return ""
    return mask_text(_card_text({"canvas": canvas})).strip()


def _corrections(conn: Conn, counts: Counts, dry_run: bool) -> None:
    last = 0
    while rows := conn.execute(
        "SELECT c.id, i.canvas FROM corrections c JOIN review_items r ON r.id = c.review_item_id "
        "LEFT JOIN ideas i ON r.item_type = 'idea' AND i.idea_id = r.ref_id "
        "WHERE c.id > %s ORDER BY c.id LIMIT %s",
        (last, BATCH),
    ).fetchall():
        last = int(rows[-1]["id"])
        texts = [(int(r["id"]), card_text(r["canvas"])) for r in rows]
        reached = [(cid, text) for cid, text in texts if text]
        gone = [cid for cid, text in texts if not text]
        if not dry_run:
            vectors = embeddings.embed([text for _, text in reached]) if reached else []
            with conn.transaction():
                for (cid, _), vec in zip(reached, vectors, strict=True):
                    conn.execute(
                        "UPDATE corrections SET card_embedding = %s::vector WHERE id = %s",
                        (vector_literal(vec), cid),
                    )
                if gone:
                    conn.execute(
                        "UPDATE corrections SET card_embedding = NULL WHERE id = ANY(%s) AND card_embedding IS NOT NULL",
                        (gone,),
                    )
        counts.corrections_reembedded += len(reached)
        counts.corrections_cleared += len(gone)


def _centroids(conn: Conn, counts: Counts, dry_run: bool) -> None:
    ids = [str(r["id"]) for r in conn.execute("SELECT id FROM clusters ORDER BY id").fetchall()]
    for start in range(0, len(ids), BATCH):
        part: list[tuple[str, list[float] | None]] = []
        for cid in ids[start : start + BATCH]:
            vecs = _vectors(conn, _members_of(conn, [cid]))
            part.append((cid, centroid(np.asarray(vecs, dtype=np.float64)).tolist() if vecs else None))
        if not dry_run:
            with conn.transaction():
                for cid, cen in part:
                    if cen is None:
                        conn.execute(
                            "UPDATE clusters SET centroid = NULL WHERE id = %s AND centroid IS NOT NULL",
                            (cid,),
                        )
                    else:
                        conn.execute(
                            "UPDATE clusters SET centroid = %s::vector WHERE id = %s",
                            (vector_literal(cen), cid),
                        )
        counts.centroids_recomputed += sum(1 for _, cen in part if cen is not None)
        counts.centroids_cleared += sum(1 for _, cen in part if cen is None)


def _audit(conn: Conn, action: str, after: dict[str, Any]) -> None:
    with conn.transaction():
        conn.execute(
            "INSERT INTO audit_log (actor, action, entity, after) VALUES (%s, %s, %s, %s)",
            (ACTOR, action, ENTITY, Jsonb(after)),
        )


def run(conn: Conn, *, dry_run: bool = False) -> Counts:
    """Rebuild (or, with `dry_run`, count) every stored vector. `conn` must be in autocommit mode: each batch
    commits in its own transaction. Call `preflight()` first. A real run writes one audit_log row when it finishes,
    or `embeddings.rebuild_stopped` with the counts so far if it stops; a dry run writes nothing."""
    mode = get_settings().embeddings_mode
    counts = Counts()
    try:
        _chunks(conn, counts, dry_run)
        _corrections(conn, counts, dry_run)
        _centroids(conn, counts, dry_run)
    except Exception as exc:
        log.error("embeddings.rebuild_stopped", mode=mode, error_type=type(exc).__name__, **asdict(counts))
        if not dry_run:
            try:
                _audit(
                    conn,
                    "embeddings.rebuild_stopped",
                    {"mode": mode, "error_type": type(exc).__name__, **asdict(counts)},
                )
            except Exception as again:
                log.error("embeddings.audit_failed", error_type=type(again).__name__)
        raise
    if dry_run:
        log.info("embeddings.rebuild_planned", mode=mode, **asdict(counts))
    else:
        _audit(conn, "embeddings.rebuilt", {"mode": mode, **asdict(counts)})
        log.info("embeddings.rebuilt", mode=mode, **asdict(counts))
    return counts


def report(counts: Counts, mode: str, *, dry_run: bool) -> str:
    c = counts
    lines = [
        f"EMBEDDINGS_MODE={mode}"
        + (" · dry run: nothing was changed; these are the rows it would change" if dry_run else ""),
        f"chunks re-embedded: repo {c.chunks_repo}, idea {c.chunks_idea}, file {c.chunks_file}"
        f" · skipped (no text): {c.chunks_skipped}",
        f"corrections re-embedded: {c.corrections_reembedded}"
        f" · cleared (card not reachable): {c.corrections_cleared}",
        f"centroids recomputed: {c.centroids_recomputed} · cleared (no member vectors): {c.centroids_cleared}",
    ]
    if not dry_run:
        lines.append("audit_log: one embeddings.rebuilt row written")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m similar.reembed", description=HELP)
    parser.add_argument(
        "--dry-run", action="store_true", help="print the counts it would change; change nothing"
    )
    args = parser.parse_args(argv)
    mode = get_settings().embeddings_mode
    try:
        preflight()
    except EmbedderNotReady as exc:
        log.error("embeddings.rebuild_refused", mode=mode, error_type=type(exc.__cause__ or exc).__name__)
        print(
            f"EMBEDDINGS_MODE={mode}: the embedder did not load ({exc}). Nothing was changed.",
            file=sys.stderr,
        )
        return 1
    conn = connect(autocommit=True)
    try:
        counts = run(conn, dry_run=args.dry_run)
    except Exception as exc:
        print(
            f"EMBEDDINGS_MODE={mode}: stopped ({type(exc).__name__}). The batches done so far are kept; "
            "run the command again to redo every row.",
            file=sys.stderr,
        )
        return 1
    finally:
        conn.close()
    print(report(counts, mode, dry_run=args.dry_run))
    return 0


if __name__ == "__main__":
    sys.exit(main())
