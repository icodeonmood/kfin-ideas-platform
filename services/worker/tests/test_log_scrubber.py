"""AT-B1-10: the log-scrubber test fails on a field named like idea text or any personal-data pattern.

Two halves: (1) the checker finds every planted violation and passes clean lines; (2) the logger itself
refuses free text and personal data. A third check, over every log line emitted during the whole test run,
lives in conftest.py (`pytest_sessionfinish`).
"""

import io
import json
import random
from collections.abc import Callable

import generators as g
import pytest

from core import logging as klog
from pii.log_rules import scan_log_line, scan_log_lines


@pytest.mark.parametrize(
    "field",
    [
        "one_line",
        "details",
        "idea_text",
        "canvas",
        "neutral_summary",
        "original_text",
        "prompt",
        "response",
        "name",
        "email",
    ],
)
def test_checker_flags_text_like_fields(field: str) -> None:
    line = json.dumps({"event": "scan.done", field: "x", "idea_id": "IDEA-2026-000001"})
    assert any(v.kind == "field" for v in scan_log_line(line))


@pytest.mark.parametrize("maker", [g.pan, g.aadhaar, g.mobile, g.ext_email, g.card])
def test_checker_flags_personal_data_values(maker: Callable[[random.Random], str]) -> None:
    value = maker(g.default_rng(3))
    json_line = json.dumps({"event": "x.y", "error_type": f"failed near {value}"})
    raw_line = f"Traceback: something about {value} broke"
    assert any(v.kind == "pattern" for v in scan_log_line(json_line))
    assert any(v.kind == "pattern" for v in scan_log_line(raw_line))


def test_checker_passes_clean_lines() -> None:
    lines = [
        json.dumps({"event": "repo_writer.committed", "outbox_id": 42, "commit_sha": "9b1f0c2a" * 5}),
        json.dumps(
            {"event": "indexer.upserted", "repo_path": "ideas/2026/11/IDEA-2026-000142.md", "chunk_count": 1}
        ),
        json.dumps(
            {"event": "killswitch.changed", "switch": "submissions", "state": "off", "reason_code": "LEAK"}
        ),
    ]
    assert scan_log_lines(lines) == []


def test_checker_flags_free_text_event_names() -> None:
    assert any(
        v.kind == "event_name" for v in scan_log_line(json.dumps({"event": "Saved the idea: SIP forms slow"}))
    )


def test_logger_refuses_text_fields_in_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    log = klog.get_logger("t")
    with pytest.raises(klog.LogPolicyError):
        log.info("scan.done", details="the idea body")
    with pytest.raises(klog.LogPolicyError):
        log.info("scan.done", error_ref=f"PAN {g.pan(g.default_rng())}")
    with pytest.raises(klog.LogPolicyError):
        log.info("This is a sentence, not an event")


def test_logger_drops_text_fields_in_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    stream = io.StringIO()
    klog.configure("INFO", stream)
    try:
        klog.get_logger("t").info("scan.done", idea_id="IDEA-2026-000001", one_line="Slow SIP forms")
    finally:
        klog.configure("INFO")
    line = stream.getvalue().strip()
    data = json.loads(line)
    assert data["dropped_fields"] == ["one_line"]
    assert "one_line" not in data
    assert scan_log_line(line) == []


def test_third_party_messages_are_not_logged() -> None:
    import logging

    stream = io.StringIO()
    klog.configure("INFO", stream)
    try:
        logging.getLogger("uvicorn.error").info("Started server for %s", "someone@example.com")
    finally:
        klog.configure("INFO")
    data = json.loads(stream.getvalue().strip())
    assert data["event"] == "external.uvicorn.error"
    assert "example.com" not in stream.getvalue()


def test_hashes_and_coded_ids_are_not_personal_data() -> None:
    """Regression: a commit SHA with a 10-digit run starting 6-9 once tripped the mobile pattern."""
    sha = "4cda907afa77" + "9" + "123456789" + "0ff112c308a468c2d3"  # 40 hex chars, built at run time
    assert len(sha) == 40
    for safe in (sha, "IDEA-2026-000142", "CTR-7f3a91", "REV-0007", "ATT-2026-000311"):
        assert scan_log_line(json.dumps({"event": "x.y", "ref": safe})) == [], safe
    bare_mobile = g.mobile(g.default_rng(11)).replace(" ", "").replace("+91", "")
    assert any(v.kind == "pattern" for v in scan_log_line(json.dumps({"event": "x.y", "ref": bare_mobile})))


def test_uncaught_exceptions_log_the_type_only() -> None:
    import subprocess
    import sys

    code = (
        "from core.logging import get_logger; get_logger('t'); "
        "raise ValueError('Failing row contains (SIP forms are slow, someone@example.com)')"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert out.returncode == 1
    combined = out.stdout + out.stderr
    assert "SIP forms" not in combined and "example.com" not in combined
    assert '"error_type":"ValueError"' in combined


def test_row_uuids_with_digit_runs_are_safe_values() -> None:
    """A random UUID can contain a run like 998877665544 (a phone-shaped number); it is an ID, not personal data."""
    from pii.log_rules import scan_log_line

    line = '{"event":"scan.saved","idea_uuid":"1b2c3d4e-5f60-4a1b-9c2d-998877665544"}'
    assert list(scan_log_line(line, 1)) == []
