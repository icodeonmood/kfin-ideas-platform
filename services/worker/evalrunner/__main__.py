"""`make eval` — golden sets for every agent (§5.5). First the harness checks:

- every golden case parses and every {{PLACEHOLDER}} has a generator (eval/golden/generators.py);
- every agent folder has prompt.md, schema.json, config.yaml, examples/ and CHANGELOG.md;
- every example's `output` validates against the agent's schema (what LLM_MODE=fake will return);
- every example named in config.yaml exists.

Then each agent's golden set runs through the production pipeline (`evalrunner/gatekeeper.py`,
`evalrunner/canvas_assist.py`) and writes `eval/reports/<agent>-<version>-<time>.json`. Harness gates always
apply; the agents' pass gates and the regression check apply on a real route (UAT), because fake mode cannot
measure a model (BLD-076). Exit 0 = everything that applies passed.

`--only gatekeeper,judge` runs just the named agents' golden sets, in the usual order (BLD-C229: `make eval-live`); the
harness checks above still run first, a name that is not an agent here stops the run before anything else, and the
speech set (DEC-096) is left out. Without `--only` nothing changes.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from core.config import REPO_ROOT

ROOT = REPO_ROOT or Path.cwd()
sys.path.insert(0, str(ROOT / "eval" / "golden"))
generators = importlib.import_module("generators")
GOLDEN = ROOT / "eval" / "golden"
AGENTS = ROOT / "agents"
# The golden sets in the order `run_agents` runs them; `--only` picks from these names (BLD-C229).
AGENT_ORDER = (
    "gatekeeper",
    "canvas-assist",
    "draft-part",
    "judge",
    "cluster-summary",
    "attachment-digest",
    "handover-draft",
    "role-themes",
    "prescore",
    "pitch-prep",
    "collation",
    "reason-writer",
)


def select_agents(only: str | None) -> tuple[str, ...]:
    """The agents to run: every one without `--only`; otherwise the comma list's names in the usual order. A name
    that is not in AGENT_ORDER, or an empty list, is a ValueError naming what was given and what is known."""
    if only is None:
        return AGENT_ORDER
    names = [n.strip() for n in only.split(",") if n.strip()]
    unknown = sorted(set(names) - set(AGENT_ORDER))
    if not names or unknown:
        raise ValueError(
            f"--only takes agent names from this list: {', '.join(AGENT_ORDER)}"
            + (f" (not agents here: {', '.join(unknown)})" if unknown else " (none given)")
        )
    return tuple(a for a in AGENT_ORDER if a in names)


def check_golden() -> list[str]:
    problems: list[str] = []
    known = set(generators.GENERATORS) | set(generators.CONTEXT_PLACEHOLDERS)
    for path in sorted(GOLDEN.glob("*.jsonl")):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                case = json.loads(line)
            except ValueError:
                problems.append(f"{path.name}:{n}: not valid JSON")
                continue
            missing = generators.placeholders(line) - known
            if missing:
                problems.append(f"{path.name}:{n} ({case.get('id')}): no generator for {sorted(missing)}")
    return problems


def check_agents() -> list[str]:
    problems: list[str] = []
    for agent in sorted(p for p in AGENTS.iterdir() if p.is_dir()):
        for required in ("prompt.md", "schema.json", "config.yaml", "CHANGELOG.md", "examples"):
            if not (agent / required).exists():
                problems.append(f"{agent.name}: missing {required}")
        if problems and problems[-1].startswith(agent.name):
            continue
        validator = Draft202012Validator(json.loads((agent / "schema.json").read_text(encoding="utf-8")))
        config = yaml.safe_load((agent / "config.yaml").read_text(encoding="utf-8"))
        for name in [*config.get("examples_in_prompt", []), config.get("fake_mode_default")]:
            if name and not (agent / "examples" / name).exists():
                problems.append(f"{agent.name}: config names example {name}, which does not exist")
        for example in sorted((agent / "examples").glob("*.json")):
            data = json.loads(example.read_text(encoding="utf-8"))
            errors = list(validator.iter_errors(data.get("output", {})))
            if errors:
                problems.append(
                    f"{agent.name}/{example.name}: output fails schema ({errors[0].message[:80]})"
                )
    return problems


def _verdict(result: dict[str, Any], route: str) -> tuple[bool, list[str]]:
    """Harness gates always; model gates and the regression check only on a real route (fake mode measures
    the harness, not the agent)."""
    from evalrunner.common import last_passing

    failed = [f"harness:{k}" for k, ok in result["harness_gates"].items() if not ok]
    if route != "fake":
        failed += [f"gate:{k}" for k, ok in result["model_gates"].items() if not ok]
        before = last_passing(result["agent"], route)
        if before:
            for key in result["model_gates"]:
                old, new = before["metrics"].get(key), result["metrics"].get(key)
                lower_is_better = key.endswith("rate") and "block" in key
                if old is not None and new is not None and (new > old if lower_is_better else new < old):
                    failed.append(f"regression:{key}")
    return not failed, failed


def _pct(v: Any) -> str:
    return "n/a" if v is None else f"{v * 100:.0f}%"


def switch_off_failing(conn: Any, results: list[dict[str, Any]], route: str) -> list[str]:
    """§7.6: an agent whose golden set fails or regresses on deploy switches itself off (audited). Only on a real
    route; fake mode measures the harness, not the agent. Returns the switches turned off."""
    from core.watch import switch_off

    if route == "fake":
        return []
    names = []
    for r in results:
        if not r["passed"] and switch_off(
            conn,
            f"agent.{r['agent']}",
            "Golden set failed or regressed on deploy (automatic)",
            actor="process:eval",
        ):
            names.append(f"agent.{r['agent']}")
    return names


def run_agents(seed: int, switch_off: bool = False, only: tuple[str, ...] = AGENT_ORDER) -> int:
    from types import SimpleNamespace

    from core.db import connect
    from evalrunner import (
        attachment_digest,
        canvas_assist,
        cluster_summary,
        committee,
        draft_part,
        gatekeeper,
        handover_draft,
        judge,
        prescore,
        role_themes,
    )
    from evalrunner.common import context, route_name, write_report

    route = route_name()
    status = 0
    results: list[dict[str, Any]] = []
    runners: tuple[tuple[Any, str], ...] = (
        (gatekeeper, "gatekeeper"),
        (canvas_assist, "canvas-assist"),
        (draft_part, "draft-part"),
        (judge, "judge"),
        (cluster_summary, "cluster-summary"),
        (attachment_digest, "attachment-digest"),
        (handover_draft, "handover-draft"),
        (role_themes, "role-themes"),
        (prescore, "prescore"),
        (SimpleNamespace(run=committee.run_pitch_prep), "pitch-prep"),
        (SimpleNamespace(run=committee.run_collation), "collation"),
        (SimpleNamespace(run=committee.run_reason_writer), "reason-writer"),
    )
    assert tuple(agent for _, agent in runners) == AGENT_ORDER  # `--only` names stay the runners' names
    with connect(autocommit=True) as conn:
        ctx = context(conn, seed)
        try:
            for runner, agent in runners:
                if agent not in only:
                    continue
                try:
                    result = runner.run(ctx)
                except (
                    Exception
                ) as exc:  # a crash is a failure for that agent; the others still run (B8 review)
                    print(f"{agent}: the golden set could not run ({type(exc).__name__})")
                    results.append({"agent": agent, "passed": False})
                    status = 1
                    continue
                passed, failed = _verdict(result, route)
                result.update({"route": route, "seed": seed, "passed": passed, "failed": failed})
                path = write_report(result["agent"], result["version"], result)
                m = result["metrics"]
                if result["agent"] == "gatekeeper":
                    detail = (
                        f"personal-data recall {_pct(m['personal_data_recall'])} · false blocks "
                        f"{_pct(m['false_block_rate'])} · kind accuracy {_pct(m['kind_accuracy'])} · pattern layer "
                        f"{_pct(m['pattern_layer_recall'])}"
                    )
                elif result["agent"] == "judge":
                    detail = (
                        f"{m['labels']} labels · same precision {_pct(m['same_precision'])} · same recall "
                        f"{_pct(m['same_recall'])} · labelled {_pct(m['labelled_share'])}"
                    )
                elif result["agent"] == "canvas-assist":
                    detail = (
                        f"submitter changes {m['submitter_field_changes']} · out-of-slice IDs {m['out_of_slice_ids']} "
                        f"· summary leaks {m['neutral_summary_leaks']} · area tags {_pct(m['area_tag_accuracy'])} "
                        f"· unquoted {m['ungrounded_suggestions']} · dropped {m['suggestions_dropped']}"
                    )
                else:  # newer agents: every metric, in order
                    detail = " · ".join(
                        f"{k.replace('_', ' ')} {_pct(v) if isinstance(v, float) else v}"
                        for k, v in m.items()
                        if k != "cases"
                    )
                note = "" if route != "fake" else " (fake route: model gates reported, not enforced)"
                print(
                    f"{result['agent']} {result['version']} [{route}]: {m['cases']} cases · {detail} · "
                    f"{'PASS' if passed else 'FAIL ' + ', '.join(failed)}{note}"
                )
                print(f"  report: {path}")
                status |= 0 if passed else 1
                results.append(result)
            if switch_off:
                for name in switch_off_failing(conn, results, route):
                    print(f"  switched off: {name}")
        finally:
            ctx.cleanup()
    return status


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Golden sets for every agent")
    parser.add_argument("--seed", type=int, default=int(os.environ.get("GOLDEN_SEED", "42")))
    parser.add_argument("--harness-only", action="store_true")
    parser.add_argument(
        "--switch-off-failing",
        action="store_true",
        help="on deploy: switch off agents that fail (real route only)",
    )
    parser.add_argument(
        "--only",
        metavar="AGENTS",
        help="comma list of agents to run, for example gatekeeper,judge (the harness checks still run; BLD-C229)",
    )
    args = parser.parse_args(argv)
    try:
        only = select_agents(args.only)
    except ValueError as exc:
        parser.error(str(exc))  # exits 2 before the harness checks or any database
    problems = check_golden() + check_agents()
    for p in problems:
        print(f"EVAL HARNESS  {p}")
    cases = sum(1 for p in GOLDEN.glob("*.jsonl") for line in p.read_text().splitlines() if line.strip())
    agents = sum(1 for p in AGENTS.iterdir() if p.is_dir())
    print(f"eval harness: {cases} golden cases, {agents} agents, {len(problems)} problems")
    if problems:
        return 1
    if args.harness_only:
        return 0
    status = run_agents(args.seed, switch_off=args.switch_off_failing, only=only)
    if args.only is not None:
        return status  # the named agents only: the speech set is not an agent (BLD-C229)
    from evalrunner import speech  # voice notes (DEC-096): runs only with SPEECH_MODE=local

    return status or speech.run()


if __name__ == "__main__":
    sys.exit(main())
