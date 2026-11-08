"""Tag on the way out (ARCHITECTURE §3.2 step 1): every personal or sensitive value becomes a typed tag.

`tag_payload` walks any JSON-shaped payload and returns the same shape with tags in place of values, plus the
tags it used. Text that already looks like a tag is defused first ("[[" becomes "[ ["), so nobody can type a
tag into their own text to pass the tag check or pull a value out of the vault.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from core.db import Conn
from pii import vault
from pii.detect import Directory, detect, directory

TAG_RE = re.compile(r"\[\[([A-Z][A-Z_]*)_([0-9]+)\]\]")


@dataclass
class Tagged:
    payload: Any
    tags: dict[str, str] = field(default_factory=dict)  # tag -> type, every tag present in the payload

    def counts(self) -> dict[str, int]:
        return dict(Counter(self.tags.values()))


def defuse(text: str) -> str:
    return text.replace("[[", "[ [").replace("]]", "] ]")


def tag_text(conn: Conn, scope_id: str, text: str, d: Directory, tags: dict[str, str]) -> str:
    text = defuse(text)
    out, last = [], 0
    for f in detect(text, d):
        tag = vault.assign(conn, scope_id, f.type, f.value, f.subject_user_id)
        tags[tag] = f.type
        out.append(text[last : f.start])
        out.append(tag)
        last = f.end
    out.append(text[last:])
    return "".join(out)


def tag_payload(conn: Conn, scope_id: str, payload: Any, *, d: Directory | None = None) -> Tagged:
    d = d or directory(conn)
    tags: dict[str, str] = {}

    def walk(node: Any) -> Any:
        if isinstance(node, str):
            return tag_text(conn, scope_id, node, d, tags)
        if isinstance(node, list):
            return [walk(x) for x in node]
        if isinstance(node, dict):
            return {k: walk(v) for k, v in node.items()}
        return node

    return Tagged(walk(payload), tags)


def tags_in(payload: Any) -> set[str]:
    found: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, str):
            found.update(m.group(0) for m in TAG_RE.finditer(node))
        elif isinstance(node, list):
            for x in node:
                walk(x)
        elif isinstance(node, dict):
            for v in node.values():
                walk(v)

    walk(payload)
    return found
