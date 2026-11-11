"""Thin wrapper over the git CLI for the company repo. Only the repo writer commits; others read."""

from __future__ import annotations

import os
import re
import subprocess
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

_AUTHOR = re.compile(r"^\s*(?P<name>[^<]+?)\s*<(?P<email>[^>]+)>\s*$")

# While `make seed` creates or refreshes the company repo it leaves a marker beside it (in the folder the worker
# also mounts). The repo writer skips its rounds while the marker is there, so it never takes a seed half-way
# through for a crashed write and resets it (BLD-A167). A marker older than this is from a seed that died.
SEED_MARKER_STALE_S = 600
SEED_SETTLE_S = 2.0  # a writer round that began just before the marker finishes its start-up steps


def seed_marker(repo: Path) -> Path:
    return repo.parent / f".{repo.name}.seeding"


def seed_in_progress(repo: Path) -> bool:
    try:
        return time.time() - seed_marker(repo).stat().st_mtime < SEED_MARKER_STALE_S
    except FileNotFoundError:
        return False


def seed_marker_age(repo: Path) -> float | None:
    try:
        return time.time() - seed_marker(repo).stat().st_mtime
    except FileNotFoundError:
        return None


@contextmanager
def seeding(repo: Path, settle_s: float = SEED_SETTLE_S) -> Iterator[None]:
    """Hold the seed marker while the seed writes the company repo. Created exclusively, so two seeds cannot both
    hold it; removed however the seed ends, an interrupt during the settle wait included. A seed killed outright
    (SIGKILL) leaves it, and it goes stale after SEED_MARKER_STALE_S."""
    marker = seed_marker(repo)
    marker.parent.mkdir(parents=True, exist_ok=True)
    if not seed_in_progress(repo):
        marker.unlink(missing_ok=True)  # stale, from a seed that died
    try:
        fd = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        raise SystemExit(
            f"another seed is running ({marker}). Wait for it to finish; if no seed is running, delete that file"
        ) from None
    try:
        os.write(fd, f"{os.getpid()}\n".encode())
        os.close(fd)
        time.sleep(settle_s)
        yield
    finally:
        marker.unlink(missing_ok=True)


class GitError(RuntimeError):
    pass


@dataclass(frozen=True)
class Change:
    status: str  # A, M, D
    path: str


class Git:
    def __init__(self, path: Path, author: str = "Ideas Platform Bot <ideas-bot@localhost>") -> None:
        self.path = path
        m = _AUTHOR.match(author)
        if not m:
            raise ValueError("REPO_WRITER_AUTHOR must look like 'Name <email>'")
        self.name, self.email = m.group("name"), m.group("email")

    def run(self, *args: str, check: bool = True, input_text: str | None = None) -> str:
        cmd = [
            "git",
            "-c", f"safe.directory={self.path}",
            "-c", f"user.name={self.name}",
            "-c", f"user.email={self.email}",
            "-c", "core.quotepath=off",
            "-C", str(self.path),
            *args,
        ]  # fmt: skip
        out = subprocess.run(cmd, capture_output=True, text=True, input=input_text, check=False)
        if check and out.returncode != 0:
            # stderr can echo file names; raise with the git subcommand only.
            raise GitError(f"git {args[0]} failed with exit code {out.returncode}")
        return out.stdout

    # ---- state -------------------------------------------------------------------------------------
    def is_repo(self) -> bool:
        return (self.path / ".git").exists()

    def head(self) -> str | None:
        out = subprocess.run(
            [
                "git",
                "-c",
                f"safe.directory={self.path}",
                "-C",
                str(self.path),
                "rev-parse",
                "--verify",
                "-q",
                "HEAD",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        return out.stdout.strip() or None

    def has_commit(self, sha: str) -> bool:
        out = subprocess.run(
            [
                "git",
                "-c",
                f"safe.directory={self.path}",
                "-C",
                str(self.path),
                "cat-file",
                "-e",
                f"{sha}^{{commit}}",
            ],
            capture_output=True,
            check=False,
        )
        return out.returncode == 0

    def is_dirty(self) -> bool:
        return bool(self.run("status", "--porcelain").strip())

    def commit_count(self) -> int:
        return int(self.run("rev-list", "--count", "HEAD").strip()) if self.head() else 0

    # ---- writes ------------------------------------------------------------------------------------
    def init(self) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        self.run("init", "-q", "-b", "main")

    def clear_stale_locks(self) -> None:
        """A writer killed inside `git add` or `git commit` leaves lock files that block every later write.
        Only call this while holding the single-writer lock."""
        git_dir = self.path / ".git"
        for lock in [git_dir / "index.lock", git_dir / "HEAD.lock", *git_dir.glob("refs/heads/*.lock")]:
            lock.unlink(missing_ok=True)

    def reset_hard(self) -> None:
        """The working tree belongs to the writer alone; anything uncommitted is a half-done write."""
        if self.head():
            self.run("reset", "-q", "--hard", "HEAD")
        self.run("clean", "-q", "-fd")

    def commit_all(self, message: str) -> str:
        self.run("add", "-A")
        self.run("commit", "-q", "--allow-empty", "-F", "-", input_text=message)
        sha = self.head()
        if sha is None:
            raise GitError("commit produced no HEAD")
        return sha

    def push(self, remote: str = "origin", branch: str = "main") -> None:
        self.run("push", "-q", remote, branch)

    # ---- reads -------------------------------------------------------------------------------------
    def show(self, rev: str, rel: str) -> str:
        return self.run("show", f"{rev}:{rel}")

    def ls_files(self, rev: str = "HEAD") -> list[str]:
        return [p for p in self.run("ls-tree", "-r", "--name-only", rev).split("\n") if p]

    def diff(self, a: str, b: str) -> list[Change]:
        out = self.run("diff", "--name-status", "--no-renames", a, b)
        changes = []
        for line in out.split("\n"):
            if line.strip():
                status, rel = line.split("\t", 1)
                changes.append(Change(status[0], rel))
        return changes

    def outbox_commits(self, limit: int = 1000) -> dict[int, str]:
        """outbox ID -> commit SHA, from the `outbox:` trailer of recent commits (crash recovery)."""
        if not self.head():
            return {}
        out = self.run("log", f"-n{limit}", "--format=%H%x09%(trailers:key=outbox,valueonly,separator=%x2C)")
        found: dict[int, str] = {}
        for line in out.split("\n"):
            if "\t" not in line:
                continue
            sha, values = line.split("\t", 1)
            for v in values.split(","):
                if v.strip().isdigit():
                    found[int(v.strip())] = sha
        return found
