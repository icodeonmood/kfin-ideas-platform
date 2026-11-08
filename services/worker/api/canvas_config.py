"""What the canvas needs from the company repo (§4.1): limits, the strength rubric, attachment rules and the
"what good looks like" examples. Rules come through the validated rules loader (never guessed). Cached until
the company repo's HEAD moves.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from core.config import get_settings
from okf.frontmatter import parse
from repo_writer.git import Git
from rules import load_all

EXAMPLE_ORDER = (
    "what-is-it",
    "who-it-touches",
    "whats-it-worth",
    "solved-elsewhere",
    "your-solution",
    "your-research",
)
_cache: dict[str, Any] = {"head": None, "value": None}


def _section(body: str, heading: str) -> str:
    m = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", body, re.MULTILINE | re.DOTALL)
    if not m:
        return ""
    text = m.group(1).strip()
    return "\n".join(line.removeprefix("> ").removeprefix(">") for line in text.splitlines()).strip()


def _examples(repo: Path) -> list[dict[str, str]]:
    out = []
    for slug in EXAMPLE_ORDER:
        path = repo / "guidance" / "canvas" / f"{slug}.md"
        if not path.exists():
            continue
        doc = parse(path.read_text(encoding="utf-8"))
        kfin = (doc.meta or {}).get("kfin") or {}
        out.append(
            {
                "slug": slug,
                "section": str(kfin.get("section", "")),
                "question": _section(doc.body, "The question"),
                "weak": _section(doc.body, "A weak answer"),
                "strong": _section(doc.body, "A strong answer"),
                "why": _section(doc.body, "Why it works"),
            }
        )
    return out


def canvas_config() -> dict[str, Any]:
    repo = Path(get_settings().company_repo_path)
    head = Git(repo).head()
    if head is not None and _cache["head"] == head:
        return dict(_cache["value"])
    rules = load_all(repo)
    thresholds = rules["thresholds"].data
    value = {
        "rules_version": {name: r.version for name, r in rules.items()},
        "commit": head,
        "canvas": thresholds["canvas"],
        "canvas_strength": thresholds["canvas_strength"],
        "attachments": thresholds["attachments"],
        "scan": {"poll_interval_s": thresholds["scan"]["poll_interval_s"]},
        "examples": _examples(repo),
    }
    _cache.update(head=head, value=value)
    return dict(value)
