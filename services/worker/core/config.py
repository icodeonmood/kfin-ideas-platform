"""Settings from the environment, with `.env` at the repo root as a fallback for local runs.

Relative paths in `.env` (for example `COMPANY_REPO_PATH=./.data/kfin-ideas`) are resolved against the
directory that holds `.env`, so `uv run` from `services/worker/` and a container agree on what they mean.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import field_validator, model_validator
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
    # Worker only (B8 hardening): the pseudonym vault's own key. The web app never receives it, so a web-side
    # compromise plus a copy of the database still cannot open the vault. Empty in dev: the shared key is used.
    pseudonym_vault_key: str = ""

    # OCR for images and scanned PDF pages (§4.2 attachments, week 3): tesseract in the worker image; `fake`
    # reads the text a synthetic test image carries in its metadata, for host-side tests without Tesseract.
    ocr_mode: str = "tesseract"
    ocr_languages: str = "eng+hin"

    embeddings_mode: str = "hash"
    embeddings_model_path: str = (
        ""  # bge-m3 only: local folder with the model files (never fetched at run time)
    )
    # Voice (DEC-096, DEC-108): speech to text. `sarvam` is the launch route (DEC-108): Sarvam's APIs through the
    # gateway (`gateway/sarvam.py`), which refuse to run without `SPEECH_HOSTED_APPROVAL` (DEC-108), the
    # `speech.hosted` switch and `SARVAM_API_KEY`. `fake` (dev and tests) reads the text a synthetic test recording
    # carries, else a fixed sample; `local` (the fallback, no further work) runs the engine on KFin's own server
    # from `SPEECH_MODEL_PATH` in images built with WITH_SPEECH=1.
    speech_mode: str = "fake"  # fake | local | sarvam
    speech_local_engine: str = "faster-whisper"  # faster-whisper | indic-conformer (coming soon)
    speech_model_path: str = ""  # local only: folder with the model files (never fetched at run time)
    # Outside dev and test, `local` speech must be the isolated speech service (BLD-C012): its own container with
    # no route to the database, the store or the internet. Empty = the in-worker child, allowed in dev and test only.
    speech_engine_url: str = ""
    speech_service_token: str = (
        ""  # shared with the speech service only (not the web app), at least 32 characters
    )
    # Outside dev and test, SPEECH_ENGINE_URL must be http:// to one of these hosts on the internal speech network
    # (BLD-C030): a recording must never be sent anywhere else by a mistyped or tampered setting.
    speech_engine_hosts: str = "speech"
    speech_max_seconds: int = 180
    speech_threads: int = 2  # the engine child's CPU threads
    speech_memory_mb: int = 4096  # the engine child's address-space limit (Linux)
    speech_timeout_s: int = 300  # the engine child's wall-clock limit
    speech_hosted_approval: str = ""  # the approval reference (DEC-108); empty = hosted routes refuse
    # Sarvam (DEC-108). The key is worker-only: never in the web app's env (compose blanks it there; deploy.sh refuses
    # it in the app env file). `SARVAM_BASE_URL` points the client at a local fake in dev and test only; outside
    # them the real service is always used.
    sarvam_api_key: str = ""
    sarvam_base_url: str = ""
    sarvam_stt_mode: str = "codemix"  # codemix | transcribe: the person's own words, as spoken (DEC-108)
    sarvam_tts_speaker: str = "simran_en_customer"  # one clear Indian English voice (L-LISTEN/6)
    llm_mode: str = "fake"  # fake | anthropic | bedrock (route per InfoSec, D1)
    llm_fast_model: str = "claude-haiku-5-5"
    llm_reasoning_model: str = "claude-sonnet-5-5"
    aws_region: str = "ap-south-1"
    llm_max_reasoning_concurrency: int = 20
    llm_max_fast_concurrency: int = 50
    llm_requests_per_minute_fast: int = 600
    llm_requests_per_minute_reasoning: int = 300
    llm_daily_budget_inr: float = 5000.0
    llm_usd_to_inr: float = 88.0  # finance sets the rate used for cost logging
    llm_refusal_fallback: bool = True  # Claude API route only: server-side fallback on a policy decline
    llm_fake_latency: str = "none"  # none | realistic (AT-B4-09)
    agents_dir: Path = Path("./agents")

    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "minio"
    s3_secret_key: str = "minio-secret"  # noqa: S105 - dev-only default; UAT/prod inject it
    s3_bucket_quarantine: str = "ideas-quarantine"
    s3_bucket_clean: str = "ideas-clean"

    clamav_host: str = "localhost"
    clamav_port: int = 3310
    smtp_url: str = "smtp://localhost:1025"
    app_base_url: str = "http://localhost:3000"

    # Dev and test only: where host-side tools and tests reach the local stack. A second stack in a worktree
    # sets these in its own `.env` (BLD-200); the defaults are the first stack's ports.
    worker_url: str = "http://localhost:8000"
    oidc_issuer: str = "http://localhost:8090/default"
    postgres_port: int = 5432
    mailpit_ui_host_port: int = 8025

    worker_roles: str = "api,repo_writer,indexer,jobs,scheduler,ticker"
    internal_api_token: str = ""
    worker_port: int = 8000
    # A host only on the default network (compose: postgres): the API listens on that network and 127.0.0.1 only,
    # never on the speech network (BLD-C017). Empty: 0.0.0.0, for host-side runs and tests.
    worker_api_bind_peer: str = ""
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

    @field_validator("company_repo_path", "agents_dir", mode="after")
    @classmethod
    def _resolve_repo_path(cls, value: Path) -> Path:
        if value.is_absolute():
            return value
        base = REPO_ROOT if REPO_ROOT else Path.cwd()
        return (base / value).resolve()

    @model_validator(mode="after")
    def _speech_engine_url_allowed(self) -> Settings:
        """Outside dev and test the speech service's address is http:// to an allowed host, or the worker refuses to
        start (BLD-C030). Dev and test may point it anywhere (the contract test runs it on localhost)."""
        if self.speech_engine_url and self.is_production_like:
            url = urlsplit(self.speech_engine_url)
            hosts = {h.strip().lower() for h in self.speech_engine_hosts.split(",") if h.strip()}
            if (
                url.scheme != "http"
                or (url.hostname or "").lower() not in hosts
                or url.username
                or url.password
            ):
                raise ValueError(
                    "SPEECH_ENGINE_URL must be http:// to an allowed speech host outside dev and test"
                )
        return self

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
