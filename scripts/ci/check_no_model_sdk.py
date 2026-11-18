#!/usr/bin/env python3
"""CI rule (non-negotiable 1, AT-B1-09): no model SDK is imported outside services/worker/gateway/.

The Sarvam SDK (`sarvamai`, on PyPI and npm) is banned everywhere, the gateway included (BLD-C177): the gateway's
Sarvam client (`gateway/sarvam.py`) is plain httpx and websockets, and the SDK may not be imported, nor listed in any
Python dependency file (pyproject.toml, requirements*.txt or .in, uv.lock) or package.json.

Scans Python, TypeScript and JavaScript sources plus package.json and the Python dependency files. Exit 0 = clean,
1 = violation. Usage: python scripts/ci/check_no_model_sdk.py [repo-root]
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path

ALLOWED_DIR = Path("services/worker/gateway")
# `.worktrees` holds other checkouts of this repo (parallel builds); each is checked from its own root.
SKIP_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    ".next",
    ".data",
    "__pycache__",
    "playwright-report",
    "test-results",
    ".mypy_cache",
    ".worktrees",
}
CODE_SUFFIXES = {".py", ".ts", ".tsx", ".mts", ".cts", ".js", ".mjs", ".cjs", ".jsx"}

_PY_MODULES = r"(?:anthropic|openai|google\.generativeai|google\.genai|langchain\w*|litellm|cohere|mistralai)"
PY_PATTERNS = [
    # from anthropic import X  /  from openai.types import Y
    re.compile(rf"^\s*from\s+({_PY_MODULES})\b", re.MULTILINE),
    # import anthropic  /  import os, anthropic as a
    re.compile(rf"^\s*import\s+(?:[\w.]+(?:\s+as\s+\w+)?\s*,\s*)*({_PY_MODULES})\b", re.MULTILINE),
    # from google import genai, generativeai
    re.compile(r"^\s*from\s+google\s+import\s+[^\n]*\b(genai|generativeai)\b", re.MULTILINE),
    # __import__("anthropic") / importlib.import_module("openai")
    re.compile(rf"""(?:__import__|import_module)\(\s*[rbu]?["']({_PY_MODULES})(?:\.[\w.]*)?["']"""),
]
BEDROCK = re.compile(r"""["'`]bedrock-runtime["'`]|bedrock_runtime|BedrockRuntime""")
_JS_PACKAGES = r"(@anthropic-ai/[\w-]+|openai|@aws-sdk/client-bedrock[\w-]*|@ai-sdk/[\w-]+|ai|@google/generative-ai|@google/genai)"
JS_IMPORT = re.compile(
    rf"""(?:\bfrom\s+|\brequire\(\s*|\bimport\(\s*|^\s*import\s+)["'`]{_JS_PACKAGES}(?:/[^"'`]*)?["'`]""",
    re.MULTILINE,
)
JS_PACKAGES = re.compile(r"^(@anthropic-ai/.+|openai|@aws-sdk/client-bedrock.*|@ai-sdk/.+|ai|@google/generative-ai|@google/genai)$")
DEPENDENCY_KEYS = ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies")

# Banned everywhere, the gateway included (BLD-C177, DEC-108).
EVERYWHERE = "sarvamai"
EVERYWHERE_PY = [
    re.compile(rf"^\s*from\s+({EVERYWHERE})\b", re.MULTILINE),
    re.compile(rf"^\s*import\s+(?:[\w.]+(?:\s+as\s+\w+)?\s*,\s*)*({EVERYWHERE})\b", re.MULTILINE),
    re.compile(rf"""(?:__import__|import_module)\(\s*[rbu]?["']({EVERYWHERE})(?:\.[\w.]*)?["']"""),
]
EVERYWHERE_JS = re.compile(
    rf"""(?:\bfrom\s+|\brequire\(\s*|\bimport\(\s*|^\s*import\s+)["'`]({EVERYWHERE})(?:/[^"'`]*)?["'`]""",
    re.MULTILINE,
)
_REQ_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
UV_LOCK_NAME = re.compile(r'^name\s*=\s*"([^"]+)"\s*$', re.MULTILINE)


def _banned_name(requirement: str) -> bool:
    """A requirement's project name is the Sarvam SDK (PEP 503: case and -_. do not matter)."""
    m = _REQ_NAME.match(requirement)
    return bool(m) and re.sub(r"[-_.]+", "", m.group(1)).lower() == EVERYWHERE


def _python_requirements(path: Path, text: str) -> list[str]:
    """The requirement strings a Python dependency file lists."""
    if path.name == "uv.lock":
        return UV_LOCK_NAME.findall(text)
    if path.name == "pyproject.toml":
        try:
            data = tomllib.loads(text)
        except tomllib.TOMLDecodeError:
            return []
        project = data.get("project") or {}
        reqs = list(project.get("dependencies") or [])
        for group in (project.get("optional-dependencies") or {}).values():
            reqs += list(group)
        for group in (data.get("dependency-groups") or {}).values():
            reqs += [r for r in group if isinstance(r, str)]
        reqs += list(((data.get("tool") or {}).get("uv") or {}).get("dev-dependencies") or [])
        return [r for r in reqs if isinstance(r, str)]
    lines = (line.split("#", 1)[0].strip() for line in text.splitlines())
    return [line for line in lines if line and not line.startswith("-")]


def _python_dependency_file(path: Path) -> bool:
    name = path.name
    return name in ("pyproject.toml", "uv.lock") or (name.startswith("requirements") and path.suffix in (".txt", ".in"))


def everywhere(path: Path, rel: Path) -> list[str]:
    """The Sarvam SDK, anywhere: an import, a package.json dependency, or a Python dependency file entry."""
    if path.suffix in CODE_SUFFIXES:
        text = path.read_text(encoding="utf-8", errors="ignore")
        pats = EVERYWHERE_PY if path.suffix == ".py" else [EVERYWHERE_JS]
        if any(p.search(text) for p in pats):
            return [f"{rel}: imports {EVERYWHERE} (banned everywhere, gateway included)"]
    elif path.name == "package.json":
        manifest = json.loads(path.read_text(encoding="utf-8"))
        deps = {name for key in DEPENDENCY_KEYS for name in (manifest.get(key) or {})}
        if EVERYWHERE in deps:
            return [f"{rel}: depends on {EVERYWHERE} (banned everywhere, gateway included)"]
    elif _python_dependency_file(path):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(_banned_name(r) for r in _python_requirements(path, text)):
            return [f"{rel}: depends on {EVERYWHERE} (banned everywhere, gateway included)"]
    return []


def violations(root: Path) -> list[str]:
    found: list[str] = []
    this_file = Path(__file__).resolve()
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts) or not path.is_file():
            continue
        if path.resolve() == this_file:
            continue
        found.extend(everywhere(path, rel))
        if rel.is_relative_to(ALLOWED_DIR):
            continue
        if path.suffix in CODE_SUFFIXES:
            text = path.read_text(encoding="utf-8", errors="ignore")
            if path.suffix == ".py":
                hits = [m.group(1) for pat in PY_PATTERNS for m in pat.finditer(text)]
                hits += ["bedrock-runtime"] if BEDROCK.search(text) else []
            else:
                hits = [m.group(1) for m in JS_IMPORT.finditer(text)]
                hits += ["bedrock-runtime"] if BEDROCK.search(text) else []
            found.extend(f"{rel}: imports {h}" for h in sorted(set(hits)))
        elif path.name == "package.json":
            manifest = json.loads(path.read_text(encoding="utf-8"))
            deps = {name: v for key in DEPENDENCY_KEYS for name, v in (manifest.get(key) or {}).items()}
            found.extend(f"{rel}: depends on {name}" for name in sorted(deps) if JS_PACKAGES.match(name))
    return found


def main(argv: list[str]) -> int:
    root = Path(argv[1] if len(argv) > 1 else ".").resolve()
    problems = violations(root)
    for p in problems:
        print(f"MODEL SDK OUTSIDE GATEWAY  {p}")
    print(f"no-model-sdk: {'FAIL' if problems else 'ok'} ({len(problems)} violations)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
