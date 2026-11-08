"""`make eval` (B4): the golden sets run through the production pipeline; harness gates always apply, the
agents' pass gates and the regression check only on a real route (BLD-076). AT-B4-03/07/08 numbers come from
the real route in UAT; here the runner itself is tested."""

from __future__ import annotations

import json
import random
from typing import Any, cast

import pytest

from core.db import connect
from evalrunner import __main__ as main_mod
from evalrunner import canvas_assist, common, gatekeeper


def result(agent: str = "gatekeeper", **metrics: Any) -> dict[str, Any]:
    return {
        "agent": agent,
        "metrics": {"personal_data_recall": 1.0, "kind_accuracy": 0.9, **metrics},
        "model_gates": {
            "personal_data_recall": True,
            "kind_accuracy": metrics.get("kind_accuracy", 0.9) >= 0.85,
        },
        "harness_gates": {"no_errors": True},
    }


def test_fake_route_enforces_the_harness_only() -> None:
    weak = result(kind_accuracy=0.4)
    assert main_mod._verdict(weak, "fake") == (True, [])
    assert main_mod._verdict(weak, "anthropic") == (False, ["gate:kind_accuracy"])
    broken = {**result(), "harness_gates": {"no_errors": False}}
    assert main_mod._verdict(broken, "fake") == (False, ["harness:no_errors"])


def test_a_drop_against_the_last_passing_report_is_a_regression(tmp_path: Any, monkeypatch: Any) -> None:
    monkeypatch.setattr(common, "REPORTS", tmp_path)
    old = {**result(kind_accuracy=0.95), "route": "anthropic", "passed": True}
    (tmp_path / "gatekeeper-0.1.0-20261101-000000.json").write_text(json.dumps(old))
    ok, failed = main_mod._verdict(result(kind_accuracy=0.9), "anthropic")
    assert not ok and failed == ["regression:kind_accuracy"]
    assert main_mod._verdict(result(kind_accuracy=0.96), "anthropic") == (True, [])
    assert main_mod._verdict(result(kind_accuracy=0.9), "bedrock") == (True, [])  # other route: no baseline


def test_golden_tags_become_consistent_synthetic_values() -> None:
    ctx = common.Context(
        conn=cast(Any, None),
        rng=random.Random(1),
        colleagues=["Meera Iyer"],
        clients=["Northwind Mutual Fund"],
    )
    out = ctx.fill({"x": "[[CLIENT_AMC_1]] asked [[KFIN_EMPLOYEE_1]]; [[CLIENT_AMC_1]] again. PAN {{PAN}}"})[
        "x"
    ]
    assert out.startswith("Northwind Mutual Fund asked Meera Iyer; Northwind Mutual Fund again. PAN ")
    assert "[[" not in out and "{{" not in out


@pytest.mark.stack
def test_both_golden_sets_run_and_the_harness_holds() -> None:
    with connect(autocommit=True) as conn:
        ctx = common.context(conn, 42)
        try:
            gk = gatekeeper.run(ctx)
            ca = canvas_assist.run(ctx)
        finally:
            ctx.cleanup()
        assert gk["metrics"]["cases"] >= 32 and all(gk["harness_gates"].values()), gk["harness_gates"]
        assert (
            gk["metrics"]["pattern_layer_recall"] == 1.0 and gk["metrics"]["pattern_layer_false_blocks"] == 0
        )
        assert all(ca["harness_gates"].values()), ca["harness_gates"]
        left = conn.execute(
            "SELECT count(*) AS n FROM pseudonym_vault WHERE scope_id = ANY(%s)", (ctx.scopes,)
        )
        assert left.fetchone()["n"] == 0  # eval scopes are cleaned up
