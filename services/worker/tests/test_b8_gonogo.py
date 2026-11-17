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
    # Voice is on at launch through Sarvam (DEC-108): the evidence of a ready launch includes the route, the approval
    # and a key (a synthetic one here; the report says present or absent, never the value).
    ready = Settings(
        privacy_notice_version="1.0",
        speech_mode="sarvam",
        speech_hosted_approval="DEC-108",
        sarvam_api_key="synthetic-test-key",
    )
    monkeypatch.setattr(g, "get_settings", lambda: ready)
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
        since="2100-01-01", launch="2100-01-01", vapt_open_high=0, sso_ready="yes", reports_dir=tmp_path / "eval",
        loadtest_dir=tmp_path / "load", drill_dir=tmp_path / "ops",
    )  # fmt: skip


def test_mode_a_needs_every_criterion(evidence: argparse.Namespace) -> None:
    out = g.collect(evidence)
    assert out["mode"] == "A. Full, once every 'confirm' row is confirmed"  # the CI row is always a person's
    # the CI row is always a person's; voice is on from migration 20261122300530 (BLD-C115) and the evidence above
    # carries the Sarvam route, the approval and a key, so both voice rows are met
    assert [(r["criterion"], r["state"]) for r in out["rows"] if r["state"] != "met"] == [
        ("Every B1–B7 acceptance test passes in UAT", "confirm"),
    ]
    assert {r["criterion"]: r["state"] for r in out["rows"]}[g.VOICE] == "met"


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


def test_canvas_assist_dropped_and_refused_shares_are_printed(evidence: argparse.Namespace) -> None:
    """DEC-095, BLD-C029: counts only, live calls apart from golden-set runs (DRAFT- scopes)."""
    from core.db import connect

    rows = [("IDEA-2100-000001", "ok", None), ("IDEA-2100-000002", "ok_after_retry", "ungrounded_dropped"),
            ("IDEA-2100-000003", "agent_failed", "invalid_output"), ("IDEA-2100-000004", "ok", None),
            ("DRAFT-gonogo-test", "ok_after_retry", "ungrounded_dropped")]  # fmt: skip
    with connect(autocommit=True) as conn:
        for ref, outcome, code in rows:
            conn.execute(
                "INSERT INTO llm_calls (agent, prompt_version, model, outcome, ref_id, error_code, created_at) "
                "VALUES ('canvas-assist', '0.4.0', 'test', %s, %s, %s, '2100-01-02')",
                (outcome, ref, code),
            )
        try:
            out = g.collect(evidence)
            since_launch = next(w for w in out["canvas_assist"] if w["window"].startswith("since launch"))
            assert (since_launch["asked"], since_launch["dropped"], since_launch["invalid"]) == (4, 1, 1)
            golden = next(w for w in out["canvas_assist"] if w["window"].startswith("golden-set"))
            assert (golden["asked"], golden["dropped"]) == (1, 1)
            text = g.render(out)
            assert "| since launch (2100-01-01) | 4 | 1 of 4 (25%) | 1 of 4 (25%) |" in text
            assert "last 24 hours" in text
            assert out["mode"] == "A. Full, once every 'confirm' row is confirmed"  # a watch, not a criterion
        finally:
            conn.execute("DELETE FROM llm_calls WHERE created_at = '2100-01-02' AND agent = 'canvas-assist'")
