"""python -m repo_writer [--once]   Run the repo writer (loop by default)."""

import argparse
import sys

from repo_writer.writer import RepoWriter

parser = argparse.ArgumentParser()
parser.add_argument("--once", action="store_true", help="commit pending events, then exit")
args = parser.parse_args()

writer = RepoWriter()
if args.once:
    if not writer.acquire():
        print("another repo writer holds the lock")
        sys.exit(3)
    try:
        print(f"committed {len(writer.run_once(limit=10_000))} events")
    finally:
        writer.release()
else:
    writer.run_forever()
