"""python -m reconcile [--report-only]   prints the drift counts; exits 1 if any drift was found."""

from __future__ import annotations

import argparse
import sys

from reconcile import run


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-only", action="store_true", help="find drift but change nothing")
    args = parser.parse_args()
    drift = run(fix=not args.report_only)
    for name, n in drift.counts().items():
        print(f"{name:26} {n}")
    print(f"{'idea_stage_lag (not drift)':26} {len(drift.idea_stage_mismatch)}")
    if drift.unfixable:
        print(f"{'could not fix':26} {len(drift.unfixable)}")
    print(f"fixed: {drift.fixed}" if drift.total else "reconcile: no drift")
    return 1 if drift.total else 0


if __name__ == "__main__":
    sys.exit(main())
