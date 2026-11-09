"""The handover-draft agent (BLD-138): values only from the options, numbers only when a member gave them, an
objective only on the fix track; it proposes and nothing is saved. Synthetic text only."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from gateway import checks, fakes
from gateway.spec import load
from tests import test_delivery
from tests.test_delivery import started
from tests.test_ones import refused

ones_db = test_delivery.ones_db
cast = test_delivery.cast
crew = test_delivery.crew
GOLDEN = Path(__file__).resolve().parents[3] / "eval" / "golden" / "handover_draft.jsonl"


def _cases() -> list[dict[str, Any]]:
    return [json.loads(line) for line in GOLDEN.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_examples_and_fake_outputs_pass_the_schema_and_the_checks() -> None:
    spec = load("handover-draft")
    schema = json.loads(
        (Path(__file__).resolve().parents[3] / "agents" / "handover-draft" / "schema.json").read_text()
    )
    for ex in spec.examples:
        jsonschema.validate(ex.output, schema)
        assert checks.run("handover-draft", ex.input, ex.output, None) == []
    for case in _cases():
        out = fakes.output_for(spec, case["input"])
        jsonschema.validate(out, schema)
        assert checks.run("handover-draft", case["input"], out, None) == [], case["id"]


def test_the_checks_refuse_invented_numbers_odd_values_and_a_misplaced_objective() -> None:
    case = _cases()[0]  # build track; the member gave "6 minutes"
    good = fakes.output_for(load("handover-draft"), case["input"])
    assert checks.run("handover-draft", case["input"], {**good, "baseline": 6}, None) == []
    bad = {**good, "target": 2, "unit": "widgets a week", "objective": "Faster mandate checks for everyone."}
    problems = " ".join(checks.run("handover-draft", case["input"], bad, None))
    assert "target must be a number a member gave" in problems
    assert "unit must be one of options.units" in problems
    assert "objective is for the fix track only" in problems
    tagged = {**good, "metric": "Minutes [[CLIENT_AMC_1]] spends per form"}
    assert any("tags" in p for p in checks.run("handover-draft", case["input"], tagged, None))


@pytest.mark.stack
def test_only_the_editors_get_a_draft_and_nothing_is_saved(ones_db: Any, crew: dict[str, str]) -> None:
    from delivery import pack_draft, service

    db = ones_db
    _idea, did = started(db, crew)
    db.execute("UPDATE deliveries SET state = 'drafting' WHERE id = %s", (did,))
    refused("owner_only", pack_draft.draft, db, crew["submitter"], did)
    before = db.execute("SELECT pack, metric_encrypted FROM deliveries WHERE id = %s", (did,)).fetchone()
    out = pack_draft.draft(db, crew["member"], did)
    assert out["unit"] in service.METRIC_UNITS and out["objective"] is None  # a build
    after = db.execute("SELECT pack, metric_encrypted FROM deliveries WHERE id = %s", (did,)).fetchone()
    assert dict(before) == dict(after)  # it proposes; people decide
    audit = db.execute(
        "SELECT after FROM audit_log WHERE action = 'delivery.pack_drafted' AND entity = %s",
        (f"delivery:{did}",),
    ).fetchone()
    assert audit is not None and set(audit["after"]) == {"members"}
