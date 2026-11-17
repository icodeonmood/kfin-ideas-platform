"""Message templates from the company repo (`comms/templates/<name>.md`, wording signed off by HR).

Mustache-style and deliberately small: `{{a.b}}` variables (a list index works: `{{idea.next_best.0}}`) and
`{{#a.b}}…{{/a.b}}` sections shown when the value is truthy. Values are inserted as plain text; nothing in a
value is ever interpreted as template syntax or markup. Unknown variables render empty.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from core.config import get_settings
from okf.frontmatter import parse

_TOKEN = re.compile(r"\{\{#([a-z_.0-9]+)\}\}(.*?)\{\{/\1\}\}|\{\{([a-z_.0-9]+)\}\}", re.S)
_COMMENT = re.compile(r"<!--.*?-->", re.S)


@dataclass(frozen=True)
class Template:
    name: str
    version: str
    subject: str
    body: str
    # Inbox templates (`comms/templates/inbox/<kind>.md`, L-INBOX.kinds) also carry the reader's kind line
    # (`heading`), the row text after the sender (`line`) and the reader's short note (`note`).
    inbox: dict[str, str] = field(default_factory=dict)


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
    """One left-to-right pass over the template: an inserted value is never scanned again, so `{{…}}` inside a
    value stays as typed (B6 review: a value inside a section used to be expanded twice)."""

    def token(m: re.Match[str]) -> str:
        if m.group(1) is not None:  # a section: its inner text is template text, rendered the same way
            return render_text(m.group(2), data) if _lookup(data, m.group(1)) else ""
        v = _lookup(data, m.group(3))
        return "" if v is None else str(v)

    return _TOKEN.sub(token, text)


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
        inbox={str(key): str(value) for key, value in (k.get("inbox") or {}).items()},
    )


def load(name: str) -> Template:
    return _load(get_settings().company_repo_path, name)


def render(name: str, data: dict[str, Any]) -> tuple[str, str, str]:
    """(subject, body, version) for a template and its variables."""
    t = load(name)
    return render_text(t.subject, data).strip(), render_text(t.body, data).strip() + "\n", t.version
