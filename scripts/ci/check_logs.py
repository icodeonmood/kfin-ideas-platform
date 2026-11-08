#!/usr/bin/env python3
"""Scan log streams for idea text or personal data (non-negotiable 3, AT-B1-10, AT-B8-08).

Usage:  docker compose logs --no-color --no-log-prefix web worker | python scripts/ci/check_logs.py -
        python scripts/ci/check_logs.py app.log other.log
Run from services/worker (`uv run`) so it shares the pattern rules. Exit 0 = clean, 1 = violations.
Only the line number, kind and field path are printed, never the offending value.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "worker"))

from pii.log_rules import scan_log_lines  # noqa: E402


def main(argv: list[str]) -> int:
    sources = argv[1:] or ["-"]
    total = 0
    for src in sources:
        lines = sys.stdin.read().splitlines() if src == "-" else Path(src).read_text(encoding="utf-8").splitlines()
        violations = scan_log_lines(lines)
        total += len(violations)
        for v in violations:
            print(f"{src}:{v.line_no}: {v.kind} {v.where}")
        print(f"{src}: {len(lines)} lines, {len(violations)} violations")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
