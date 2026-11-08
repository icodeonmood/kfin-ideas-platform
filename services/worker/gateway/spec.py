"""Agent definitions from `agents/<name>/`: prompt, output schema, runtime config and fixed examples."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from core.config import get_settings


class AgentConfigError(RuntimeError):
    """An agent folder is missing a file or has an invalid config. Carries the agent name only."""


@dataclass(frozen=True)
class Example:
    name: str
    description: str
    input: dict[str, Any]
    output: dict[str, Any]


@dataclass(frozen=True)
class AgentSpec:
    name: str
    version: str
    tier: str  # fast | reasoning
    prompt: str
    schema: dict[str, Any]
    max_tokens: int
    timeout_s: float
    latency_budget_s: float
    retries_on_invalid: int
    cache_ttl_days: int
    effort: str | None
    thinking: str  # off | adaptive
    input_blocks: tuple[str, ...]
    untrusted_blocks: tuple[str, ...]
    examples: tuple[Example, ...]
    prompt_examples: tuple[str, ...]
    fake_default: str
    raw: dict[str, Any] = field(default_factory=dict)

    def example(self, name: str) -> Example:
        for e in self.examples:
            if e.name == name:
                return e
        raise AgentConfigError(f"{self.name}: no example {name}")

    @property
    def model(self) -> str:
        s = get_settings()
        return s.llm_fast_model if self.tier == "fast" else s.llm_reasoning_model


def _blocks(values: list[str]) -> tuple[str, ...]:
    out: list[str] = []
    for v in values:
        out.extend(part.strip() for part in str(v).split("|"))  # "submission | attachment_text": either
    return tuple(out)


@lru_cache(maxsize=32)
def load(name: str, agents_dir: Path | None = None) -> AgentSpec:
    root = (agents_dir or get_settings().agents_dir) / name
    try:
        cfg = yaml.safe_load((root / "config.yaml").read_text(encoding="utf-8"))
        prompt = (root / "prompt.md").read_text(encoding="utf-8")
        schema = json.loads((root / "schema.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise AgentConfigError(f"{name}: {type(exc).__name__}") from None
    if cfg.get("name") != name or cfg.get("tier") not in ("fast", "reasoning"):
        raise AgentConfigError(f"{name}: config name or tier is wrong")
    examples = []
    for path in sorted((root / "examples").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        examples.append(Example(path.name, str(data.get("description", "")), data["input"], data["output"]))
    return AgentSpec(
        name=name,
        version=str(cfg["version"]),
        tier=cfg["tier"],
        prompt=prompt,
        schema=schema,
        max_tokens=int(cfg["max_tokens"]),
        timeout_s=float(cfg["timeout_s"]),
        latency_budget_s=float(cfg["latency_budget_s"]),
        retries_on_invalid=int(cfg.get("retries_on_invalid", 1)),
        cache_ttl_days=int(cfg.get("cache_ttl_days", 30)),
        effort=cfg.get("effort"),
        thinking="off"
        if cfg.get("thinking", "off") in ("off", False)
        else str(cfg["thinking"]),  # YAML: off is False
        input_blocks=_blocks(cfg.get("input_blocks", [])),
        untrusted_blocks=_blocks(cfg.get("untrusted_blocks", [])),
        examples=tuple(examples),
        prompt_examples=tuple(cfg.get("examples_in_prompt", [])),
        fake_default=str(cfg.get("fake_mode_default", examples[0].name if examples else "")),
        raw=cfg,
    )
