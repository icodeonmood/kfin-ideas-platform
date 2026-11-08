"""Message templates from the company repo (`comms/templates/<name>.md`, wording signed off by HR).

Mustache-style and deliberately small: `{{a.b}}` variables (a list index works: `{{idea.next_best.0}}`) and
`{{#a.b}}…{{/a.b}}` sections shown when the value is truthy. Values are inserted as plain text; nothing in a
value is ever interpreted as template syntax or markup. Unknown variables render empty.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from core.config import get_settings
from okf.frontmatter import parse

_SECTION = re.compile(r"\{\{#([a-z_.0-9]+)\}\}(.*?)\{\{/\1\}\}", re.S)
_VAR = re.compile(r"\{\{([a-z_.0-9]+)\}\}")
_COMMENT = re.compile(r"<!--.*?-->", re.S)


@dataclass(frozen=True)
class Template:
    name: str
    version: str
    subject: str
    body: str


def _lookup(data: Any, path: str) -> Any:
    node = data
    for key in path.split("."):
        if isinstance(node, dict):
            node = node.get(key)
        elif isinstance(node, list) and key.isdigit() and int(key) < len(node):
            node = node[int(key)]
        else:
            return None
    return node


def render_text(text: str, data: dict[str, Any]) -> str:
    def section(m: re.Match[str]) -> str:
        return render_text(m.group(2), data) if _lookup(data, m.group(1)) else ""

    out = _SECTION.sub(section, text)
    return _VAR.sub(
        lambda m: "" if _lookup(data, m.group(1)) is None else str(_lookup(data, m.group(1))), out
    )


@lru_cache(maxsize=64)
def _load(repo: Path, name: str) -> Template:
    doc = parse((repo / "comms" / "templates" / f"{name}.md").read_text(encoding="utf-8"))
    meta = doc.meta or {}
    k = meta.get("kfin") or {}
    body = _COMMENT.sub("", doc.body).strip()
    return Template(
        name=name,
        version=str(k.get("version", "1.0")),
        subject=str(k.get("subject") or meta.get("title")),
        body=body,
    )


def load(name: str) -> Template:
    return _load(get_settings().company_repo_path, name)


def render(name: str, data: dict[str, Any]) -> tuple[str, str, str]:
    """(subject, body, version) for a template and its variables."""
    t = load(name)
    return render_text(t.subject, data).strip(), render_text(t.body, data).strip() + "\n", t.version
