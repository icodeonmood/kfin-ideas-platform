"""Text → 1,024-dimension unit vectors. `EMBEDDINGS_MODE=hash` (tests, B1) or `bge-m3` (B5, self-hosted)."""

from __future__ import annotations

import hashlib
import math
import re
from itertools import pairwise
from typing import Any

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
        return _bge_m3(texts)
    raise ValueError(f"unknown EMBEDDINGS_MODE {mode!r}")


_model: Any = None


def _bge_m3(texts: list[str]) -> list[list[float]]:
    """BGE-M3 dense vectors (1,024 dimensions, normalised), self-hosted in the worker (BLD-080). The model files
    come from `EMBEDDINGS_MODEL_PATH` (never fetched at run time, never in Git); the library is installed only in
    images built with `--build-arg WITH_BGE=1` (UAT and prod). AT-B5-01 is checked with `python -m embeddings.check`."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]
        except ImportError:
            raise RuntimeError("EMBEDDINGS_MODE=bge-m3 needs an image built with WITH_BGE=1") from None
        path = get_settings().embeddings_model_path
        if not path:
            raise RuntimeError("EMBEDDINGS_MODEL_PATH is not set")
        _model = SentenceTransformer(path, device="cpu", local_files_only=True)
    vectors = _model.encode(texts, normalize_embeddings=True, batch_size=16)
    return [[float(x) for x in v] for v in vectors]
