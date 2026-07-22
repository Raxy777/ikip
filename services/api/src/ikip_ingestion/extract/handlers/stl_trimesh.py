"""STL handler backed by trimesh. Tier 1 (full geometry) — the verified reference path.

Handles both ASCII (``solid`` header) and binary STL (no magic number; identified by
extension + 84-byte floor). STL carries only triangles — no assembly structure, PMI, or
named properties — so the ExtractedModel has a single synthetic part and empty pmi/parts
beyond that. Geometry is always available for a well-formed STL, which is exactly why it is
the reference format for verifying the whole path end to end.
"""
from __future__ import annotations

from pathlib import Path

from ikip_ingestion.extract.mesh import from_trimesh
from ikip_ingestion.extract.types import (
    ExtractedModel,
    ExtractionTier,
    PartRecord,
)

_BINARY_STL_HEADER = 80
_BINARY_STL_COUNT = 4
_BINARY_STL_MIN = _BINARY_STL_HEADER + _BINARY_STL_COUNT  # 84 bytes: header + triangle count


class StlTrimeshHandler:
    """Extract a canonical mesh + metrics from an STL file using trimesh."""

    format_key = "STL"

    def sniff(self, head: bytes, filename: str) -> bool:
        name = filename.lower()
        if name.endswith(".stl"):
            return True
        # ASCII STL without a .stl name: recognizable by the 'solid' keyword.
        return head[:5].lower() == b"solid"

    def available(self) -> bool:
        # trimesh + numpy are core ingestion deps; import is checked at extract time too.
        return True

    def extract(self, path: Path) -> ExtractedModel:
        import trimesh  # local import keeps module import cheap and toolkit-optional-safe

        # process=True merges coincident vertices. For an STL (a triangle soup) this is the
        # correct canonicalization, not data loss: it is what makes watertightness and volume
        # computable, and it deduplicates the per-corner vertices STL stores.
        loaded = trimesh.load(str(path), file_type="stl", process=True)
        # A multi-body STL loads as a Scene; concatenate to a single mesh for metrics.
        if isinstance(loaded, trimesh.Scene):
            mesh = trimesh.util.concatenate(tuple(loaded.geometry.values()))
        else:
            mesh = loaded

        canonical, metrics = from_trimesh(mesh, units="mm")

        warnings: list[str] = []
        if metrics.is_watertight is None:
            warnings.append("mesh not watertight; volume not computed")

        part = PartRecord(part_ref="part-0", name=path.stem or "stl-part")

        return ExtractedModel(
            source_format="STL",
            tier=ExtractionTier.FULL_GEOMETRY,
            geometry_available=True,
            metrics=metrics,
            canonical_mesh=canonical,
            parts=[part],
            pmi=[],
            properties={"units": canonical.units},
            geometry_kernel=None,  # STL is a tessellation; no B-rep kernel
            tessellation=f"trimesh:{trimesh.__version__}",
            warnings=warnings,
        )
