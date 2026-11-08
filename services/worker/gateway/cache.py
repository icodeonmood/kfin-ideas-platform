"""Gateway cache (§3.2 step 4): keyed by agent, version, model and the tagged inputs; values encrypted."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from core.crypto import CryptoError, decrypt_json, encrypt_json
from core.db import Conn
from gateway.spec import AgentSpec


def key(spec: AgentSpec, model: str, tagged_inputs: dict[str, Any]) -> bytes:
    material = json.dumps([spec.name, spec.version, model, tagged_inputs], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(material.encode()).digest()


def get(conn: Conn, k: bytes) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT output_encrypted FROM llm_cache WHERE key = %s AND expires_at > now()", (k,)
    ).fetchone()
    if row is None:
        return None
    try:
        value = decrypt_json(bytes(row["output_encrypted"]), k.hex())
    except CryptoError:
        return None  # a rotated key: treat as a miss
    return value if isinstance(value, dict) else None


def put(conn: Conn, k: bytes, spec: AgentSpec, output: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO llm_cache (key, agent, version, output_encrypted, expires_at) "
        "VALUES (%s, %s, %s, %s, now() + make_interval(days => %s)) "
        "ON CONFLICT (key) DO UPDATE SET output_encrypted = EXCLUDED.output_encrypted, "
        "expires_at = EXCLUDED.expires_at",
        (k, spec.name, spec.version, encrypt_json(output, k.hex()), spec.cache_ttl_days),
    )


def purge_expired(conn: Conn) -> int:
    return conn.execute("DELETE FROM llm_cache WHERE expires_at <= now()").rowcount
