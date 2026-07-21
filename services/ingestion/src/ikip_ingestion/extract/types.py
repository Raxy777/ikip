"""Core types for CAD/mesh extraction.

`ExtractedModel` is the normalized result every handler produces, regardless of source
format (STEP, STL, and later OLE-wrapped proprietary parts). Downstream stages consume
ONLY this type, so adding a format means adding a handler — never touching the stages.

Design invariants:
  - A handler NEVER returns partial-but-unmarked data. If geometry could not be read, it
    sets `geometry_available=False` and populates whatever metadata it could, so the
    tiered model (Tier 1 full geometry / Tier 2 metadata-only / Tier 3 needs conversion)
    is explicit rather than inferred.
  - Extracted text/metadata is DATA, never instruction (same untrusted-content rule as the
    rest of ingestion). Handlers must not execute anything found inside a file.
  - Every derived chunk can point back to a `CadCoordinate`, so a PMI note or property can
    be cited to the exact geometric entity it came from.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ExtractionTier(str, Enum):
    """How much a handler could recover from a file.

    FULL_GEOMETRY : boundary representation read; canonical mesh + metrics available.
    METADATA_ONLY : properties/thumbnail recovered, but no usable geometry (e.g. a native
                    proprietary part with no neutral geometry inside).
    NEEDS_CONVERSION : recognized but not directly readable; requires a converter pass
                    before it can be re-ingested as Tier 1.
    BLOCKED       : recognized and deliberately not processed (policy/format block).
    """

    FULL_GEOMETRY = "full_geometry"
    METADATA_ONLY = "metadata_only"
    NEEDS_CONVERSION = "needs_conversion"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class CadCoordinate:
    """A citable location inside a CAD model.

    Mirrors the CAD form of provenance.source_coordinates. Fields are optional because
    different formats expose different handles; at least one should be set for a chunk that
    claims a geometric source.
    """

    entity_type: str | None = None  # "solid" | "face" | "edge" | "pmi" | "property" | "part"
    entity_id: str | None = None  # kernel handle / persistent id where available
    part_ref: str | None = None  # owning part identifier within an assembly
    label: str | None = None  # human-facing label (feature/property name)

    def as_dict(self) -> dict:
        """Serialize to the open-ended dict stored in provenance.source_coordinates."""
        return {k: v for k, v in {
            "cad_entity_type": self.entity_type,
            "cad_entity_id": self.entity_id,
            "cad_part_ref": self.part_ref,
            "cad_label": self.label,
        }.items() if v is not None}


@dataclass(frozen=True)
class BoundingBox:
    """Axis-aligned bounding box in model units (millimetres unless the file says otherwise)."""

    min_xyz: tuple[float, float, float]
    max_xyz: tuple[float, float, float]

    @property
    def size(self) -> tuple[float, float, float]:
        return tuple(hi - lo for hi, lo in zip(self.max_xyz, self.min_xyz))  # type: ignore[return-value]


@dataclass(frozen=True)
class MeshMetrics:
    """Cheap, deterministic geometry metrics used for the part card and sanity checks."""

    vertex_count: int
    face_count: int
    bounding_box: BoundingBox | None = None
    volume: float | None = None
    surface_area: float | None = None
    is_watertight: bool | None = None


@dataclass(frozen=True)
class CanonicalMesh:
    """The normalized tessellation kept for downstream use (shape descriptors, previews).

    Stored as flat vertex/face arrays so it is engine-neutral and cheaply serializable.
    `units` records the source unit so a consumer never assumes millimetres.
    """

    vertices: list[tuple[float, float, float]]
    faces: list[tuple[int, int, int]]
    units: str = "mm"


@dataclass(frozen=True)
class PmiNote:
    """A single Product Manufacturing Information item (GD&T, note, datum, tolerance)."""

    text: str
    coordinate: CadCoordinate


@dataclass(frozen=True)
class PartRecord:
    """One part in an assembly (or the single part of a part file)."""

    part_ref: str
    name: str | None = None
    part_number: str | None = None
    properties: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ExtractedModel:
    """The normalized output of any CAD/mesh handler. Downstream stages consume only this."""

    source_format: str  # "STEP" | "STL" | ...
    tier: ExtractionTier
    geometry_available: bool
    # Geometry (present only for FULL_GEOMETRY).
    metrics: MeshMetrics | None = None
    canonical_mesh: CanonicalMesh | None = None
    # Structure & semantics.
    parts: list[PartRecord] = field(default_factory=list)
    pmi: list[PmiNote] = field(default_factory=list)
    properties: dict[str, str] = field(default_factory=dict)
    # Handler-declared processing versions (kernel/tessellation), merged into provenance.
    geometry_kernel: str | None = None
    tessellation: str | None = None
    # Non-fatal notes for observability (e.g. "no PMI present", "units assumed mm").
    warnings: list[str] = field(default_factory=list)

    @property
    def is_root_part(self) -> bool:
        return len(self.parts) == 1
