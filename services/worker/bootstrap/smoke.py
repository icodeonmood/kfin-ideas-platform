"""Smoke tests after a deploy (AT-B7-06). Runs inside the worker container, on the stack's own network:

python -m bootstrap.smoke --web-url http://web:3000

Checks that the services answer, signed-out people are sent to sign in, the database and kill switches are in
place, the company repo is valid OKF without any dev-only files, the index is at the repo's head, the rules load,
the people are synthetic and no dev persona roles exist. Reports which scanner and file store are in use. Prints one line per check; exits 1 if any fails.
Never prints data, only counts and states.
"""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path

from core.config import get_settings
from core.db import connect
from okf.validate import validate_bundle
from repo_writer.git import Git
from rules.loader import RULE_PATHS, load_all

DEV_ONLY = (
    "taxonomy/clients/CLI-northwind-amc.md",
    "taxonomy/clients/CLI-tejas-amc.md",
    "taxonomy/clients/CLI-kaveri-infra.md",
)
SWITCHES = {
    "ai.all",
    "submissions",
    "attachments.upload",
    "attachments.open",
    "matching.show",
    "comms.email",
    "wall.public",
}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: object, **kwargs: object) -> None:
        return None


def _get(url: str, headers: dict[str, str] | None = None) -> tuple[int, dict[str, str]]:
    opener = urllib.request.build_opener(_NoRedirect)
    req = urllib.request.Request(url, headers=headers or {})  # noqa: S310 - the stack's own URLs
    try:
        with opener.open(req, timeout=10) as resp:
            return int(resp.status), dict(resp.headers)
    except urllib.error.HTTPError as err:
        return int(err.code), dict(err.headers)


def checks(web: str, worker: str, fresh: bool = False) -> list[tuple[str, Callable[[], tuple[bool, str]]]]:
    s = get_settings()
    repo = Path(s.company_repo_path)

    def worker_health() -> tuple[bool, str]:
        code, _ = _get(f"{worker}/internal/health")
        return code == 200, f"HTTP {code}"

    def web_health() -> tuple[bool, str]:
        code, _ = _get(f"{web}/api/health")
        return code == 200, f"HTTP {code}"

    def sign_in_page() -> tuple[bool, str]:
        code, _ = _get(f"{web}/sign-in")
        return code == 200, f"HTTP {code}"

    def api_needs_session() -> tuple[bool, str]:
        code, _ = _get(f"{web}/api/me")
        return code == 401, f"HTTP {code}"

    def pages_need_session() -> tuple[bool, str]:
        code, headers = _get(f"{web}/wall")
        where = headers.get("Location", headers.get("location", ""))
        return code in (302, 303, 307) and "/sign-in" in where, f"HTTP {code}"

    def internal_token() -> tuple[bool, str]:
        """The web app's own token reaches the worker (deep health), and a wrong token is refused."""
        code, _ = _get(f"{web}/api/health?deep=1")
        bad, _ = _get(f"{worker}/internal/token-check", {"X-Internal-Token": "not-the-token"})
        return code == 200 and bad in (401, 403), f"web deep health HTTP {code}, wrong token HTTP {bad}"

    def scanner() -> tuple[bool, str]:
        from attachments.clamav import ping

        host = urllib.parse.urlparse(s.s3_endpoint).hostname
        return ping(), f"scanner {s.clamav_host}:{s.clamav_port}; file store {host}"

    def kill_switches() -> tuple[bool, str]:
        with connect(autocommit=True) as conn:
            rows = conn.execute("SELECT name, state FROM kill_switches").fetchall()
        names = {r["name"] for r in rows}
        off = sorted(r["name"] for r in rows if r["state"] == "off")
        return names >= SWITCHES, f"{len(rows)} switches; off: {', '.join(off) or 'none'}"

    def company_repo() -> tuple[bool, str]:
        if not (repo / ".git").exists():
            return False, "not a Git repo"
        errors = [i for i in validate_bundle(repo) if i.level == "error"]
        dev = [p for p in DEV_ONLY if (repo / p).exists()] if s.is_production_like else []  # dev has them
        return not errors and not dev, f"{len(errors)} OKF errors; {len(dev)} dev-only files"

    def rules() -> tuple[bool, str]:
        loaded = load_all(repo)
        return set(RULE_PATHS) <= set(loaded), f"{len(loaded)} of {len(RULE_PATHS)} rule files"

    def index_at_head() -> tuple[bool, str]:
        head = Git(repo, s.repo_writer_author).head()
        with connect(autocommit=True) as conn:
            state = conn.execute("SELECT last_commit FROM index_state").fetchone()
            files = conn.execute("SELECT count(*) AS n FROM repo_files").fetchone()
        at = state["last_commit"] if state else None
        n = int(files["n"]) if files else 0
        return at == head and n > 0, f"{n} files indexed; {'at head' if at == head else 'behind head'}"

    def people() -> tuple[bool, str]:
        """Right after a fresh deploy: synthetic people only, and no role grants at all (no dev personas)."""
        with connect(autocommit=True) as conn:
            row = conn.execute(
                "SELECT count(*) AS n, count(*) FILTER (WHERE email NOT LIKE '%%@kfintech.example') AS other "
                "FROM users"
            ).fetchone()
            grants = conn.execute("SELECT count(*) AS n FROM role_grants").fetchone()
        assert row is not None and grants is not None
        ok = int(row["n"]) > 0 and (not fresh or (int(row["other"]) == 0 and int(grants["n"]) == 0))
        return (
            ok,
            f"{row['n']} people, {row['other']} outside the synthetic domain, {grants['n']} role grants",
        )

    def voice_notes() -> tuple[bool, str]:
        """DEC-096: voice notes are off, or on with the engine on KFin's own server; never the fake route outside
        dev and test. The quarantine bucket is never versioned (a version would outlive a delete)."""
        from attachments.store import versioning

        with connect(autocommit=True) as conn:
            row = conn.execute("SELECT state FROM kill_switches WHERE name = 'capture.voice'").fetchone()
        on = row is not None and row["state"] == "on"
        # On outside dev and test: only the engine on KFin's own server, through the isolated speech service
        # (BLD-C012); hosted routes need InfoSec and the DPO.
        mode_ok = (
            not on or not s.is_production_like or (s.speech_mode == "local" and bool(s.speech_engine_url))
        )
        try:
            versioned = versioning(s.s3_bucket_quarantine)
        except Exception:  # a store with no versioning at all (the dev gateway) cannot keep old versions
            versioned = "unsupported"
        return (
            mode_ok and versioned != "Enabled",
            f"capture.voice {'on' if on else 'off'}; SPEECH_MODE {s.speech_mode}; "
            f"isolated service {'set' if s.speech_engine_url else 'unset'}; quarantine versioning {versioned}",
        )

    return [
        ("worker answers", worker_health),
        ("web answers", web_health),
        ("sign-in page", sign_in_page),
        ("API needs a session", api_needs_session),
        ("pages send people to sign in", pages_need_session),
        ("web-to-worker token", internal_token),
        ("virus scanner answers", scanner),
        ("kill switches in place", kill_switches),
        ("company repo valid, no dev files", company_repo),
        ("rules load", rules),
        ("index at the repo head", index_at_head),
        ("people are synthetic, no dev personas", people),
        ("voice notes: safe speech route, quarantine not versioned", voice_notes),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--web-url", default="http://web:3000")
    parser.add_argument("--worker-url", default="http://localhost:8000")
    parser.add_argument("--fresh", action="store_true", help="right after a deploy from a clean database")
    args = parser.parse_args(argv)
    failed = 0
    for name, run in checks(args.web_url.rstrip("/"), args.worker_url.rstrip("/"), args.fresh):
        try:
            ok, detail = run()
        except Exception as exc:  # a check that cannot run is a failed check
            ok, detail = False, type(exc).__name__
        failed += not ok
        print(f"{'ok  ' if ok else 'FAIL'}  {name:38} {detail}")
    print("smoke: all checks passed" if not failed else f"smoke: {failed} check(s) failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
