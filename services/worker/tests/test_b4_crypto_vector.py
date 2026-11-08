"""The worker opens what the web app seals (drafts and submitted text), and vice versa: one shared vector."""

from typing import Any

import pytest

from core import crypto

VECTOR = bytes.fromhex(
    "01000102030405060708090a0b076facb600f662c34d073089a2d0f0976a161c3c1fd2c6c1df6e276d9679ce3bd4384df6689c769b8af50708bdb7eecadf5f54722a3c19d698"
)


def test_python_opens_the_web_vector(monkeypatch: Any) -> None:
    monkeypatch.setattr(crypto, "_raw_key", lambda: "vector-key-for-tests-only-0001")
    assert crypto.decrypt_json(VECTOR, "ROW-VECTOR-1") == {"details": "Synthetic vector text", "n": 1}
    with pytest.raises(crypto.CryptoError):
        crypto.decrypt_json(VECTOR, "ROW-VECTOR-2")
    sealed = crypto.encrypt_json({"x": 1}, "ctx")
    assert sealed[0] == 1 and len(sealed) > 29
    assert crypto.decrypt_json(sealed, "ctx") == {"x": 1}
