"""UAT deploy pieces (B7, AT-B7-06). The full run is `make uat-rehearsal` (a UAT-shaped stack from an empty
database, smoke-tested, then torn down); these tests keep its parts honest between rehearsals."""

from __future__ import annotations

import contextlib
from typing import Any

import pytest

from bootstrap import preflight, smoke

GOOD = {
    "APP_ENV": "uat",
    "APP_BASE_URL": "https://ideas-uat.kfintech.example",
    "INTERNAL_API_TOKEN": "a" * 40,
    "SESSION_SECRET": "b" * 40,
    "CONTRIBUTOR_HMAC_SECRET": "c" * 40,
    "VAULT_ENCRYPTION_KEY": "d" * 40,
    "S3_ENDPOINT": "https://s3.uat.kfintech.example",
    "S3_ACCESS_KEY": "uat-ideas-store",
    "S3_SECRET_KEY": "e" * 24,
    "CLAMAV_HOST": "scanner.uat.kfintech.example",
    "OIDC_MODE": "entra",
    "OIDC_ISSUER": "https://login.microsoftonline.com/tenant/v2.0",
    "OIDC_CLIENT_ID": "ideas-platform",
    "OIDC_CLIENT_SECRET": "f" * 30,
    "LLM_MODE": "anthropic",
    "ANTHROPIC_API_KEY": "from-the-vault",
    "EMBEDDINGS_MODE": "bge-m3",
    "EMAIL_MODE": "graph",
    "GRAPH_TENANT_ID": "t",
    "GRAPH_CLIENT_ID": "c",
    "GRAPH_SERVICE_MAILBOX": "garage@kfintech.example",
    "KFIN_EMAIL_DOMAINS": "kfintech.com,kfintech.example",
}


def test_preflight_passes_a_uat_configuration() -> None:
    assert preflight.check(GOOD) == ([], [])
    assert preflight.ai_route_ready(GOOD)


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({"APP_ENV": "dev"}, "APP_ENV must be uat or prod"),
        ({"SESSION_SECRET": "change-me-32-bytes-min"}, "SESSION_SECRET must be a random value"),
        ({"INTERNAL_API_TOKEN": "short"}, "INTERNAL_API_TOKEN must be a random value"),
        ({"VAULT_ENCRYPTION_KEY": ""}, "VAULT_ENCRYPTION_KEY is not set"),
        ({"S3_SECRET_KEY": "minio-secret"}, "S3_SECRET_KEY must be the UAT store's key"),
        ({"S3_ACCESS_KEY": "minio"}, "S3_ACCESS_KEY must be the UAT store's access key"),
        ({"CLAMAV_HOST": ""}, "CLAMAV_HOST is not set"),
        ({"OIDC_MODE": "mock"}, "OIDC_MODE must be entra"),
        ({"OIDC_ISSUER": "http://localhost:8090/default"}, "OIDC_ISSUER must be an https URL"),
        ({"ANTHROPIC_API_KEY": ""}, "LLM_MODE=anthropic needs ANTHROPIC_API_KEY"),
        ({"GRAPH_SERVICE_MAILBOX": ""}, "EMAIL_MODE=graph needs GRAPH_SERVICE_MAILBOX"),
    ],
)
def test_preflight_refuses_dev_settings_and_weak_secrets(change: dict[str, str], expected: str) -> None:
    problems, _ = preflight.check(GOOD | change)
    assert any(p.startswith(expected) for p in problems), problems


def test_preflight_warns_about_mode_b_without_stopping() -> None:
    problems, warnings = preflight.check(GOOD | {"LLM_MODE": "fake", "EMBEDDINGS_MODE": "hash"})
    assert problems == []
    assert any("Mode B" in w for w in warnings) and any("bge-m3" in w for w in warnings)
    assert not preflight.ai_route_ready(GOOD | {"LLM_MODE": "fake"})


def test_preflight_never_prints_a_secret(capsys: pytest.CaptureFixture[str], monkeypatch: Any) -> None:
    for k, v in (GOOD | {"SESSION_SECRET": "change-me-but-secret-ish-value"}).items():
        monkeypatch.setenv(k, v)
    assert preflight.main() == 1
    out = capsys.readouterr().out
    assert "change-me-but-secret-ish-value" not in out and "a" * 40 not in out


@pytest.mark.stack
def test_smoke_checks_pass_on_the_dev_stack() -> None:
    results = {name: run() for name, run in smoke.checks("http://localhost:3000", "http://localhost:8000")}
    failed = {name: detail for name, (ok, detail) in results.items() if not ok}
    assert failed == {}


@pytest.mark.stack
def test_the_first_admin_is_granted_from_the_command_line(db: Any, monkeypatch: Any) -> None:
    from identity import grants
    from identity.codes import emp_id_hash

    db.execute(
        "INSERT INTO users (emp_id_hash, name, email, source) VALUES (%s, 'Uat Admin', 'uat.admin@kfintech.example', 'hr')",
        (emp_id_hash("SYN-09001"),),
    )
    monkeypatch.setattr("core.db.connect", lambda *a, **k: contextlib.nullcontext(db))
    argv = [
        "grant",
        "--employee-id",
        "SYN-09001",
        "--role",
        "admin",
        "--reason",
        "First UAT admin, ticket UAT-1",
    ]
    assert grants.main([*argv, "--actor", "ops:REV-0001"]) == 0
    assert db.execute("SELECT count(*) AS n FROM role_grants WHERE role = 'admin'").fetchone()["n"] == 1
    assert db.execute(
        "SELECT 1 FROM audit_log WHERE action = 'role.grant' AND actor = 'ops:REV-0001'"
    ).fetchone()
    assert grants.main(["grant", "--employee-id", "SYN-99999", "--role", "admin", "--reason", "No such person here",
                        "--actor", "ops:REV-0001"]) == 1  # fmt: skip
