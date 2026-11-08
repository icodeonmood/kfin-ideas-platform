"""The worker opens what the web app seals (drafts and submitted text), and vice versa: one shared vector."""

from typing import Any

import pytest

from core import crypto

VECTOR = bytes.fromhex(
    "01000102030405060708090a0b076facb600f662c34d073089a2d0f0976a161c3c1fd2c6c1df6e276d9679ce3bd4384df6689c769b8af50708bdb7eecadf5f54722a3c19d698"
)


def test_python_opens_the_web_vector(monkeypatch: Any) -> None:
    monkeypatch.setattr(crypto, "_raw_key", lambda kind="data": "vector-key-for-tests-only-0001")
    assert crypto.decrypt_json(VECTOR, "ROW-VECTOR-1") == {"details": "Synthetic vector text", "n": 1}
    with pytest.raises(crypto.CryptoError):
        crypto.decrypt_json(VECTOR, "ROW-VECTOR-2")
    sealed = crypto.encrypt_json({"x": 1}, "ctx")
    assert sealed[0] == 1 and len(sealed) > 29
    assert crypto.decrypt_json(sealed, "ctx") == {"x": 1}


def test_the_vault_has_its_own_worker_only_key(monkeypatch: Any) -> None:
    """BLD-098: vault values and lookup hashes use PSEUDONYM_VAULT_KEY; the shared key cannot open them."""
    from core.config import Settings

    shared, own = "s" * 40, "v" * 40
    monkeypatch.setattr(
        crypto, "get_settings", lambda: Settings(vault_encryption_key=shared, pseudonym_vault_key=own)
    )
    sealed = crypto.encrypt_bytes(b"Meera Iyer", "IDEA-2026-000001|[[KFIN_EMPLOYEE_1]]", kind="vault")
    assert crypto.decrypt_bytes(sealed, "IDEA-2026-000001|[[KFIN_EMPLOYEE_1]]", kind="vault") == b"Meera Iyer"
    with pytest.raises(crypto.CryptoError):
        crypto.decrypt_bytes(sealed, "IDEA-2026-000001|[[KFIN_EMPLOYEE_1]]")  # the web app's key
    vault_hash = crypto.keyed_hash("vault", "KFIN_EMPLOYEE:meera iyer")
    other_hash = crypto.keyed_hash("crew-ref", "KFIN_EMPLOYEE:meera iyer")

    monkeypatch.setattr(
        crypto, "get_settings", lambda: Settings(vault_encryption_key=shared, pseudonym_vault_key="")
    )
    assert (
        crypto.keyed_hash("vault", "KFIN_EMPLOYEE:meera iyer") != vault_hash
    )  # lookups depend on the vault key
    assert crypto.keyed_hash("crew-ref", "KFIN_EMPLOYEE:meera iyer") == other_hash  # nothing else changes

    monkeypatch.setattr(
        crypto,
        "get_settings",
        lambda: Settings(app_env="uat", vault_encryption_key=shared, pseudonym_vault_key=""),
    )  # outside dev, no vault without its own key
    with pytest.raises(crypto.CryptoError):
        crypto.encrypt_bytes(b"x", "ctx", kind="vault")
    assert crypto.decrypt_bytes(crypto.encrypt_bytes(b"x", "ctx"), "ctx") == b"x"  # drafts still work
