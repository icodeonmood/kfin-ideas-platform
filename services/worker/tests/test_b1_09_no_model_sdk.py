"""AT-B1-09: CI fails if any file outside `services/worker/gateway/` imports a model SDK."""

import subprocess
import sys
from pathlib import Path

import pytest

from tests import helpers

SCRIPT = helpers.ROOT / "scripts" / "ci" / "check_no_model_sdk.py"


def _run(root: Path) -> int:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(root)], capture_output=True, text=True, check=False
    ).returncode


def _tree(tmp_path: Path, rel: str, text: str) -> Path:
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return tmp_path


def test_the_repo_itself_is_clean() -> None:
    assert _run(helpers.ROOT) == 0


@pytest.mark.parametrize(
    ("rel", "text"),
    [
        ("services/worker/scan/agent.py", "import anthropic\n"),
        ("services/worker/match/judge.py", "from anthropic import Anthropic\n"),
        # Built at run time so this test file does not itself trip the checker it tests.
        ("services/worker/match/llm.py", "client = boto3.client('" + "bedrock" + "-runtime')\n"),
        ("apps/web/src/server/ai.ts", 'import Anthropic from "@anthropic-ai/sdk";\n'),
        ("apps/web/src/server/ai2.ts", 'const o = require("openai");\n'),
        ("apps/web/package.json", '{"dependencies": {"@anthropic-ai/sdk": "1.0.0"}}'),
        # Gaps found in review:
        ("services/worker/scan/a.py", "import os, anthropic\n"),
        ("services/worker/scan/b.py", "from google import genai\n"),
        ("services/worker/scan/c.py", "mod = importlib.import_module" + "('anthropic')\n"),
        ("services/worker/scan/d.py", "mod = __import__" + "('openai')\n"),
        ("apps/web/src/server/e.ts", 'import OpenAI from "openai/resources";\n'),
        ("apps/web/src/server/f.mts", "const m = await import(`@anthropic-ai/sdk`);\n"),
        ("apps/web/src/server/g.ts", 'import "@anthropic-ai/sdk/shims/node";\n'),
        ("apps/web/package.json", '{"peerDependencies": {"openai": "4.0.0"}}'),
    ],
)
def test_sdk_outside_gateway_fails(tmp_path: Path, rel: str, text: str) -> None:
    assert _run(_tree(tmp_path, rel, text)) == 1


def test_sdk_inside_gateway_is_allowed(tmp_path: Path) -> None:
    assert _run(_tree(tmp_path, "services/worker/gateway/route.py", "import anthropic\n")) == 0


def test_ruff_bans_the_import_too(tmp_path: Path) -> None:
    worker = helpers.ROOT / "services" / "worker"
    bad = worker / "scan" / "_ci_probe.py"
    bad.parent.mkdir(exist_ok=True)
    bad.write_text("import anthropic  # probe\n", encoding="utf-8")
    try:
        out = subprocess.run(
            ["uv", "run", "--frozen", "ruff", "check", "--select", "TID251", str(bad)],
            cwd=worker, capture_output=True, text=True, check=False,
        )  # fmt: skip
        assert out.returncode == 1 and "TID251" in out.stdout
    finally:
        bad.unlink()
