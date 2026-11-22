"""`make eval-live`'s paste block (BLD-C229; V-EVAL, AT-B4-03, AT-B5-04).

`scripts/eval/live.sh` runs `python -m evalrunner --only gatekeeper,judge` on a throwaway database with the real model
route, then this, which reads the reports that run wrote and prints the block the product lead (or KFin IT, in server
mode) pastes back. Numbers and names only: never case text, model output, a key or a URL. Every number comes from the
report JSON (`evalrunner/common.py` `write_report`) and the throwaway database's `llm_calls`, never from the runner's
printed lines; PASS and FAIL are the report's own `model_gates` and `harness_gates`, and the gate values shown are the
agents' `pass_gates` (config.yaml), as `evalrunner/gatekeeper.py` and `judge.py` apply them.

    python -m evalrunner.paste --reports DIR --route anthropic --mode mac --checkout-sha SHA --eval-exit 0

The lead's three rows come first (gatekeeper `personal_data_recall` and `false_block_rate`, judge `same_precision`),
then every other model gate, marked "also gated". The last line is `EVAL-LIVE: PASS` or
`EVAL-LIVE: FAIL (<failed gate names>)`; exit 0 on PASS, 1 on FAIL. It never switches an agent off: people decide
(non-negotiable 5).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

BEGIN = "=== PASTE FROM HERE ==="
END = "=== PASTE TO HERE ==="
DEFAULT_AGENTS = ("gatekeeper", "judge")
LEAD_ROWS = (
    ("gatekeeper", "personal_data_recall"),
    ("gatekeeper", "false_block_rate"),
    ("judge", "same_precision"),
)
# (agent, gate) -> (the pass_gates key in config.yaml, how it compares, the runner's default when the key is absent)
GATES: dict[tuple[str, str], tuple[str | None, str, float]] = {
    ("gatekeeper", "personal_data_recall"): ("personal_data_recall", ">=", 1.0),
    ("gatekeeper", "false_block_rate"): ("false_block_rate_max", "<=", 0.05),
    ("gatekeeper", "kind_accuracy"): ("kind_accuracy_min", ">=", 0.85),
    ("gatekeeper", "injection_held"): (None, "=", 1.0),
    ("judge", "same_precision"): ("same_precision_min", ">=", 0.85),
    ("judge", "same_recall"): ("same_recall_min", ">=", 0.75),
}
IST = dt.timezone(dt.timedelta(hours=5, minutes=30), "IST")


@dataclass
class Calls:
    """The throwaway database's `llm_calls`: rows, the ones that reached the model route, and the gateway's cost."""

    rows: int
    reached_model: int
    cost_inr: float


@dataclass
class Meta:
    mode: str  # mac | server
    route: str
    fast_model: str
    reasoning_model: str
    agents: tuple[str, ...] = DEFAULT_AGENTS
    checkout_sha: str = ""
    checkout_changes: bool = False
    installed_tag: str = ""
    installed_sha: str = ""
    install_before: int | None = None
    install_after: int | None = None
    eval_exit: int = 0
    at: dt.datetime = field(default_factory=lambda: dt.datetime.now(IST))


def _pct(v: Any) -> str:
    return "n/a" if not isinstance(v, int | float) or isinstance(v, bool) else f"{v * 100:.1f}%"


def _gate_text(agent: str, gate: str, pass_gates: dict[str, Any]) -> str:
    key, op, default = GATES.get((agent, gate), (None, "", 0.0))
    if not op:
        return "see config"
    value = pass_gates.get(key, default) if key else default
    return f"{op}{_pct(value)}"


def latest_reports(reports_dir: Path, agents: Sequence[str]) -> dict[str, dict[str, Any]]:
    """The newest report per agent in `reports_dir` (a fresh folder per run, so one each). Only an agent's own
    report counts: `<agent>-<version>-<time>.json` whose body names that agent."""
    found: dict[str, dict[str, Any]] = {}
    for agent in agents:
        for path in sorted(reports_dir.glob(f"{agent}-*.json"), reverse=True):
            body = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(body, dict) and body.get("agent") == agent:
                found[agent] = body
                break
    return found


def verdict(reports: dict[str, dict[str, Any]], meta: Meta) -> list[str]:
    """The failed gate names, in the order the block shows them; empty means PASS."""
    failed: list[str] = []
    for agent in meta.agents:
        r = reports.get(agent)
        if r is None:
            failed.append(f"{agent}.no_report")
            continue
        if r.get("route") != meta.route:
            failed.append(f"{agent}.route_not_{meta.route}")
        failed += [f"{agent}.{g}" for g, ok in (r.get("model_gates") or {}).items() if ok is not True]
        failed += [
            f"{agent}.harness.{g}" for g, ok in (r.get("harness_gates") or {}).items() if ok is not True
        ]
        if not r.get("model_gates") or not r.get("harness_gates"):
            failed.append(f"{agent}.no_gates")
    ordered = [f"{a}.{g}" for a, g in LEAD_ROWS if f"{a}.{g}" in failed]
    failed = ordered + [f for f in failed if f not in ordered]
    if meta.mode == "server" and (
        meta.install_before is None or meta.install_after is None or meta.install_before != meta.install_after
    ):
        failed.append("install.llm_calls_changed")
    if meta.eval_exit != 0 and not failed:
        failed.append(f"evalrunner.exit_{meta.eval_exit}")
    return failed


def render(
    reports: dict[str, dict[str, Any]], pass_gates: dict[str, dict[str, Any]], calls: Calls | None, meta: Meta
) -> tuple[list[str], bool]:
    """The paste block's lines and whether it passed. Reads only names, versions, counts, metrics and gate
    booleans from the reports: a case's rows (`cases`) are never read."""
    out = [BEGIN, "eval-live (BLD-C229): the real-model golden sets on a throwaway database"]
    if meta.mode == "server":
        out.append(f"installed: {meta.installed_tag or 'no tag'} at {meta.installed_sha or 'unknown'}")
    else:
        changes = " with local changes" if meta.checkout_changes else ""
        out.append(f"checkout: {meta.checkout_sha or 'unknown'}{changes}")
    out.append(
        f"route: {meta.route} | fast model: {meta.fast_model} | reasoning model: {meta.reasoning_model}"
    )
    out.append(f"time: {meta.at.astimezone(IST).strftime('%d %b %Y %H:%M')} IST")
    for agent in meta.agents:
        r = reports.get(agent)
        if r is None:
            out.append(f"agent {agent}: no report (the golden set did not finish)")
            continue
        cases = (r.get("metrics") or {}).get("cases")
        out.append(f"agent {agent} {r.get('version', '?')}: {cases if isinstance(cases, int) else '?'} cases")

    rows: list[tuple[str, str, bool]] = [(a, g, True) for a, g in LEAD_ROWS if a in meta.agents]
    for agent in meta.agents:
        for gate in (reports.get(agent) or {}).get("model_gates") or {}:
            if (agent, gate) not in LEAD_ROWS:
                rows.append((agent, gate, False))
    out.append(f"{'gate':<36}{'value':>8}  {'needs':<10}result")
    for agent, gate, lead in rows:
        r = reports.get(agent)
        name = f"{agent} {gate}"
        needs = _gate_text(agent, gate, pass_gates.get(agent, {}))
        if r is None:
            out.append(f"{name:<36}{'-':>8}  {needs:<10}FAIL (no report)")
            continue
        ok = (r.get("model_gates") or {}).get(gate)
        value = _pct((r.get("metrics") or {}).get(gate))
        result = "PASS" if ok is True else "FAIL"
        out.append(f"{name:<36}{value:>8}  {needs:<10}{result}{'' if lead else '  also gated'}")

    harness = []
    for agent in meta.agents:
        gates = (reports.get(agent) or {}).get("harness_gates") or {}
        if not gates:
            harness.append(f"{agent} none")
            continue
        bad = [g for g, ok in gates.items() if ok is not True]
        harness.append(
            f"{agent} {len(gates) - len(bad)}/{len(gates)} PASS"
            + (f" ({', '.join(bad)} FAIL)" if bad else "")
        )
    out.append("harness gates: " + " | ".join(harness))
    if calls is None:
        out.append("model calls: not counted")
    else:
        out.append(
            f"model calls: {calls.reached_model} (llm_calls rows: {calls.rows}) | cost: INR {calls.cost_inr:.2f}"
        )
    if meta.mode == "server":
        if meta.install_before is not None and meta.install_before == meta.install_after:
            out.append(f"install database: llm_calls unchanged ({meta.install_before})")
        else:
            before = "?" if meta.install_before is None else meta.install_before
            after = "?" if meta.install_after is None else meta.install_after
            out.append(f"install database: llm_calls CHANGED ({before} to {after})")
    failed = verdict(reports, meta)
    out.append("EVAL-LIVE: PASS" if not failed else f"EVAL-LIVE: FAIL ({', '.join(failed)})")
    out.append(END)
    return out, not failed


def count_calls() -> Calls:
    """The throwaway database's model calls (DATABASE_URL): `llm_calls` rows, the ones that reached the route (not
    switched off, leak-aborted or cached), and the gateway's own cost in INR."""
    from core.db import connect

    with connect(autocommit=True) as conn:
        row = conn.execute(
            "SELECT count(*) AS n, "
            "count(*) FILTER (WHERE outcome NOT IN ('switched_off', 'leak_abort', 'cached')) AS reached, "
            "coalesce(sum(cost_inr), 0) AS cost FROM llm_calls"
        ).fetchone()
    assert row is not None
    return Calls(rows=int(row["n"]), reached_model=int(row["reached"]), cost_inr=float(row["cost"]))


def _gates_of(agent: str) -> dict[str, Any]:
    from gateway.spec import load

    gates = load(agent).raw.get("pass_gates") or {}
    return dict(gates) if isinstance(gates, dict) else {}


def main(argv: list[str] | None = None) -> int:
    from core.config import get_settings

    p = argparse.ArgumentParser(description="make eval-live's paste block (BLD-C229)")
    p.add_argument("--reports", type=Path, required=True)
    p.add_argument("--route", required=True, choices=["anthropic", "bedrock"])
    p.add_argument("--mode", required=True, choices=["mac", "server"])
    p.add_argument("--agents", default=",".join(DEFAULT_AGENTS))
    p.add_argument("--checkout-sha", default="")
    p.add_argument("--checkout-changes", action="store_true")
    p.add_argument("--installed-tag", default="")
    p.add_argument("--installed-sha", default="")
    p.add_argument("--install-before", type=int)
    p.add_argument("--install-after", type=int)
    p.add_argument("--eval-exit", type=int, default=0)
    args = p.parse_args(argv)
    s = get_settings()
    agents = tuple(a.strip() for a in args.agents.split(",") if a.strip())
    meta = Meta(
        mode=args.mode,
        route=args.route,
        fast_model=s.llm_fast_model,
        reasoning_model=s.llm_reasoning_model,
        agents=agents,
        checkout_sha=args.checkout_sha,
        checkout_changes=args.checkout_changes,
        installed_tag=args.installed_tag,
        installed_sha=args.installed_sha,
        install_before=args.install_before,
        install_after=args.install_after,
        eval_exit=args.eval_exit,
    )
    reports = latest_reports(args.reports, agents)
    lines, passed = render(reports, {a: _gates_of(a) for a in agents}, count_calls(), meta)
    print("\n".join(lines))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
