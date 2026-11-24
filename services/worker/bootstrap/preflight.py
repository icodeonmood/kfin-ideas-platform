"""UAT and prod preflight (AT-B7-06): refuse to deploy with dev settings or weak secrets, and say plainly which
features will start switched off. Runs inside the worker image, against the environment the services will get.

python -m bootstrap.preflight      exits 1 on any problem; warnings do not stop the deploy.

Reads names only; never prints a secret's value.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from email.utils import parseaddr

SECRETS = ("INTERNAL_API_TOKEN", "SESSION_SECRET", "CONTRIBUTOR_HMAC_SECRET", "VAULT_ENCRYPTION_KEY")
DEV_VALUES = {"ideas", "minio", "minio-secret", "dev-web-only", "dev-worker-only", "change-me"}
# Email through Graph (BLD-A243). GRAPH_CLIENT_SECRET is the worker's alone: the database env file, never the app's.
GRAPH_NAMES = (
    "GRAPH_TENANT_ID",
    "GRAPH_CLIENT_ID",
    "GRAPH_SERVICE_MAILBOX",
    "GRAPH_CLIENT_SECRET",
    "EMAIL_FROM",
)


def is_production(app_env: str) -> bool:
    """Production mode (BLD-A235): APP_ENV is `prod` as this preflight reads it, stripped and case-sensitive, so a
    value preflight passes as prod is prod in the seed and the smoke checks too. Anything else is not production."""
    return app_env.strip() == "prod"


def check(env: Mapping[str, str]) -> tuple[list[str], list[str]]:
    """(problems, warnings) for a UAT or prod environment."""
    problems: list[str] = []
    warnings: list[str] = []

    def get(name: str) -> str:
        value = env.get(name, "").strip()
        return "" if value.startswith("#") else value

    if get("APP_ENV") not in ("uat", "prod"):
        problems.append("APP_ENV must be uat or prod")
    for name in SECRETS:
        value = get(name)
        if not value:
            problems.append(f"{name} is not set")
        elif value.startswith("change-me") or value in DEV_VALUES or len(value) < 32:
            problems.append(f"{name} must be a random value of at least 32 characters (from the vault)")
    vault_key = get("PSEUDONYM_VAULT_KEY")
    if len(vault_key) < 32:
        problems.append("PSEUDONYM_VAULT_KEY must be a random value of at least 32 characters (worker only)")
    elif vault_key == get("VAULT_ENCRYPTION_KEY"):
        problems.append(
            "PSEUDONYM_VAULT_KEY must differ from VAULT_ENCRYPTION_KEY, which the web app also holds"
        )
    if get("S3_SECRET_KEY") in DEV_VALUES or len(get("S3_SECRET_KEY")) < 16:
        problems.append("S3_SECRET_KEY must be the UAT store's key (at least 16 characters)")
    if not get("S3_ACCESS_KEY") or get("S3_ACCESS_KEY") in DEV_VALUES:
        problems.append("S3_ACCESS_KEY must be the UAT store's access key")
    for name in ("S3_ENDPOINT", "CLAMAV_HOST"):
        if not get(name):
            problems.append(f"{name} is not set (KFin's file store and virus scanner in UAT)")
    if get("OIDC_MODE") != "entra":
        problems.append("OIDC_MODE must be entra (the mock sign-in is for dev only)")
    for name in ("OIDC_ISSUER", "OIDC_CLIENT_ID", "OIDC_CLIENT_SECRET"):
        if not get(name):
            problems.append(f"{name} is not set (Entra app registration, IT item O2)")
    if get("OIDC_ISSUER") and not get("OIDC_ISSUER").startswith("https://"):
        problems.append("OIDC_ISSUER must be an https URL")
    if not get("APP_BASE_URL").startswith("https://"):
        warnings.append("APP_BASE_URL is not https: links in emails will not be secure")
    if get("DATABASE_URL"):
        warnings.append("DATABASE_URL in the app env file is ignored: each service gets its own login")

    mode = get("LLM_MODE") or "fake"
    if mode == "fake":
        warnings.append(
            "LLM_MODE=fake: Mode B, `ai.all` starts off and scans queue until the route is approved (D1)"
        )
    elif mode == "anthropic" and not get("ANTHROPIC_API_KEY"):
        problems.append("LLM_MODE=anthropic needs ANTHROPIC_API_KEY (from the vault)")
    elif mode == "bedrock" and not get("AWS_REGION"):
        problems.append("LLM_MODE=bedrock needs AWS_REGION")
    elif mode not in ("anthropic", "bedrock"):
        problems.append("LLM_MODE must be fake, anthropic or bedrock")
    if (get("EMBEDDINGS_MODE") or "hash") == "hash":
        warnings.append(
            "EMBEDDINGS_MODE=hash: matching quality is not representative (UAT should use bge-m3, AT-B5-01)"
        )
    email_mode = get("EMAIL_MODE") or "smtp"
    # BLD-A243: the secret comes from the database env file, the rest from the app env file.
    if email_mode == "graph":
        for name in GRAPH_NAMES:
            if not get(name):
                problems.append(f"EMAIL_MODE=graph needs {name}")
        mailbox, sender = get("GRAPH_SERVICE_MAILBOX"), get("EMAIL_FROM")
        if mailbox and "@" not in mailbox:
            problems.append("GRAPH_SERVICE_MAILBOX must be the service mailbox's email address")
        elif mailbox and sender and parseaddr(sender)[1].strip().lower() != mailbox.lower():
            problems.append(
                "EMAIL_FROM must be the service mailbox's address (GRAPH_SERVICE_MAILBOX) with EMAIL_MODE=graph"
            )
    elif email_mode == "smtp":
        warnings.append("EMAIL_MODE=smtp: email goes to the SMTP_URL server, not the KFin service mailbox")
    else:
        problems.append("EMAIL_MODE must be smtp or graph")
    if "kfintech.example" not in get("KFIN_EMAIL_DOMAINS"):
        warnings.append(
            "KFIN_EMAIL_DOMAINS lacks kfintech.example: the synthetic UAT people will look external"
        )
    return problems, warnings


def ai_route_ready(env: Mapping[str, str]) -> bool:
    """Whether a real model route is configured; if not, the deploy switches `ai.all` off (Mode B, §9.3)."""
    mode = env.get("LLM_MODE", "fake").strip()
    return (mode == "anthropic" and bool(env.get("ANTHROPIC_API_KEY", "").strip())) or mode == "bedrock"


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "ai-route-ready":
        return 0 if ai_route_ready(os.environ) else 1
    problems, warnings = check(os.environ)
    for w in warnings:
        print(f"warning  {w}")
    for p in problems:
        print(f"PROBLEM  {p}")
    print("preflight: ok" if not problems else f"preflight: {len(problems)} problem(s); nothing was deployed")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
