"""Week-3 file checks (§4.2 attachments steps 3, 4 and 6; D3), behind the `attachments.deep_check` switch.

- **Gatekeeper over file text.** After the pattern check passes, the file's text goes to `gatekeeper` in attachment
  mode, in pieces of about 2,000 tokens (spreadsheets: the first 200 rows of each sheet). It is tagged under a
  throwaway scope (`ATTCHK-…`) that is purged straight after, so only the verdict is kept. A span at the block
  threshold, or any investor-context tag, refuses the file with the location, never the value.
- **Digest.** Once a file is clean and its idea has been submitted, `attachment-digest` summarises it under the
  idea's own scope (so `[[CLIENT_AMC_1]]` means the same in the canvas and the file). The digest goes to the
  attachments row, the idea's canvas and, through the outbox, the idea file.
- **Index.** The file's text, tagged under the idea's scope, goes into `chunks` in pieces of about 800 tokens
  (`file_type = attachment`, trust `unverified`, the idea's visibility). File contents never go into Git.
"""

from __future__ import annotations

import re
from typing import Any

from psycopg.types.json import Jsonb

from attachments.extract import Extracted
from core.db import Conn, vector_literal
from core.logging import get_logger
from embeddings import embed
from gateway import AgentFailed, run_agent
from pii import vault
from pii.tagger import tag_payload
from rules import load_rule

log = get_logger("attachments.deep")
GATEKEEPER_PIECE_CHARS = 8_000  # about 2,000 tokens
INDEX_PIECE_CHARS = 3_200  # about 800 tokens
MAX_GATEKEEPER_CALLS = 40
SHEET_ROWS = 200
DIGEST_MAX_CHARS = 60_000
_ROW = re.compile(
    r"\brow (\d+)\b|\bcell [A-Z]{1,3}(\d+)\b"
)  # CSV and Word tables: "row 4"; sheets: "cell B4"


class Unavailable(Exception):
    """The gatekeeper could not run (switched off, budget, route down). The file waits or falls back."""


def _within_rows(location: str) -> bool:
    m = _ROW.search(location)
    return m is None or int(m.group(1) or m.group(2)) <= SHEET_ROWS


def batches(pieces: list[tuple[str, str]], limit: int) -> list[list[tuple[str, str]]]:
    """Consecutive pieces packed into batches of at most `limit` characters; a long piece is split."""
    out: list[list[tuple[str, str]]] = []
    current: list[tuple[str, str]] = []
    size = 0
    for location, text in pieces:
        parts = [text[i : i + limit] for i in range(0, len(text), limit)] or [""]
        for part in parts:
            if current and size + len(part) > limit:
                out.append(current)
                current, size = [], 0
            current.append((location, part))
            size += len(part)
    if current:
        out.append(current)
    return out


def gatekeeper_verdict(conn: Conn, att_id: str, extracted: Extracted) -> dict[str, str] | None:
    """The first blocking finding as {type, code, location}, or None when the text is clear. Raises Unavailable
    when the gatekeeper cannot run, and TooMuchText when the file is too long to check in full."""
    t = load_rule(_repo(), "thresholds").data["gatekeeper"]
    block_at = float(t["personal_data_block"])
    pieces = [(loc, text) for loc, text in extracted.pieces if text.strip() and _within_rows(loc)]
    groups = batches(pieces, GATEKEEPER_PIECE_CHARS)
    if len(groups) > MAX_GATEKEEPER_CALLS:
        return {
            "type": "too_big",
            "code": "too_big",
            "location": "the whole file",
        }  # too long to check in full
    scope = f"ATTCHK-{att_id}"
    try:
        for group in groups:
            # One key per piece, so a span's field names where it is; duplicate locations get a suffix.
            text: dict[str, str] = {}
            for loc, part in group:
                key = loc if loc not in text else f"{loc} ({len(text) + 1})"
                text[key] = part
            try:
                out = run_agent(
                    "gatekeeper", {"mode": "attachment", "attachment_text": text}, scope, conn=conn
                )
            except AgentFailed as exc:
                raise Unavailable(exc.code) from None
            spans = [s for s in out.data["personal_data"]["spans"] if float(s["confidence"]) >= block_at]
            if out.data["investor_context_tags"] or spans:
                where = str(spans[0]["field"]) if spans else next(iter(text))
                location = where if where in text else next(iter(text))
                return {"type": "personal data", "code": "gatekeeper", "location": location.split(" (")[0]}
        return None
    finally:
        vault.purge_scope(conn, scope)  # only the verdict is kept


def _repo() -> Any:
    from attachments.service import store_repo

    return store_repo()


def digest_and_index(
    conn: Conn, att: dict[str, Any], idea: dict[str, Any], extracted: Extracted, kind: str
) -> dict[str, Any]:
    """Digest (model) and index (no model) for one clean file of a submitted idea."""
    idea_id = str(idea["idea_id"])
    result: dict[str, Any] = {"digest": False, "indexed": 0}
    pieces = [(loc, text) for loc, text in extracted.pieces if text.strip()]
    sent: list[dict[str, str]] = []
    size = 0
    for loc, text in pieces:
        if size >= DIGEST_MAX_CHARS:
            break
        part = text[: DIGEST_MAX_CHARS - size]
        sent.append({"location": loc[:80], "text": part})
        size += len(part)
    try:
        out = run_agent(
            "attachment-digest",
            {"file": {"kind": kind.removesuffix("_ocr"), "ocr": kind.endswith("_ocr")}, "text": sent},
            idea_id,
            conn=conn,
        )
        conn.execute(
            "UPDATE attachments SET digest = %s, digest_meta = %s WHERE id = %s",
            (
                out.data["summary"],
                Jsonb({"claims": out.data["claims"], "kind_of_evidence": out.data["kind_of_evidence"],
                       "generated_by": f"attachment-digest/{out.version}"}),
                att["id"],
            ),
        )  # fmt: skip
        result["digest"] = True
    except AgentFailed as exc:
        log.warning("attachments.digest_unavailable", attachment_id=att["id"], error_code=exc.code)

    # The index: tagged text under the idea's scope, never raw. Replaces any earlier copy of this file.
    conn.execute("DELETE FROM chunks WHERE attachment_id = %s", (att["id"],))
    texts = [
        "\n".join(f"{loc}: {text}" for loc, text in group) for group in batches(pieces, INDEX_PIECE_CHARS)
    ]
    if texts:
        tagged = [str(tag_payload(conn, idea_id, {"t": t}).payload["t"]) for t in texts]
        vectors = embed(tagged)
        for n, (text, vec) in enumerate(zip(tagged, vectors, strict=True)):
            conn.execute(
                "INSERT INTO chunks (attachment_id, file_type, section, ordinal, text, embedding, trust, stage, lobs, "
                "category, area_ids, visibility) VALUES (%s, 'attachment', 'file', %s, %s, %s::vector, 'unverified', "
                "%s, %s, %s, %s, %s)",
                (
                    att["id"], n, text, vector_literal(vec), idea["stage"], list(idea["lobs"] or []),
                    idea["category"], list(idea["area_ids"] or []), idea["visibility"],
                ),
            )  # fmt: skip
        result["indexed"] = len(texts)
    conn.execute("UPDATE attachments SET indexed_at = now() WHERE id = %s", (att["id"],))
    _into_canvas(conn, att["id"], idea)
    return result


def _into_canvas(conn: Conn, att_id: str, idea: dict[str, Any]) -> None:
    """The idea's canvas lists its research files with their digests; the repo writer rewrites the idea file."""
    row = conn.execute(
        "SELECT name, state, digest, sha256, bytes FROM attachments WHERE id = %s", (att_id,)
    ).fetchone()
    if row is None or idea.get("canvas") is None:
        return
    canvas = dict(idea["canvas"])
    entries = [dict(a) for a in canvas.get("attachments") or []]
    entry = {"id": att_id, "name": row["name"], "state": row["state"], "digest": row["digest"],
             "sha256": row["sha256"], "bytes": row["bytes"]}  # fmt: skip
    for i, a in enumerate(entries):
        if a.get("id") == att_id:
            entries[i] = {**a, **entry}
            break
    else:
        entries.append(entry)
    canvas["attachments"] = entries
    conn.execute("UPDATE ideas SET canvas = %s WHERE idea_id = %s", (Jsonb(canvas), idea["idea_id"]))
    if idea["stage"] not in ("draft", "scanning", "blocked"):
        conn.execute(
            "INSERT INTO outbox (event_type, aggregate_id, actor, payload) VALUES ('idea.updated', %s, %s, %s)",
            (idea["idea_id"], "process:attachment-digest",
             Jsonb({"idea_id": idea["idea_id"], "history": [{"event": "research_digest", "note": att_id}]})),
        )  # fmt: skip
