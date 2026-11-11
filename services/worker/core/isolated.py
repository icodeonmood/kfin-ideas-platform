"""Run a standalone script on costly or hostile input in a short-lived child process (DEC-096, BLD-C005, BLD-C012).

What it gives: a separate interpreter started with `-I` (no user site, no environment-driven imports); a cleared
environment (the worker's database URL, keys and tokens are not passed, and the runner refuses secret-looking
variables); no inherited file descriptors (`close_fds`); its own limits, set first thing before it touches the
input (address space, CPU seconds, file size, no core files); a wall-clock timeout; and its stderr discarded (a
decoder's message can carry pieces of the input). So a file that would exhaust memory or CPU, or crash a parser,
costs one child and never the worker.

What it does not give: the child runs as the worker's own user, on the worker's filesystem and network. Code that
took control of it could read what that user can read, including the worker's `/proc/<pid>/environ` and any
mounted secret, and could reach the database and the store. It is a resource boundary, not a security boundary.
The stdlib-only probe is low risk; a native decoder (the speech engine) is not, so outside dev and test the engine
runs in the isolated speech service instead (BLD-C012).
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


class IsolatedFailed(Exception):
    """The child did not give an answer. `code` is safe to log and store."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def minimal_env(extra: dict[str, str] | None = None, *, home: str) -> dict[str, str]:
    """Only what an interpreter needs. Anything secret the worker holds is left behind on purpose."""
    env = {"PATH": os.defpath, "LANG": "C.UTF-8", "HOME": home, "TMPDIR": home, "PYTHONHASHSEED": "0"}
    for key, value in (extra or {}).items():
        if any(word in key.upper() for word in ("KEY", "TOKEN", "SECRET", "PASSWORD", "DATABASE", "URL")):
            raise ValueError("refusing to pass a secret-looking variable to an isolated child")
        env[key] = value
    return env


def run(
    script: Path,
    args: list[str],
    data: bytes,
    *,
    timeout_s: float,
    memory_mb: int,
    cpu_s: int,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Run `script` on `data` and return its JSON answer. The script is standalone (stdlib, plus its engine when
    it has one) and must apply `--memory-mb` and `--cpu-s` with `resource.setrlimit` before reading its input:
    RLIMIT_AS is enforced on Linux (the worker's containers); macOS may refuse it, and the timeout still holds."""
    with tempfile.TemporaryDirectory(prefix="isolated-") as home:
        try:
            done = subprocess.run(  # our own script, a fixed interpreter, no shell
                [
                    sys.executable,
                    "-I",
                    str(script),
                    "--memory-mb",
                    str(memory_mb),
                    "--cpu-s",
                    str(cpu_s),
                    *args,
                ],
                input=data,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=timeout_s,
                env=minimal_env(env, home=home),
                cwd=home,
                close_fds=True,
                check=False,
            )
        except subprocess.TimeoutExpired:
            raise IsolatedFailed("timeout") from None
    if done.returncode < 0:
        sig = -done.returncode
        raise IsolatedFailed("cpu_limit" if sig in (signal.SIGXCPU, signal.SIGKILL) else "crashed")
    lines = done.stdout.decode("utf-8", "replace").strip().splitlines()
    try:
        answer = json.loads(lines[-1]) if lines else None
    except ValueError:
        answer = None
    if not isinstance(answer, dict):
        raise IsolatedFailed("memory" if done.returncode in (137, 9) else "crashed")
    return answer
