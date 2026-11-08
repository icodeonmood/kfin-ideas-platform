"""Go/no-go evidence (§9.3): Mode A only when every criterion is met; a failed load test or drill rules it out;
an unreadable report becomes a row to confirm, not a crash."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pytest

import gonogo.__main__ as g
from core.config import Settings

pytestmark = pytest.mark.stack  # reads leak aborts and switches from the dev database


def _write(folder: Path, name: str, body: Any) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(body if isinstance(body, str) else json.dumps(body), encoding="utf-8")


@pytest.fixture
def evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> argparse.Namespace:
    monkeypatch.setattr(g, "get_settings", lambda: Settings(privacy_notice_version="1.0"))
    real = {"route": "anthropic", "version": "0.2.0"}
    _write(tmp_path / "eval", "gatekeeper-0.2.0-1.json",
           real | {"metrics": {"personal_data_recall": 1.0, "false_block_rate": 0.02}})  # fmt: skip
    _write(tmp_path / "eval", "judge-0.2.1-1.json", real | {"metrics": {"same_precision": 0.9}})
    _write(tmp_path / "load", "report-1.json", {
        "settings": {"scale": 1.0, "submissions_per_hour": 150, "sign_ins": 3000, "base_url": "http://test-mac"},
        "scan": {"p95_s": 8.0}, "error_rate": 0.001, "pass": {"scan_p95": True, "page_p95": True, "error_rate": True},
    })  # fmt: skip
    _write(
        tmp_path / "ops", "restore-drill-1.json", {"passed": True, "seconds": 5400, "where": "UAT", "at": "x"}
    )
    return argparse.Namespace(
        since="2100-01-01", vapt_open_high=0, sso_ready="yes", reports_dir=tmp_path / "eval",
        loadtest_dir=tmp_path / "load", drill_dir=tmp_path / "ops",
    )  # fmt: skip


def test_mode_a_needs_every_criterion(evidence: argparse.Namespace) -> None:
    out = g.collect(evidence)
    assert out["mode"] == "A. Full, once every 'confirm' row is confirmed"  # the CI row is always a person's
    assert [r["state"] for r in out["rows"] if r["state"] != "met"] == ["confirm"]


def test_a_load_rehearsal_or_a_failed_drill_rules_out_mode_a(evidence: argparse.Namespace) -> None:
    report = json.loads((evidence.loadtest_dir / "report-1.json").read_text())
    report["settings"]["scale"] = 0.1
    _write(evidence.loadtest_dir, "report-1.json", report)
    assert g.collect(evidence)["mode"] == "B. Capture first"
    _write(
        evidence.drill_dir,
        "restore-drill-1.json",
        {"passed": False, "seconds": 60, "where": "UAT", "at": "x"},
    )
    assert g.collect(evidence)["mode"] == "C. Preview"


def test_an_unreadable_report_is_a_row_to_confirm(evidence: argparse.Namespace) -> None:
    _write(evidence.loadtest_dir, "report-1.json", "{not json")
    out = g.collect(evidence)
    row = next(r for r in out["rows"] if r["criterion"].startswith("Scan time"))
    assert row["state"] == "confirm" and "unreadable" in row["evidence"]
