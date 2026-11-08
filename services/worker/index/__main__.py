"""python -m index [--rebuild] [--loop]   Index the company repo into the search tables."""

import argparse

from index.indexer import Indexer

parser = argparse.ArgumentParser()
parser.add_argument("--rebuild", action="store_true", help="drop the index and rebuild it from HEAD")
parser.add_argument("--loop", action="store_true", help="keep polling for new commits")
args = parser.parse_args()

indexer = Indexer()
if args.loop:
    indexer.run_forever()
else:
    r = indexer.run_once(rebuild=args.rebuild)
    print(f"indexed {r.to_commit}: {len(r.upserted)} upserted, {len(r.deleted)} deleted, rebuilt={r.rebuilt}")
