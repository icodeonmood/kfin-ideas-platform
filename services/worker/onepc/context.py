"""Sealing for the `*_encrypted` columns added by the handoff cut-over (BLD-E006), shared with
`apps/web/src/lib/contracts/crypto-context.ts`: the payload is `{"text": …}` (core.crypto's JSON layout) and the
associated data is "<table>.<column>:<row id>", so a value written by one side opens on the other.

`idea_words_sealed.text_encrypted` (the sharer's unmasked words, DEC-103) is the worker's alone and is sealed with
the vault key (`vault=True`), which the web app never holds outside dev.
"""

from __future__ import annotations

import json

from core.crypto import CryptoError, decrypt_bytes, encrypt_bytes


def sealed_context(table: str, column: str, row_id: str | int) -> str:
    return f"{table}.{column}:{row_id}"


def seal_text(table: str, column: str, row_id: str | int, text: str, *, vault: bool = False) -> bytes:
    payload = json.dumps({"text": text}, ensure_ascii=False).encode()
    return encrypt_bytes(payload, sealed_context(table, column, row_id), "vault" if vault else "data")


def open_text(
    table: str, column: str, row_id: str | int, blob: bytes | memoryview | None, *, vault: bool = False
) -> str | None:
    """The text, or None when there is none or it will not open (wrong key, context or tampering)."""
    if blob is None:
        return None
    try:
        raw = decrypt_bytes(bytes(blob), sealed_context(table, column, row_id), "vault" if vault else "data")
    except CryptoError:
        return None
    text = json.loads(raw).get("text")
    return text if isinstance(text, str) else None
