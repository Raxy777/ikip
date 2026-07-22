"""CAD/mesh extraction subsystem.

Converts untrusted CAD and mesh files into a normalized `ExtractedModel` that the ingestion
stages consume without knowing the source format. Formats are added by registering a handler
(see `registry.default_registry`); stages never change.

Tiered by how much a handler can recover:
  Tier 1 (FULL_GEOMETRY)   — STEP, STL: B-rep/mesh read, canonical mesh + metrics.
  Tier 2 (METADATA_ONLY)   — proprietary parts: properties/thumbnail, no geometry. (Phase 2)
  Tier 3 (NEEDS_CONVERSION)— convert to a neutral format, then re-ingest as Tier 1. (Phase 4)
"""
from ikip_ingestion.extract.registry import (
    Handler,
    HandlerRegistry,
    default_registry,
)
from ikip_ingestion.extract.sandbox import (
    HandlerUnavailable,
    SandboxFailure,
    SandboxResult,
    run_sandboxed,
)
from ikip_ingestion.extract.types import (
    BoundingBox,
    CadCoordinate,
    CanonicalMesh,
    ExtractedModel,
    ExtractionTier,
    MeshMetrics,
    PartRecord,
    PmiNote,
)

__all__ = [
    "Handler",
    "HandlerRegistry",
    "default_registry",
    "HandlerUnavailable",
    "SandboxFailure",
    "SandboxResult",
    "run_sandboxed",
    "BoundingBox",
    "CadCoordinate",
    "CanonicalMesh",
    "ExtractedModel",
    "ExtractionTier",
    "MeshMetrics",
    "PartRecord",
    "PmiNote",
]
