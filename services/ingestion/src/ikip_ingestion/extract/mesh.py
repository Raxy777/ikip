"""Canonical mesh construction and deterministic metrics.

Both the STL handler (trimesh) and the STEP handler (OCCT tessellation) funnel their
geometry through here, so a `CanonicalMesh` and its `MeshMetrics` are computed identically
regardless of source format. Keeping this in one place means the part card and the
(Phase 3) shape descriptor see a single, engine-neutral representation.

numpy is a hard dependency (light); trimesh is used opportunistically for robust volume/
watertightness but the module degrades to pure-numpy metrics if a mesh object lacks them.
"""
from __future__ import annotations

import numpy as np

from ikip_ingestion.extract.types import (
    BoundingBox,
    CanonicalMesh,
    MeshMetrics,
)


def canonical_from_arrays(
    vertices: np.ndarray,
    faces: np.ndarray,
    *,
    units: str = "mm",
) -> CanonicalMesh:
    """Build a CanonicalMesh from (N,3) vertices and (M,3) integer faces."""
    v = np.asarray(vertices, dtype=float).reshape(-1, 3)
    f = np.asarray(faces, dtype=np.int64).reshape(-1, 3)
    return CanonicalMesh(
        vertices=[tuple(map(float, row)) for row in v],
        faces=[tuple(map(int, row)) for row in f],
        units=units,
    )


def metrics_from_arrays(
    vertices: np.ndarray,
    faces: np.ndarray,
    *,
    volume: float | None = None,
    surface_area: float | None = None,
    is_watertight: bool | None = None,
) -> MeshMetrics:
    """Compute deterministic metrics. Volume/area/watertight may be supplied by the engine.

    When area is not supplied it is computed from triangle cross-products (always possible).
    Volume and watertightness are left as provided (None if the engine could not decide),
    because a naive signed-volume on a non-watertight mesh would be misleading.
    """
    v = np.asarray(vertices, dtype=float).reshape(-1, 3)
    f = np.asarray(faces, dtype=np.int64).reshape(-1, 3)

    bbox: BoundingBox | None = None
    if v.size:
        bbox = BoundingBox(
            min_xyz=tuple(map(float, v.min(axis=0))),  # type: ignore[arg-type]
            max_xyz=tuple(map(float, v.max(axis=0))),  # type: ignore[arg-type]
        )

    if surface_area is None and f.size and v.size:
        tris = v[f]
        cross = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
        surface_area = float(0.5 * np.linalg.norm(cross, axis=1).sum())

    return MeshMetrics(
        vertex_count=int(v.shape[0]),
        face_count=int(f.shape[0]),
        bounding_box=bbox,
        volume=volume,
        surface_area=surface_area,
        is_watertight=is_watertight,
    )


def from_trimesh(mesh: object, *, units: str = "mm") -> tuple[CanonicalMesh, MeshMetrics]:
    """Build canonical mesh + metrics from a trimesh.Trimesh without importing trimesh here.

    Accepts anything exposing `.vertices`, `.faces`, and optionally `.volume`,
    `.area`, `.is_watertight` (duck-typed so the mesh module has no trimesh import).
    """
    vertices = np.asarray(getattr(mesh, "vertices"), dtype=float).reshape(-1, 3)
    faces = np.asarray(getattr(mesh, "faces"), dtype=np.int64).reshape(-1, 3)

    is_watertight = bool(getattr(mesh, "is_watertight", False)) or None
    volume = None
    if is_watertight:
        vol = getattr(mesh, "volume", None)
        volume = abs(float(vol)) if vol is not None else None
    area = getattr(mesh, "area", None)
    surface_area = float(area) if area is not None else None

    canonical = canonical_from_arrays(vertices, faces, units=units)
    metrics = metrics_from_arrays(
        vertices, faces, volume=volume, surface_area=surface_area, is_watertight=is_watertight
    )
    return canonical, metrics
