"""Shared pieces for the golden-set runs: fixed-seed values, re-identifying pre-tagged golden text with
synthetic values (so the real tagger runs on it), one scope per case, and reports."""

from __future__ import annotations

import datetime as dt
import importlib
import json
import os
import random
import re
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.config import REPO_ROOT, get_settings
from core.db import Conn

ROOT = REPO_ROOT or Path.cwd()
GOLDEN = ROOT / "eval" / "golden"
# UAT keeps reports in its data folder (EVAL_REPORTS_DIR), so the next deploy has a baseline for the
# regression check and the go/no-go report can read them (B8 review).
REPORTS = Path(os.environ.get("EVAL_REPORTS_DIR") or ROOT / "eval" / "reports")
sys.path.insert(0, str(GOLDEN))
generators = importlib.import_module("generators")
TAG = re.compile(r"\[\[([A-Z][A-Z_]*)_([0-9]+)\]\]")
WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]


@dataclass
class Context:
    conn: Conn
    rng: random.Random
    colleagues: list[str]
    clients: list[str]
    scopes: list[str] = field(default_factory=list)

    def scope(self) -> str:
        s = f"DRAFT-{uuid.UUID(int=self.rng.getrandbits(128))}"
        self.scopes.append(s)
        return s

    def generators(self) -> dict[str, Any]:
        return {
            "COLLEAGUE_NAME": lambda r: r.choice(self.colleagues),
            "CLIENT_AMC_NAME": lambda r: r.choice(self.clients),
            "ACCOUNT_IN_WORDS": lambda r: " ".join(
                WORDS[int(d)] for d in generators.account(r) if d.isdigit()
            ),
        }

    def fill(self, node: Any) -> Any:
        """Placeholders become generated values; tags in golden text become synthetic values of their type,
        consistently within the case, so the production tagger re-tags them."""
        seen: dict[str, str] = {}

        def untag(m: re.Match[str]) -> str:
            tag = m.group(0)
            if tag not in seen:
                typ = m.group(1)
                if typ == "KFIN_EMPLOYEE":
                    seen[tag] = self.rng.choice(self.colleagues)
                elif typ.startswith("CLIENT_"):
                    seen[tag] = self.rng.choice(self.clients)
                else:
                    seen[tag] = generators.person_name(self.rng)
            return seen[tag]

        def walk(x: Any) -> Any:
            if isinstance(x, str):
                return TAG.sub(untag, generators.fill(x, self.rng, self.generators()))
            if isinstance(x, list):
                return [walk(v) for v in x]
            if isinstance(x, dict):
                return {k: walk(v) for k, v in x.items()}
            return x

        return walk(node)

    def cleanup(self) -> None:
        if self.scopes:
            self.conn.execute("DELETE FROM pseudonym_vault WHERE scope_id = ANY(%s)", (self.scopes,))


def context(conn: Conn, seed: int) -> Context:
    from pii.detect import directory

    colleagues = [
        r["name"]
        for r in conn.execute(
            "SELECT name FROM users WHERE source = 'hr' AND name ~ ' ' ORDER BY name LIMIT 200"
        ).fetchall()
    ]
    d = directory(conn)
    clients = sorted({a for a, t in d.clients.items() if t == "CLIENT_AMC" and len(a) > 6})
    if not colleagues or not clients:
        raise SystemExit("eval needs the synthetic HR directory and client names: run `make seed` first")
    rng = random.Random(seed)  # noqa: S311 - repeatable synthetic test data, not secrets
    return Context(conn=conn, rng=rng, colleagues=colleagues, clients=clients)


def read_jsonl(name: str) -> list[dict[str, Any]]:
    path = GOLDEN / name
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def route_name() -> str:
    return get_settings().llm_mode


def write_report(agent: str, version: str, body: dict[str, Any]) -> Path:
    REPORTS.mkdir(parents=True, exist_ok=True)
    day = dt.datetime.now(dt.UTC).strftime("%Y%m%d-%H%M%S")
    path = REPORTS / f"{agent}-{version}-{day}.json"
    path.write_text(json.dumps(body, indent=1, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return path


def last_passing(agent: str, route: str) -> dict[str, Any] | None:
    if not REPORTS.exists():
        return None
    for path in sorted(REPORTS.glob(f"{agent}-*.json"), reverse=True):
        body = json.loads(path.read_text(encoding="utf-8"))
        if body.get("route") == route and body.get("passed"):
            return body  # type: ignore[no-any-return]
    return None
