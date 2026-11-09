"""The arithmetic of the weekly clustering batch (§4.4 B steps 3–5), kept free of the database so it can be
tested on its own. Vectors are unit-normalised card embeddings; distance is cosine distance (1 − cosine).

Grouping is average-linkage agglomerative clustering cut at a distance threshold, for every pool size
(BLD-202: the spec's UMAP + HDBSCAN path for pools of 200 or more is not built; average linkage is exact,
deterministic and needs no seed, and its O(n²) memory fits the year-one pool). It uses the nearest-neighbour
chain algorithm, which gives the same tree as the textbook method in O(n²) time.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

Matrix = NDArray[np.float64]


def normalise(vectors: Sequence[Sequence[float]] | Matrix) -> Matrix:
    m = np.asarray(vectors, dtype=np.float64)
    if m.ndim != 2 or m.shape[0] == 0:
        return m.reshape(0, 0) if m.size == 0 else m
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return np.asarray(m / norms, dtype=np.float64)


def cosine(a: Matrix, b: Matrix) -> float:
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def centroid(vectors: Matrix) -> Matrix:
    """Mean of member vectors, normalised (§4.4 B step 9)."""
    c = np.asarray(vectors, dtype=np.float64).mean(axis=0)
    n = float(np.linalg.norm(c))
    return np.asarray(c / n if n else c, dtype=np.float64)


def average_linkage(vectors: Matrix, threshold: float) -> list[list[int]]:
    """Groups of row indices whose average-linkage merge distance is at most `threshold`. Singletons included.
    Output is sorted (each group ascending, groups by their first index) so runs are repeatable."""
    n = int(vectors.shape[0])
    if n == 0:
        return []
    if n == 1:
        return [[0]]
    v = normalise(vectors)
    dist = 1.0 - v @ v.T
    np.fill_diagonal(dist, np.inf)
    size = np.ones(n)
    active = np.ones(n, dtype=bool)
    merges: list[tuple[float, int, int]] = []
    chain: list[int] = []
    remaining = n
    while remaining > 1:
        if not chain:
            chain.append(int(np.flatnonzero(active)[0]))
        a = chain[-1]
        row = np.where(active, dist[a], np.inf)
        row[a] = np.inf
        b = int(np.argmin(row))
        # Prefer the previous element of the chain on ties, so the chain always ends in a reciprocal pair.
        if len(chain) > 1 and row[chain[-2]] <= row[b]:
            b = chain[-2]
        if len(chain) > 1 and b == chain[-2]:
            chain.pop()
            chain.pop()
            d = float(dist[a, b])
            merges.append((d, a, b))
            # Lance–Williams update for average linkage: the merged cluster keeps index `a`.
            new = (size[a] * dist[a] + size[b] * dist[b]) / (size[a] + size[b])
            dist[a, :] = new
            dist[:, a] = new
            dist[a, a] = np.inf
            dist[b, :] = np.inf
            dist[:, b] = np.inf
            size[a] += size[b]
            active[b] = False
            remaining -= 1
        else:
            chain.append(b)
    # Cut: average linkage is monotone, so the groups at the threshold are the unions of every merge at or below it.
    # Each merge names the two leaves that represented its clusters, so unioning those leaves joins the clusters.
    uf = UnionFind(range(n))
    for d, a, b in sorted(merges, key=lambda m: m[0]):
        if d > threshold:
            break
        uf.union(a, b)
    return uf.groups()


class UnionFind:
    def __init__(self, items: Iterable[int]) -> None:
        self.parent: dict[int, int] = {i: i for i in items}

    def find(self, x: int) -> int:
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)

    def groups(self) -> list[list[int]]:
        out: dict[int, list[int]] = {}
        for x in sorted(self.parent):
            out.setdefault(self.find(x), []).append(x)
        return sorted(out.values(), key=lambda g: g[0])


def apply_constraints(
    groups: list[list[int]],
    must: Iterable[tuple[int, int]],
    cannot: Iterable[tuple[int, int]],
    order: Sequence[str],
) -> list[list[int]]:
    """§4.4 B step 4. Groups joined by a must-link are merged. Where a cannot-link pair lands in one group, the
    later idea (by ID, `order[i]`) leaves the group and stays on its own (BLD-203: the simpler reading of "move
    it to its next-nearest group or leave it on its own"). A must-link never overrides a cannot-link."""
    n = sum(len(g) for g in groups)
    uf = UnionFind(range(n))
    for g in groups:
        for x in g[1:]:
            uf.union(g[0], x)
    for a, b in must:
        uf.union(a, b)
    merged = uf.groups()
    banned = {(min(a, b), max(a, b)) for a, b in cannot}
    out: list[list[int]] = []
    for g in merged:
        keep: list[int] = []
        alone: list[int] = []
        for x in sorted(g, key=lambda i: order[i]):
            if any((min(x, y), max(x, y)) in banned for y in keep):
                alone.append(x)
            else:
                keep.append(x)
        out.append(sorted(keep))
        out.extend([x] for x in alone)
    return sorted(out, key=lambda g: g[0])


def medoid(vectors: Matrix) -> int:
    """Index of the most central member: the highest mean cosine to the others."""
    v = normalise(vectors)
    if v.shape[0] <= 2:
        return 0
    sims = v @ v.T
    return int(np.argmax(sims.sum(axis=1)))


def jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a or b else 0.0


@dataclass
class Existing:
    """An approved cluster: its current members and centroid."""

    id: str
    members: set[str]
    centroid: Matrix | None


@dataclass
class Proposal:
    kind: str  # new | grow | merge | split
    members: list[str]
    targets: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)
    groups: list[list[str]] = field(default_factory=list)  # split: the member groups


def classify(
    group: set[str],
    group_centroid: Matrix,
    anchors: set[str],
    clusters: Sequence[Existing],
    t: dict[str, float],
) -> Proposal | None:
    """§4.4 B step 5 for one group of ideas. `anchors` are the approved clusters whose centroid fell into this
    group; their members count as part of the group for the overlap. Returns None for "no change"."""
    effective = set(group)
    for c in clusters:
        if c.id in anchors:
            effective |= c.members
    overlaps = {c.id: jaccard(effective, c.members) for c in clusters}
    touched = sorted(cid for cid, j in overlaps.items() if j > 0)
    if len(touched) >= 2:
        return Proposal(
            "merge", sorted(effective), touched, {f"overlap_{c}": round(overlaps[c], 3) for c in touched}
        )
    if len(touched) == 1:
        c = next(x for x in clusters if x.id == touched[0])
        adds = sorted(group - c.members)
        if overlaps[c.id] >= t["grow_overlap"] and adds:
            return Proposal("grow", adds, [c.id], {"overlap": round(overlaps[c.id], 3)})
        return None
    if len(group) < 2:
        return None
    best = max((cosine(group_centroid, c.centroid) for c in clusters if c.centroid is not None), default=0.0)
    if best < t["new_max_centroid"]:
        return Proposal("new", sorted(group), [], {"nearest_centroid": round(best, 3)})
    return None


def merges_by_centroid(clusters: Sequence[Existing], threshold: float) -> list[Proposal]:
    """Two approved clusters whose centroids reach `merge_centroid` are proposed for merging."""
    out: list[Proposal] = []
    with_c = [c for c in clusters if c.centroid is not None]
    for i, a in enumerate(with_c):
        for b in with_c[i + 1 :]:
            assert a.centroid is not None and b.centroid is not None
            cos = cosine(a.centroid, b.centroid)
            if cos >= threshold:
                out.append(
                    Proposal(
                        "merge",
                        sorted(a.members | b.members),
                        sorted([a.id, b.id]),
                        {"centroid": round(cos, 3)},
                    )
                )
    return out


def splits(
    clusters: Sequence[Existing],
    groups: Sequence[tuple[set[str], Matrix]],
    threshold: float,
) -> list[Proposal]:
    """A cluster whose members fall into two or more groups of at least 2 each, with cosine between the groups
    below `split_between`, is proposed for a split."""
    out: list[Proposal] = []
    for c in clusters:
        parts = [(g & c.members, cen) for g, cen in groups if len(g & c.members) >= 2]
        if len(parts) < 2:
            continue
        far = all(
            cosine(parts[i][1], parts[j][1]) < threshold
            for i in range(len(parts))
            for j in range(i + 1, len(parts))
        )
        if far:
            out.append(
                Proposal(
                    "split",
                    sorted(set().union(*(p[0] for p in parts))),
                    [c.id],
                    {"parts": float(len(parts))},
                    [sorted(p[0]) for p in parts],
                )
            )
    return out
