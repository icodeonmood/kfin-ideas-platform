"""Settings from the environment, with `.env` at the repo root as a fallback for local runs.

Relative paths in `.env` (for example `COMPANY_REPO_PATH=./.data/kfin-ideas`) are resolved against the
directory that holds `.env`, so `uv run` from `services/worker/` and a container agree on what they mean.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def find_repo_root(start: Path | None = None) -> Path | None:
    """Walk up from `start` (default: cwd) to the folder holding the app repo's Makefile and CLAUDE.md."""
    here = (start or Path.cwd()).resolve()
    for folder in (here, *here.parents):
        if (folder / "CLAUDE.md").is_file() and (folder / "Makefile").is_file():
            return folder
    return None


REPO_ROOT = find_repo_root(Path(__file__).parent)
_ENV_FILE = (REPO_ROOT / ".env") if REPO_ROOT else None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = ""  # must be set; anything but dev or test gets production rules (fail closed)
    database_url: str = "postgres://ideas:ideas@localhost:5432/ideas?sslmode=disable"

    company_repo_path: Path = Path("./.data/kfin-ideas")
    company_repo_remote: str = ""
    repo_writer_author: str = "Ideas Platform Bot <ideas-bot@localhost>"

    kfin_email_domains: str = "kfintech.com"
    privacy_notice_version: str = ""
    contributor_hmac_secret: str = ""
    vault_encryption_key: str = ""

    embeddings_mode: str = "hash"
    llm_mode: str = "fake"

    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "minio"
    s3_secret_key: str = "minio-secret"  # noqa: S105 - dev-only default; UAT/prod inject it
    s3_bucket_quarantine: str = "ideas-quarantine"
    s3_bucket_clean: str = "ideas-clean"

    clamav_host: str = "localhost"
    clamav_port: int = 3310
    smtp_url: str = "smtp://localhost:1025"

    worker_roles: str = "api,repo_writer,indexer,jobs,scheduler"
    internal_api_token: str = ""
    worker_port: int = 8000
    index_poll_seconds: float = 2.0
    repo_writer_poll_seconds: float = 1.0
    log_level: str = "INFO"

    @field_validator("*", mode="before")
    @classmethod
    def _no_comment_values(cls, value: object) -> object:
        """Some dotenv readers turn `KEY=   # note` into the value "# note". Treat that as empty."""
        if isinstance(value, str) and value.strip().startswith("#"):
            return ""
        return value

    @field_validator("company_repo_path", mode="after")
    @classmethod
    def _resolve_repo_path(cls, value: Path) -> Path:
        if value.is_absolute():
            return value
        base = REPO_ROOT if REPO_ROOT else Path.cwd()
        return (base / value).resolve()

    @property
    def is_production_like(self) -> bool:
        return self.app_env not in {"dev", "test"}

    @property
    def kfin_domains(self) -> list[str]:
        return [d.strip().lower() for d in self.kfin_email_domains.split(",") if d.strip()]

    @property
    def roles(self) -> set[str]:
        return {r.strip() for r in self.worker_roles.split(",") if r.strip()}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
