"""AT-B5-01 (UAT): `python -m embeddings.check` — vectors are 1,024-dimensional and normalised, and a card and
its paraphrase score cosine 0.80 or more. Synthetic sentences only."""

from __future__ import annotations

import math
import sys

from embeddings import embed

CARD = "SIP registrations slip by a day because ops re-check every form by hand for missing bank details."
PARAPHRASE = (
    "Every SIP form is manually rechecked for missing bank fields, which delays registration by one day."
)


def main() -> int:
    a, b = embed([CARD, PARAPHRASE])
    dims = len(a) == 1024 and len(b) == 1024
    norms = all(abs(math.sqrt(sum(x * x for x in v)) - 1.0) < 1e-3 for v in (a, b))
    cos = sum(x * y for x, y in zip(a, b, strict=True))
    print(f"dimensions 1024: {dims} · normalised: {norms} · paraphrase cosine: {cos:.3f} (needs ≥ 0.80)")
    return 0 if dims and norms and cos >= 0.80 else 1


if __name__ == "__main__":
    sys.exit(main())
