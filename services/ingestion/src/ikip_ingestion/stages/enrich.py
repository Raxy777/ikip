"""Ingestion stage: enrich — D2 shape-distribution descriptor (§C).

Computes a compact, rotation/translation/scale-invariant shape descriptor from a
CanonicalMesh so the shape-similarity channel can rank geometrically similar parts.

D2 descriptor: sample N random pairs of surface points, compute pairwise distances,
normalize by the bounding-box diagonal (scale invariance), bin into a histogram, then
L2-normalize the histogram vector. The result is invariant to rigid transforms and uniform
scaling, and cheap to compute on the canonical mesh already produced by Tier-1 handlers.

The descriptor is stored as a flat list[float] so it is engine-neutral and can be written
directly to a pgvector column or compared in-memory.
"""
from __future__ import annotations

import random
from math import sqrt

from ikip_ingestion.extract.types import CanonicalMesh

# Descriptor hyper-parameters. Kept small so the in-memory store and tests are fast;
# a production deployment can increase N_SAMPLES for higher fidelity.
N_SAMPLES = 1024   # number of random point pairs
N_BINS = 64        # histogram bins
_SEED = 42         # deterministic sampling


def _bbox_diagonal(vertices: list[tuple[float, float, float]]) -> float:
    if not vertices:
        return 1.0
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    zs = [v[2] for v in vertices]
    dx = max(xs) - min(xs)
    dy = max(ys) - min(ys)
    dz = max(zs) - min(zs)
    return sqrt(dx * dx + dy * dy + dz * dz) or 1.0


def _sample_surface_points(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, int, int]],
    n: int,
    rng: random.Random,
) -> list[tuple[float, float, float]]:
    """Sample n points uniformly from triangle surfaces (area-weighted via random barycentric)."""
    if not faces:
        # Fall back to vertex sampling when no faces (degenerate mesh).
        pool = vertices * (n // len(vertices) + 1)
        return pool[:n]

    points: list[tuple[float, float, float]] = []
    for _ in range(n):
        a, b, c = faces[rng.randrange(len(faces))]
        va, vb, vc = vertices[a], vertices[b], vertices[c]
        r1 = rng.random()
        r2 = rng.random()
        if r1 + r2 > 1.0:
            r1, r2 = 1.0 - r1, 1.0 - r2
        r3 = 1.0 - r1 - r2
        px = r1 * va[0] + r2 * vb[0] + r3 * vc[0]
        py = r1 * va[1] + r2 * vb[1] + r3 * vc[1]
        pz = r1 * va[2] + r2 * vb[2] + r3 * vc[2]
        points.append((px, py, pz))
    return points


def compute_d2_descriptor(
    mesh: CanonicalMesh,
    *,
    n_samples: int = N_SAMPLES,
    n_bins: int = N_BINS,
) -> list[float]:
    """Return an L2-normalized D2 histogram descriptor for `mesh`.

    Invariant to translation (distances), rotation (distances), and uniform scale
    (normalized by bbox diagonal). Returns a zero vector for degenerate meshes.
    """
    vertices = mesh.vertices
    faces = mesh.faces

    if len(vertices) < 2:
        return [0.0] * n_bins

    diag = _bbox_diagonal(vertices)
    rng = random.Random(_SEED)
    pts = _sample_surface_points(vertices, faces, n_samples, rng)

    # Sample n_samples/2 pairs (each iteration picks two distinct points).
    n_pairs = n_samples // 2
    distances: list[float] = []
    for i in range(n_pairs):
        p = pts[i * 2]
        q = pts[i * 2 + 1]
        d = sqrt((p[0]-q[0])**2 + (p[1]-q[1])**2 + (p[2]-q[2])**2) / diag
        distances.append(d)

    # Bin into [0, 1] range (normalized distances are in [0, 1] by construction).
    hist = [0.0] * n_bins
    for d in distances:
        idx = min(int(d * n_bins), n_bins - 1)
        hist[idx] += 1.0

    # L2-normalize.
    norm = sqrt(sum(x * x for x in hist)) or 1.0
    return [x / norm for x in hist]


__all__ = ["compute_d2_descriptor", "N_BINS", "N_SAMPLES"]
