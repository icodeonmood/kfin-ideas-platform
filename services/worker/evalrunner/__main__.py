"""`make eval` — golden-set harness. Until the gateway exists (B4) this checks the harness, not the agents:

- every golden case parses and every {{PLACEHOLDER}} has a generator (eval/golden/generators.py);
- every agent folder has prompt.md, schema.json, config.yaml, examples/ and CHANGELOG.md;
- every example's `output` validates against the agent's schema (what LLM_MODE=fake will return);
- every example named in config.yaml exists.

Exit 0 = harness healthy. Agent scores and pass gates arrive with run_agent in B4.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from core.config import REPO_ROOT

ROOT = REPO_ROOT or Path.cwd()
sys.path.insert(0, str(ROOT / "eval" / "golden"))
generators = importlib.import_module("generators")
GOLDEN = ROOT / "eval" / "golden"
AGENTS = ROOT / "agents"


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


def main() -> int:
    problems = check_golden() + check_agents()
    for p in problems:
        print(f"EVAL HARNESS  {p}")
    cases = sum(1 for p in GOLDEN.glob("*.jsonl") for line in p.read_text().splitlines() if line.strip())
    agents = sum(1 for p in AGENTS.iterdir() if p.is_dir())
    print(f"eval harness: {cases} golden cases, {agents} agents, {len(problems)} problems")
    print("agent scores: not run until the gateway exists (B4)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
