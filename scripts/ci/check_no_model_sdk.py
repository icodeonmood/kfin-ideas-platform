#!/usr/bin/env python3
"""CI rule (non-negotiable 1, AT-B1-09): no model SDK is imported outside services/worker/gateway/.

Scans Python, TypeScript and JavaScript sources plus the web app's package.json. Exit 0 = clean, 1 = violation.
Usage: python scripts/ci/check_no_model_sdk.py [repo-root]
"""

from __future__ import annotations

import json
import re
import sys
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


def violations(root: Path) -> list[str]:
    found: list[str] = []
    this_file = Path(__file__).resolve()
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts) or not path.is_file():
            continue
        if path.resolve() == this_file or rel.is_relative_to(ALLOWED_DIR):
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
