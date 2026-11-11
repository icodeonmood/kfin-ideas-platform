"""Load `rules/*.md` and `comms/rules.md` from the company repo, validate each against its schema.

Each rule file has a short explanation and exactly one fenced ```yaml block (§3.4). The loader parses that
block, validates it against `rules/schemas/<name>.schema.json`, then runs semantic checks a schema cannot
express (weights that must sum to 100, bands that must be contiguous). A missing or broken rule raises
`RulesConfigError`; callers never guess a value (plan P1).

Past versions stay replayable: pass `ref` (a commit SHA) to read a rule as it was at that commit.

Usage: python -m rules check <repo-dir> [--ref <sha>]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from functools import cache
from itertools import pairwise
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from okf.frontmatter import FrontmatterError, parse

SCHEMAS = Path(__file__).with_name("schemas")
YAML_BLOCK = re.compile(r"^```yaml[ \t]*\n(.*?)^```[ \t]*$", re.DOTALL | re.MULTILINE)

# rule name -> path inside the company repo
RULE_PATHS: dict[str, str] = {
    "calendar": "rules/calendar.md",
    "compliance-tier": "rules/compliance-tier.md",
    "points": "rules/points.md",
    "priority": "rules/priority.md",
    "reason-codes": "rules/reason-codes.md",
    "redirects": "rules/redirects.md",
    "routing": "rules/routing.md",
    "scorecard": "rules/scorecard.md",
    "sla": "rules/sla.md",
    "thresholds": "rules/thresholds.md",
    "comms": "comms/rules.md",
}


class RulesConfigError(Exception):
    """A rule file is missing, unparseable or invalid. The message names the file and the problem."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("; ".join(problems))


@dataclass(frozen=True)
class RuleFile:
    name: str
    path: str
    version: str  # kfin.version in the frontmatter: the version decisions record
    block_version: str  # `version` inside the yaml block
    data: dict[str, Any]
    ref: str | None


@cache
def _validator(name: str) -> Draft202012Validator:
    schema = json.loads((SCHEMAS / f"{name}.schema.json").read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def _stringify_keys(obj: Any) -> Any:
    """YAML gives int keys (scorecard bands); JSON Schema expects strings."""
    if isinstance(obj, dict):
        return {str(k): _stringify_keys(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_stringify_keys(v) for v in obj]
    return obj


def _read(repo: Path, rel: str, ref: str | None) -> str:
    if ref is None:
        return (repo / rel).read_text(encoding="utf-8")
    out = subprocess.run(
        ["git", "-C", str(repo), "show", f"{ref}:{rel}"], capture_output=True, text=True, check=False
    )
    if out.returncode != 0:
        raise FileNotFoundError(rel)
    return out.stdout


def _semantic(name: str, data: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if name == "scorecard":
        total = sum(d["weight"] for d in data["dimensions"].values())
        if total != 100:
            problems.append(f"dimension weights sum to {total}, not 100")
        bands = [data["financial_bands_inr_per_year"][str(i)] for i in range(1, 6)]
        if bands[0][0] is not None or bands[-1][1] is not None:
            problems.append("financial bands must start and end open (null)")
        for lower, upper in pairwise(bands):
            if lower[1] != upper[0]:
                problems.append("financial bands must be contiguous")
                break
    elif name == "priority":
        total = sum(data["weights"].values())
        if total != 100:
            problems.append(f"priority weights sum to {total}, not 100")
        spans = sorted((lo, hi) for lo, hi in data["classes"].values())
        if spans[0][0] != 0 or spans[-1][1] != 100:
            problems.append("priority classes must cover 0 to 100")
        for (_, hi), (lo, _) in pairwise(spans):
            if hi != lo:
                problems.append("priority classes must be contiguous")
                break
    elif name == "thresholds":
        auto = data["autonomy"]
        if auto["demote_below"] >= auto["promote_at"]:
            problems.append("autonomy.demote_below must be below autonomy.promote_at")
        if data["match"]["final_k"] > data["match"]["top_k_each"]:
            problems.append("match.final_k cannot exceed match.top_k_each")
        ids = [a["id"] for a in data.get("assumptions") or []]
        if len(ids) != len(set(ids)):
            problems.append("assumptions: each id may appear only once")
    elif name == "calendar":
        for h in data["holidays"]:
            try:
                date.fromisoformat(h["date"])
            except ValueError:
                problems.append(f"holiday date {h['date']} is not a real date")
    elif name == "reason-codes":
        codes = [c["code"] for c in data["codes"]]
        if len(codes) != len(set(codes)):
            problems.append("reason codes must be unique")
    elif name == "sla":
        for key, spec in data.items():
            if key != "version" and not ({"limit_wd", "limit_days", "due_wd_before_session"} & set(spec)):
                problems.append(f"{key} has no limit")
    return problems


def load_rule(repo: Path, name: str, ref: str | None = None) -> RuleFile:
    if name not in RULE_PATHS:
        raise RulesConfigError([f"unknown rule {name}"])
    rel = RULE_PATHS[name]
    try:
        text = _read(repo, rel, ref)
    except FileNotFoundError:
        raise RulesConfigError([f"{rel}: missing"]) from None
    try:
        doc = parse(text)
    except FrontmatterError as exc:
        raise RulesConfigError([f"{rel}: {exc}"]) from None
    meta = doc.meta or {}
    if meta.get("type") != "rule":
        raise RulesConfigError([f"{rel}: frontmatter type must be 'rule'"])
    blocks = YAML_BLOCK.findall(doc.body)
    if len(blocks) != 1:
        raise RulesConfigError([f"{rel}: expected exactly one ```yaml block, found {len(blocks)}"])
    try:
        data = yaml.safe_load(blocks[0])
    except yaml.YAMLError as exc:
        raise RulesConfigError([f"{rel}: yaml block does not parse ({exc.__class__.__name__})"]) from None
    if not isinstance(data, dict):
        raise RulesConfigError([f"{rel}: yaml block must be a mapping"])
    data = _stringify_keys(data)
    problems = [
        f"{rel}: {'.'.join(str(p) for p in e.path) or '(root)'}: {e.message}"
        for e in sorted(_validator(name).iter_errors(data), key=lambda e: list(e.path))
    ]
    if not problems:
        problems = [f"{rel}: {p}" for p in _semantic(name, data)]
    if problems:
        raise RulesConfigError(problems)
    kfin = meta.get("kfin") or {}
    return RuleFile(
        name=name,
        path=rel,
        version=str(kfin.get("version", "")),
        block_version=str(data.get("version", "")),
        data=data,
        ref=ref,
    )


def load_all(repo: Path, ref: str | None = None) -> dict[str, RuleFile]:
    """Every rule, or one RulesConfigError listing every problem across files."""
    loaded: dict[str, RuleFile] = {}
    problems: list[str] = []
    for name in RULE_PATHS:
        try:
            loaded[name] = load_rule(repo, name, ref)
        except RulesConfigError as exc:
            problems.extend(exc.problems)
    if problems:
        raise RulesConfigError(problems)
    return loaded


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the rule files of a company repo.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    check = sub.add_parser("check")
    check.add_argument("repo", type=Path)
    check.add_argument("--ref", default=None)
    args = parser.parse_args(argv)
    try:
        rules = load_all(args.repo, args.ref)
    except RulesConfigError as exc:
        for p in exc.problems:
            print(f"CONFIG ERROR {p}")
        return 1
    for r in rules.values():
        print(f"ok  {r.path:28} version {r.version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
