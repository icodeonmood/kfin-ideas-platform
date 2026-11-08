"""Text → 1,024-dimension unit vectors. `EMBEDDINGS_MODE=hash` (tests, B1) or `bge-m3` (B5, self-hosted)."""

from __future__ import annotations

import hashlib
import math
import re
from itertools import pairwise

from core.config import get_settings

DIMENSIONS = 1024
_TOKEN = re.compile(r"\w+", re.UNICODE)


def hash_embed(text: str) -> list[float]:
    """Deterministic feature-hashing vector: unigrams and bigrams, signed buckets, sqrt term weights.

    Identical texts give identical vectors and overlapping texts give positive cosine, which is all the
    tests need. It carries no meaning beyond word overlap; BGE-M3 replaces it outside tests.
    """
    tokens = [t.lower() for t in _TOKEN.findall(text)]
    features = tokens + [f"{a} {b}" for a, b in pairwise(tokens)]
    counts: dict[int, float] = {}
    for feat in features:
        digest = hashlib.blake2b(feat.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "big") % DIMENSIONS
        sign = 1.0 if digest[4] & 1 else -1.0
        counts[bucket] = counts.get(bucket, 0.0) + sign
    vec = [0.0] * DIMENSIONS
    for bucket, value in counts.items():
        vec[bucket] = math.copysign(math.sqrt(abs(value)), value)
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0.0:
        vec[0] = 1.0  # an empty text still needs a unit vector for cosine search
        return vec
    return [v / norm for v in vec]


def embed(texts: list[str]) -> list[list[float]]:
    mode = get_settings().embeddings_mode
    if mode == "hash":
        return [hash_embed(t) for t in texts]
    if mode == "bge-m3":
        raise NotImplementedError("BGE-M3 embeddings arrive in B5; use EMBEDDINGS_MODE=hash until then")
    raise ValueError(f"unknown EMBEDDINGS_MODE {mode!r}")
