"""Column encryption shared with the web app (apps/web/src/server/crypto.ts).

AES-256-GCM. Layout: [0x01 version][12-byte IV][16-byte tag][ciphertext]. The context string (a row ID, or
scope and tag for the vault) is bound in as associated data, so a ciphertext copied elsewhere fails to open.
Key: SHA-256 of VAULT_ENCRYPTION_KEY. A cross-language vector keeps both sides identical.

The pseudonym vault (`kind="vault"`: its values and its lookup hashes) uses PSEUDONYM_VAULT_KEY when set, a key
only the worker holds (B8 hardening, BLD-098). UAT and prod must set it; dev falls back to the shared key.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Any, Literal

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from core.config import get_settings

VERSION = 0x01


class CryptoError(Exception):
    """A ciphertext would not open (wrong key, wrong context or tampering). Carries no data."""


Kind = Literal["data", "vault"]


def _raw_key(kind: Kind = "data") -> str:
    s = get_settings()
    raw = s.pseudonym_vault_key if kind == "vault" and s.pseudonym_vault_key else s.vault_encryption_key
    if not raw:
        raise CryptoError("key_missing")
    if s.is_production_like and (raw.startswith("change-me") or len(raw) < 32):
        raise CryptoError("key_placeholder")
    if s.is_production_like and kind == "vault" and not s.pseudonym_vault_key:
        raise CryptoError("vault_key_missing")  # outside dev the vault never shares the web app's key
    return raw


def _key(kind: Kind = "data") -> bytes:
    return hashlib.sha256(_raw_key(kind).encode()).digest()


def encrypt_bytes(plain: bytes, context: str, kind: Kind = "data") -> bytes:
    iv = os.urandom(12)
    sealed = AESGCM(_key(kind)).encrypt(iv, plain, context.encode())  # ciphertext || tag
    return bytes([VERSION]) + iv + sealed[-16:] + sealed[:-16]


def decrypt_bytes(blob: bytes, context: str, kind: Kind = "data") -> bytes:
    if len(blob) < 29 or blob[0] != VERSION:
        raise CryptoError("format")
    iv, tag, body = blob[1:13], blob[13:29], blob[29:]
    try:
        return AESGCM(_key(kind)).decrypt(iv, body + tag, context.encode())
    except Exception:
        raise CryptoError("open_failed") from None


def encrypt_json(value: Any, context: str) -> bytes:
    return encrypt_bytes(json.dumps(value, ensure_ascii=False).encode(), context)


def decrypt_json(blob: bytes, context: str) -> Any:
    return json.loads(decrypt_bytes(blob, context))


def keyed_hash(purpose: str, value: str) -> bytes:
    """HMAC-SHA256 under a key derived from the vault key, for lookups without storing the value."""
    kind: Kind = "vault" if purpose == "vault" else "data"
    k = hashlib.sha256(b"kfin-ideas:" + purpose.encode() + b":" + _raw_key(kind).encode()).digest()
    return hmac.new(k, value.encode(), hashlib.sha256).digest()
