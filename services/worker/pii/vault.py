"""The pseudonym vault (ARCHITECTURE §3.2 steps 1 and 8): tag ↔ real value, per idea or cluster.

Values are encrypted (AES-256-GCM, bound to scope and tag) and looked up by a keyed hash, so the same value
always gets the same tag within a scope, across every call. Only the gateway's tagger and restore service use
this module. Tag numbers are allocated per type under a per-scope advisory lock.
"""

from __future__ import annotations

import re

from core.crypto import decrypt_bytes, encrypt_bytes, keyed_hash
from core.db import Conn

SCOPE_RE = re.compile(r"^(IDEA-[0-9]{4}-[0-9]{6}|CL-[0-9]{4}|DRAFT-[0-9a-f-]{36})$")
IDENTIFIER_TYPES = {
    "PAN", "AADHAAR", "PHONE", "ACCOUNT_NUMBER", "CARD_NUMBER", "FOLIO_NUMBER", "DEMAT_ACCOUNT", "PRAN",
    "IFSC", "ARN", "EUIN", "CONTRIBUTOR", "REVIEWER",
}  # fmt: skip


def normalise(type_: str, value: str) -> str:
    if type_ == "EMAIL":
        return value.strip().lower()
    if type_ in IDENTIFIER_TYPES:
        return re.sub(r"[\s-]", "", value).upper()
    return " ".join(value.split()).casefold()


def assign(conn: Conn, scope_id: str, type_: str, value: str, subject_user_id: str | None = None) -> str:
    """The tag for `value` in this scope, creating it on first sight."""
    if not SCOPE_RE.match(scope_id):
        raise ValueError("bad_scope")
    digest = keyed_hash("vault", f"{type_}:{normalise(type_, value)}")
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (scope_id,))
        row = conn.execute(
            "SELECT tag FROM pseudonym_vault WHERE scope_id = %s AND value_hmac = %s", (scope_id, digest)
        ).fetchone()
        if row:
            return str(row["tag"])
        n = conn.execute(
            "INSERT INTO vault_counters (scope_id, type, last) VALUES (%s, %s, 1) "
            "ON CONFLICT (scope_id, type) DO UPDATE SET last = vault_counters.last + 1 RETURNING last",
            (scope_id, type_),
        ).fetchone()
        assert n is not None
        tag = f"[[{type_}_{int(n['last'])}]]"  # never reused, even after a row is erased (BLD-081)
        conn.execute(
            "INSERT INTO pseudonym_vault (scope_id, tag, type, value_hmac, value_encrypted, subject_user_id) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (
                scope_id,
                tag,
                type_,
                digest,
                encrypt_bytes(value.encode(), f"{scope_id}|{tag}"),
                subject_user_id,
            ),
        )
    return tag


def known_tags(conn: Conn, scope_id: str) -> dict[str, str]:
    """Tag -> type for a scope, without opening any value (for the tag check)."""
    rows = conn.execute("SELECT tag, type FROM pseudonym_vault WHERE scope_id = %s", (scope_id,)).fetchall()
    return {str(r["tag"]): str(r["type"]) for r in rows}


def mapping(conn: Conn, scope_id: str) -> dict[str, tuple[str, str]]:
    """Tag -> (type, real value). Restore service only."""
    rows = conn.execute(
        "SELECT tag, type, value_encrypted FROM pseudonym_vault WHERE scope_id = %s", (scope_id,)
    ).fetchall()
    return {
        str(r["tag"]): (
            str(r["type"]),
            decrypt_bytes(bytes(r["value_encrypted"]), f"{scope_id}|{r['tag']}").decode(),
        )
        for r in rows
    }


def purge_scope(conn: Conn, scope_id: str) -> int:
    """Remove every value held for a scope (an idea sent back to edit after a block: BLD-081). Counters stay."""
    return conn.execute("DELETE FROM pseudonym_vault WHERE scope_id = %s", (scope_id,)).rowcount
