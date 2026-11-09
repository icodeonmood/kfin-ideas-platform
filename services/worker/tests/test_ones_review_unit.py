"""Ones review fixes that need no stack (BLD-110 to BLD-113): held text is refused, a number race answers 409,
the demo only ever writes to the local dev database, and the repo writer removes only a demo idea's own file."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import psycopg
import pytest

from bootstrap import demo
from core.config import Settings
from ones import service, text
from ones.text import OnesRefused
from repo_writer import writer

THRESHOLDS = {
    "gatekeeper": {"personal_data_block": 0.5, "redirect_suggest": 0.8, "spam_hold": 0.9},
    "scan": {},
}


def _gk(**over: Any) -> dict[str, Any]:
    gk: dict[str, Any] = {
        "personal_data": {"found": False, "confidence": 0.0},
        "investor_context_tags": [],
        "kind": {"value": "idea", "confidence": 0.99},
        "abuse": {"value": False, "confidence": 0.0},
    }
    gk.update(over)
    return gk


def test_held_text_is_refused_with_its_own_code(monkeypatch: pytest.MonkeyPatch) -> None:
    import scan.pipeline as pipeline

    monkeypatch.setattr(pipeline, "thresholds", lambda: THRESHOLDS)
    for gk in (
        _gk(kind={"value": "spam", "confidence": 0.99}),
        _gk(abuse={"value": True, "confidence": 0.99}),
    ):
        with pytest.raises(OnesRefused) as exc:
            text._verdict(gk)
        assert exc.value.code == "text_needs_review"
    with pytest.raises(OnesRefused) as exc:
        text._verdict(_gk(personal_data={"found": True, "confidence": 0.9}))
    assert exc.value.code == "personal_data"
    text._verdict(_gk())  # plain text passes


def test_a_number_race_answers_try_again(monkeypatch: pytest.MonkeyPatch) -> None:
    def clash(*_a: Any, **_k: Any) -> Any:
        raise psycopg.errors.UniqueViolation("duplicate key value")

    monkeypatch.setattr(service, "_need", lambda *_a, **_k: {"admin"})
    monkeypatch.setattr(service, "_carry_out", clash)
    with pytest.raises(OnesRefused) as exc:
        service.carry_out(None, "admin-user", 1, now=dt.datetime.now(dt.UTC))  # type: ignore[arg-type]
    assert (exc.value.status, exc.value.code) == (409, "try_again")


@pytest.mark.parametrize(
    ("env", "url", "allowed"),
    [
        ("dev", "postgres://ideas:ideas@localhost:5432/ideas", True),
        ("dev", "postgres://ideas_worker:x@postgres:5432/ideas", True),
        ("dev", "postgres://ideas:ideas@localhost:5532/ideas", True),
        ("uat", "postgres://ideas:ideas@localhost:5432/ideas", False),
        ("dev", "postgres://ideas:ideas@db.uat.kfintech.example:5432/ideas", False),
        ("dev", "postgres://ideas:ideas@localhost:5432/ideas_prod", False),
    ],
)
def test_the_demo_writes_only_to_the_local_dev_database(
    env: str, url: str, allowed: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(demo, "get_settings", lambda: Settings(app_env=env, database_url=url))
    if allowed:
        demo._dev_only()
    else:
        with pytest.raises(SystemExit):
            demo._dev_only()


def _writer(tmp_path: Path, env: str = "dev") -> writer.RepoWriter:
    return writer.RepoWriter(Settings(app_env=env, company_repo_path=tmp_path))


def test_the_repo_writer_removes_only_the_named_demo_file(tmp_path: Path) -> None:
    month = tmp_path / "ideas" / "2026" / "11"
    month.mkdir(parents=True)
    (month / "IDEA-2026-000123.md").write_text("demo idea\n", encoding="utf-8")
    (month / "IDEA-2026-000124.md").write_text("someone else's idea\n", encoding="utf-8")
    (month / "index.md").write_text(
        "# Ideas, November 2026\n\n* [IDEA-2026-000123](IDEA-2026-000123.md) - demo\n"
        "* [IDEA-2026-000124](IDEA-2026-000124.md) - kept\n",
        encoding="utf-8",
    )
    event = {
        "id": 7, "aggregate_id": "IDEA-2026-000123", "actor": "process:demo",
        "payload": {"demo": True, "path": "ideas/2026/11/IDEA-2026-000123.md"},
    }  # fmt: skip
    message = _writer(tmp_path)._remove_demo_file(event)
    assert message.startswith("[IDEA-2026-000123] demo_removed")
    assert not (month / "IDEA-2026-000123.md").exists() and (month / "IDEA-2026-000124.md").exists()
    index = (month / "index.md").read_text(encoding="utf-8")
    assert "IDEA-2026-000123" not in index and "IDEA-2026-000124" in index


@pytest.mark.parametrize(
    ("env", "payload", "aggregate"),
    [
        ("uat", {"demo": True, "path": "ideas/2026/11/IDEA-2026-000123.md"}, "IDEA-2026-000123"),
        ("dev", {"demo": False, "path": "ideas/2026/11/IDEA-2026-000123.md"}, "IDEA-2026-000123"),
        ("dev", {"demo": True, "path": "rules/thresholds.md"}, "IDEA-2026-000123"),
        ("dev", {"demo": True, "path": "ideas/2026/11/IDEA-2026-000999.md"}, "IDEA-2026-000123"),
        ("dev", {"demo": True, "path": "ideas/2026/11/../../../x/IDEA-2026-000123.md"}, "IDEA-2026-000123"),
    ],
)
def test_the_repo_writer_refuses_anything_else(
    tmp_path: Path, env: str, payload: dict[str, Any], aggregate: str
) -> None:
    event = {"id": 8, "aggregate_id": aggregate, "actor": "process:demo", "payload": payload}
    with pytest.raises(writer.EventError) as exc:
        _writer(tmp_path, env)._remove_demo_file(event)
    assert exc.value.code == "demo_remove_refused"
