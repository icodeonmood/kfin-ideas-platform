"""Check every local service's health endpoint (AT-B1-01). Used by `make up` and `make health`.

python -m core.health [--timeout 120]   exits 0 when every check passes within the timeout.
"""

from __future__ import annotations

import argparse
import socket
import sys
import time
import urllib.request
from collections.abc import Callable

import psycopg

from core.config import get_settings


def _http(url: str) -> Callable[[], bool]:
    def check() -> bool:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:  # noqa: S310 - fixed local URLs
                return bool(resp.status == 200)
        except OSError:
            return False

    return check


def _clamd(host: str, port: int) -> Callable[[], bool]:
    def check() -> bool:
        try:
            with socket.create_connection((host, port), timeout=2) as s:
                s.sendall(b"zPING\0")
                return s.recv(16).startswith(b"PONG")
        except OSError:
            return False

    return check


def _postgres(url: str) -> Callable[[], bool]:
    def check() -> bool:
        try:
            with psycopg.connect(url, connect_timeout=2) as conn:
                return conn.execute("SELECT 1").fetchone() == (1,)
        except psycopg.Error:
            return False

    return check


def checks() -> dict[str, Callable[[], bool]]:
    s = get_settings()
    return {
        "postgres": _postgres(s.database_url),
        "s3": _http(f"{s.s3_endpoint.rstrip('/')}/health"),
        "clamav": _clamd(s.clamav_host, s.clamav_port),
        "mock-oidc": _http(f"{s.oidc_issuer.rstrip('/')}/.well-known/openid-configuration"),
        "mailpit": _http(f"http://localhost:{s.mailpit_ui_host_port}/readyz"),
        "worker": _http(f"{s.worker_url.rstrip('/')}/internal/health"),
        "web": _http(f"{s.app_base_url.rstrip('/')}/api/health"),
    }


def wait_healthy(timeout: float) -> dict[str, float | None]:
    """Seconds until each service first answered 200 (None if it never did)."""
    start = time.monotonic()
    pending = checks()
    ready: dict[str, float | None] = dict.fromkeys(pending)
    while pending and time.monotonic() - start < timeout:
        for name, check in list(pending.items()):
            if check():
                ready[name] = round(time.monotonic() - start, 1)
                del pending[name]
        if pending:
            time.sleep(1)
    return ready


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args(argv)
    ready = wait_healthy(args.timeout)
    for name, secs in ready.items():
        print(f"{'ok  ' if secs is not None else 'FAIL'} {name:10} {'' if secs is None else f'{secs}s'}")
    return 0 if all(v is not None for v in ready.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
