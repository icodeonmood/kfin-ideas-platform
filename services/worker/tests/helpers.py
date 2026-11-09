"""Helpers for integration tests: fresh databases, temporary company repos, synthetic ideas and events."""

from __future__ import annotations

import json
import os
import secrets
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from core.config import REPO_ROOT, Settings
from core.db import Conn

assert REPO_ROOT is not None
ROOT: Path = REPO_ROOT
SEED = ROOT / "seed" / "company-repo"
COMPOSE = [
    "docker",
    "compose",
    "-f",
    "infra/docker-compose.yml",
    "--project-directory",
    ".",
    "--env-file",
    ".env",
]
PG_PORT = Settings().postgres_port  # host port of the dev stack's Postgres (BLD-200)
ADMIN_URL = os.environ.get(
    "TEST_ADMIN_DATABASE_URL", f"postgres://ideas:ideas@localhost:{PG_PORT}/postgres?sslmode=disable"
)
CANVAS_EXAMPLE = ROOT / "agents" / "canvas-assist" / "examples" / "01-quick-capture.json"


def db_url(name: str, host: str = "localhost") -> str:
    """`localhost` is the host side of the dev stack; `postgres` is the name inside its Docker network."""
    port = 5432 if host == "postgres" else PG_PORT
    return f"postgres://ideas:ideas@{host}:{port}/{name}?sslmode=disable"


def create_database(prefix: str = "ideas_test") -> str:
    name = f"{prefix}_{secrets.token_hex(4)}"
    with psycopg.connect(ADMIN_URL, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}"')
    return name


def drop_database(name: str) -> None:
    with psycopg.connect(ADMIN_URL, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


def dbmate(name: str, *args: str) -> subprocess.CompletedProcess[str]:
    """Run the real migration tool (the same container `make migrate` uses) against database `name`."""
    cmd = [*COMPOSE, "run", "--rm", "-T", "-e", f"DATABASE_URL={db_url(name, 'postgres')}", "dbmate", *args]
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)


def seeded_repo(dest: Path) -> Path:
    """A company repo exactly as `make seed` creates it, in a temp folder."""
    from bootstrap.seed import create_company_repo

    create_company_repo(SEED, dest, "Ideas Platform Bot <ideas-bot@localhost>", SEED.parent / "dev-overlay")
    return dest


def settings_for(repo: Path, database: str, **extra: Any) -> Settings:
    return Settings(company_repo_path=repo, database_url=db_url(database), **extra)


def synthetic_canvas() -> dict[str, Any]:
    """The handed-over synthetic canvas-assist example, plus the original text it came from."""
    example = json.loads(CANVAS_EXAMPLE.read_text(encoding="utf-8"))
    canvas: dict[str, Any] = dict(example["output"])
    canvas["original_text"] = canvas["details"]
    canvas["generated_by"] = "canvas-assist/0.1.0"
    return canvas


def insert_idea(conn: Conn, *, contributor: str = "CTR-0a1b2c", stage: str = "scanned") -> str:
    year = datetime.now(UTC).astimezone().year
    number = conn.execute("SELECT next_number('IDEA', %s) AS n", (str(year),)).fetchone()["n"]
    idea_id, sub_id = f"IDEA-{year}-{number:06d}", f"SUB-{year}-{number:06d}"
    canvas = synthetic_canvas()
    system = canvas["system"]
    conn.execute(
        "INSERT INTO ideas (idea_id, submission_id, stage, capture_mode, kind, category, play, basis, strength, scope, "
        "area_ids, lobs, systems, roles_affected, visibility, contributor_code, language, canvas, submitted_at) "
        "VALUES (%s,%s,%s,'quick',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'org',%s,'en',%s, now())",
        (
            idea_id, sub_id, stage, canvas["kind"], canvas["value"]["category"], canvas["value"]["play"],
            canvas["value"]["basis"], canvas["strength"]["score"], system["scope"], system["areas"], system["lobs"],
            system["systems"], system["roles_affected"], contributor, Jsonb(canvas),
        ),
    )  # fmt: skip
    return idea_id


def insert_event(
    conn: Conn, idea_id: str, *, actor: str = "CTR-0a1b2c", event: str = "idea.submitted"
) -> int:
    row = conn.execute(
        "INSERT INTO outbox (event_type, aggregate_id, actor, payload) VALUES (%s, %s, %s, %s) RETURNING id",
        (
            event,
            idea_id,
            actor,
            Jsonb({"idea_id": idea_id, "history": [{"event": event.split(".")[1], "note": ""}]}),
        ),
    ).fetchone()
    assert row is not None
    return int(row["id"])


def git_log(repo: Path) -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(repo), "log", "--format=%H%x1f%B%x1e"], capture_output=True, text=True, check=True
    )
    return [c.strip() for c in out.stdout.split("\x1e") if c.strip()]


def tables_containing(conn: Conn, needle: str) -> list[str]:
    """Every `table.column` in the public schema whose value contains `needle` as plain text (AT-B4-06).
    Text and JSON columns are searched as text; bytea columns as UTF-8 bytes."""
    cols = conn.execute(
        "SELECT table_name, column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = 'public' AND data_type IN ('text', 'character varying', 'jsonb', 'json', 'bytea', "
        "'ARRAY') AND table_name NOT LIKE 'schema_migrations%%'"
    ).fetchall()
    found = []
    for c in cols:
        t, col, typ = c["table_name"], c["column_name"], c["data_type"]
        if typ == "bytea":
            sql = f'SELECT 1 FROM "{t}" WHERE position(convert_to(%s, \'UTF8\') in "{col}") > 0 LIMIT 1'  # noqa: S608
        else:
            sql = f"SELECT 1 FROM \"{t}\" WHERE \"{col}\"::text LIKE '%%' || %s || '%%' LIMIT 1"  # noqa: S608
        if conn.execute(sql, (needle,)).fetchone():
            found.append(f"{t}.{col}")
    return found
