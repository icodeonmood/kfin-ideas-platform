"""AT-B2-02: contributor code is `CTR-` + the first 6 hex characters of HMAC-SHA256(employee ID, secret); the
same employee always gets the same code; the secret comes only from the environment."""

import hashlib
import hmac
from collections.abc import Iterator
from typing import Any

import pytest

from core.config import get_settings
from identity import codes

SECRET = "vector-secret-for-tests-only-0001"
# Shared with apps/web/tests/unit/codes.test.ts: both languages must produce exactly these values.
VECTOR = {
    "employee_id": "SYN-90001",
    "code": "CTR-fb857d",
    "code8": "CTR-fb857d55",
    "hash16": "a0cd9e28ae246d18",
}


@pytest.fixture
def secret(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("CONTRIBUTOR_HMAC_SECRET", SECRET)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_code_is_ctr_plus_six_hex_of_the_hmac(secret: None) -> None:
    expected = hmac.new(SECRET.encode(), b"SYN-90001", hashlib.sha256).hexdigest()[:6]
    assert codes.contributor_code("SYN-90001") == f"CTR-{expected}" == VECTOR["code"]
    assert codes.contributor_code("SYN-90001", 8) == VECTOR["code8"]
    assert codes.emp_id_hash("SYN-90001")[:16] == VECTOR["hash16"]


def test_same_employee_same_code(secret: None) -> None:
    assert codes.contributor_code("SYN-90001") == codes.contributor_code("  syn-90001 ")
    assert codes.contributor_code("SYN-90001") != codes.contributor_code("SYN-90002")


def test_code_and_employee_hash_are_unlinkable(secret: None) -> None:
    """users.emp_id_hash must not reveal the code, or deleting contributor_map would not anonymise (§2.5)."""
    code_hex = codes.contributor_code("SYN-90001").removeprefix("CTR-")
    assert not codes.emp_id_hash("SYN-90001").startswith(code_hex)


def test_secret_comes_only_from_the_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    monkeypatch.delenv("CONTRIBUTOR_HMAC_SECRET", raising=False)
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()
    monkeypatch.setattr("core.config._ENV_FILE", None, raising=False)
    monkeypatch.setattr(
        get_settings().__class__, "model_config", {**get_settings().model_config, "env_file": None}
    )
    get_settings.cache_clear()
    try:
        with pytest.raises(codes.SecretMissing):
            codes.contributor_code("SYN-90001")
    finally:
        get_settings.cache_clear()


def test_placeholder_secret_refused_outside_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONTRIBUTOR_HMAC_SECRET", "change-me")
    monkeypatch.setenv("APP_ENV", "prod")
    get_settings.cache_clear()
    try:
        with pytest.raises(codes.SecretMissing):
            codes.contributor_code("SYN-90001")
    finally:
        get_settings.cache_clear()


@pytest.mark.stack
def test_collision_extends_to_eight_characters(db: Any, secret: None) -> None:
    other = db.execute(
        "INSERT INTO users (emp_id_hash, name, email) VALUES ('h-other', 'Synthetic Other', 'other@kfintech.example') RETURNING id"
    ).fetchone()["id"]
    me = db.execute(
        "INSERT INTO users (emp_id_hash, name, email) VALUES ('h-me', 'Synthetic Me', 'me@kfintech.example') RETURNING id"
    ).fetchone()["id"]
    db.execute(
        "INSERT INTO contributor_map (contributor_code, user_id) VALUES (%s, %s)", (VECTOR["code"], other)
    )
    assert codes.assign_contributor_code(db, str(me), "SYN-90001") == VECTOR["code8"]
    assert codes.assign_contributor_code(db, str(me), "SYN-90001") == VECTOR["code8"]  # stable afterwards


def test_missing_app_env_gets_production_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONTRIBUTOR_HMAC_SECRET", "change-me")
    monkeypatch.setenv("APP_ENV", "")
    get_settings.cache_clear()
    try:
        assert get_settings().is_production_like
        with pytest.raises(codes.SecretMissing):
            codes.contributor_code("SYN-90001")
    finally:
        get_settings.cache_clear()
