"""Split an OKF Markdown file into its YAML frontmatter and body."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml


class FrontmatterError(ValueError):
    pass


@dataclass(frozen=True)
class Document:
    meta: dict[str, Any] | None  # None when the file has no frontmatter block
    body: str
    body_line: int  # 1-based line where the body starts


def parse(text: str) -> Document:
    if text.startswith("﻿"):
        text = text[1:]
    lines = text.split("\n")
    if not lines or lines[0].rstrip() != "---":
        return Document(meta=None, body=text, body_line=1)
    for i in range(1, len(lines)):
        if lines[i].rstrip() == "---":
            raw = "\n".join(lines[1:i])
            try:
                meta = yaml.safe_load(raw) if raw.strip() else {}
            except yaml.YAMLError as exc:
                raise FrontmatterError(f"frontmatter is not valid YAML: {exc.__class__.__name__}") from exc
            if not isinstance(meta, dict):
                raise FrontmatterError("frontmatter must be a YAML mapping")
            return Document(meta=meta, body="\n".join(lines[i + 1 :]), body_line=i + 2)
    raise FrontmatterError("frontmatter block is not closed with ---")


def dump(meta: dict[str, Any], body: str) -> str:
    """Render frontmatter and body. Key order is kept as given."""
    head = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True, width=1000, default_flow_style=False)
    return f"---\n{head}---\n{body if body.startswith(chr(10)) else chr(10) + body}"
