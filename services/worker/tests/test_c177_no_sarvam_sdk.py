"""BLD-C177 (DEC-108, non-negotiable 1): the Sarvam SDK (`sarvamai`, on PyPI and npm) is banned everywhere, the
gateway included: as an import (scripts/ci/check_no_model_sdk.py and ruff), and as a dependency in pyproject.toml,
requirements files, uv.lock and package.json. The gateway's own client, `gateway/sarvam.py`, is plain httpx and
websockets."""

from __future__ import annotations

import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from tests import helpers

SCRIPT = helpers.ROOT / "scripts" / "ci" / "check_no_model_sdk.py"
WORKER = helpers.ROOT / "services" / "worker"
SDK = "sarvam" + "ai"  # built at run time, so this file does not itself trip the checker it tests


def _run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(root)], capture_output=True, text=True, check=False
    )


def _tree(tmp_path: Path, rel: str, text: str) -> Path:
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize(
    ("rel", "text"),
    [
        # Imports, the gateway included.
        ("services/worker/gateway/sarvam.py", f"import {SDK}\n"),
        ("services/worker/gateway/speech.py", f"from {SDK} import SarvamAI\n"),
        ("services/worker/gateway/x.py", f"def f():\n    from {SDK}.types import AudioData\n"),
        ("services/worker/gateway/y.py", f"mod = importlib.import_module('{SDK}')\n"),
        ("services/worker/speech/drafts.py", f"import os, {SDK}\n"),
        ("apps/web/src/server/voice.ts", f'import {{ SarvamAIClient }} from "{SDK}";\n'),
        ("apps/web/src/server/voice2.ts", f'const s = require("{SDK}");\n'),
        # Dependencies.
        ("apps/web/package.json", f'{{"dependencies": {{"{SDK}": "1.0.0"}}}}'),
        ("services/worker/pyproject.toml", f'[project]\nname = "w"\ndependencies = ["{SDK}>=0.1"]\n'),
        ("services/worker/pyproject.toml", f'[project]\nname = "w"\n[dependency-groups]\ndev = ["{SDK}"]\n'),
        ("services/worker/pyproject.toml", '[project]\nname = "w"\ndependencies = ["Sarvam_AI==0.1.46"]\n'),
        ("services/worker/speech_service/requirements.txt", f"{SDK}==0.1.46 \\\n    --hash=sha256:00\n"),
        ("services/worker/speech_service/requirements.in", f"{SDK}  # streaming\n"),
        ("services/worker/uv.lock", f'version = 1\n\n[[package]]\nname = "{SDK}"\nversion = "0.1.46"\n'),
    ],
)
def test_BLD_C177_the_sarvam_sdk_is_banned_everywhere_gateway_included(
    tmp_path: Path, rel: str, text: str
) -> None:
    done = _run(_tree(tmp_path, rel, text))
    assert done.returncode == 1, done.stdout
    assert SDK in done.stdout


@pytest.mark.parametrize(
    ("rel", "text"),
    [
        # A ban, a comment or a longer name is not a dependency.
        (
            "services/worker/pyproject.toml",
            f'[tool.ruff.lint.flake8-tidy-imports.banned-api]\n"{SDK}".msg = "no"\n',
        ),
        ("services/worker/speech_service/requirements.txt", f"# never {SDK}\nfaster-whisper==1.1.1\n"),
        ("services/worker/pyproject.toml", f'[project]\nname = "w"\ndependencies = ["{SDK}-tools"]\n'),
        ("services/worker/gateway/sarvam.py", "import httpx\nfrom websockets.sync.client import connect\n"),
    ],
)
def test_BLD_C177_mentions_that_are_not_the_sdk_pass(tmp_path: Path, rel: str, text: str) -> None:
    assert _run(_tree(tmp_path, rel, text)).returncode == 0


def test_BLD_C177_the_repo_has_no_sarvam_sdk() -> None:
    done = _run(helpers.ROOT)
    assert done.returncode == 0, done.stdout


def test_BLD_C177_ruff_bans_the_sdk_in_and_outside_the_gateway() -> None:
    config = tomllib.loads((WORKER / "pyproject.toml").read_text(encoding="utf-8"))
    tidy = config["tool"]["ruff"]["lint"]["flake8-tidy-imports"]
    assert SDK in tidy["banned-api"] and SDK in tidy["banned-module-level-imports"]
    probes = {
        WORKER / "gateway" / "_c177_probe.py": ("TID253", f"import {SDK}  # probe\n"),
        WORKER / "scan" / "_c177_probe.py": ("TID251", f"def f() -> None:\n    import {SDK}  # probe\n"),
    }
    try:
        for path, (rule, text) in probes.items():
            path.write_text(text, encoding="utf-8")
            out = subprocess.run(
                [sys.executable, "-m", "ruff", "check", "--no-cache", "--select", "TID251,TID253", str(path)],
                cwd=WORKER,
                capture_output=True,
                text=True,
                check=False,
            )
            assert out.returncode == 1 and rule in out.stdout, (path.name, out.stdout)
    finally:
        for path in probes:
            path.unlink(missing_ok=True)


def test_BLD_C177_the_worker_dependency_files_do_not_list_the_sdk() -> None:
    def name(req: str) -> str:
        return (
            re.split(r"[\s\[<>=!~;@]", req.strip(), maxsplit=1)[0].replace("-", "").replace("_", "").lower()
        )

    project = tomllib.loads((WORKER / "pyproject.toml").read_text(encoding="utf-8"))
    reqs = list(project["project"]["dependencies"])
    reqs += [
        r for group in (project.get("dependency-groups") or {}).values() for r in group if isinstance(r, str)
    ]
    for path in sorted((WORKER / "speech_service").glob("requirements*")):
        reqs += [line.split("#", 1)[0] for line in path.read_text(encoding="utf-8").splitlines()]
    assert SDK not in {name(r) for r in reqs if r.strip() and not r.strip().startswith("-")}
    locked = re.findall(r'^name = "([^"]+)"$', (WORKER / "uv.lock").read_text(encoding="utf-8"), re.MULTILINE)
    assert locked and SDK not in {n.replace("-", "").replace("_", "").lower() for n in locked}


def test_BLD_C177_a_sarvam_sdk_hit_in_the_gateway_is_not_called_outside_the_gateway(tmp_path: Path) -> None:
    done = _run(_tree(tmp_path, "services/worker/gateway/sarvam.py", f"import {SDK}\n"))
    assert done.returncode == 1
    assert "SARVAM SDK, BANNED EVERYWHERE  services/worker/gateway/sarvam.py" in done.stdout
    assert "OUTSIDE GATEWAY" not in done.stdout
    outside = _run(_tree(tmp_path / "b", "services/worker/scan/agent.py", "import anthropic\n"))
    assert "MODEL SDK OUTSIDE GATEWAY  services/worker/scan/agent.py" in outside.stdout
