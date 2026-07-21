"""Ingestion stage: validate — schema/evidence gate for CAD chunks.

Before a chunk is written to the governed store it must pass a structural gate, mirroring
the retrieval-side rule that unsupported content never surfaces. For CAD chunks:

  - every chunk has non-empty text and a stable chunk_id;
  - provenance carries the CAD extraction versions (parser + extraction_tier at minimum),
    so a chunk can always be reproduced or invalidated;
  - a chunk that CLAIMS a geometric source (part_card / pmi) must carry CAD
    source_coordinates identifying the entity — no un-anchored geometric claims;
  - property chunks may use the generic property coordinate.

A failing chunk is dropped from the write set with a reason, never silently written.
"""
from __future__ import annotations

from dataclasses import dataclass

from ikip_ingestion.stages.chunk import Chunk

_GEOMETRIC_KINDS = {"part_card", "pmi"}
_COORD_REQUIRED_KEYS = ("cad_entity_type",)


@dataclass(frozen=True)
class ValidationOutcome:
    valid: list[Chunk]
    rejected: list[tuple[Chunk, str]]

    @property
    def ok(self) -> bool:
        return not self.rejected


def _validate_chunk(chunk: Chunk) -> str | None:
    """Return a rejection reason, or None if the chunk passes the gate."""
    if not chunk.chunk_id:
        return "missing chunk_id"
    if not chunk.text or not chunk.text.strip():
        return "empty chunk text"

    pv = chunk.provenance.processing_versions
    if not pv.parser:
        return "provenance missing parser"
    if pv.extraction_tier is None:
        return "CAD chunk missing extraction_tier in provenance"

    if chunk.kind in _GEOMETRIC_KINDS:
        coords = chunk.source_coordinates or {}
        if not any(k in coords for k in _COORD_REQUIRED_KEYS):
            return f"{chunk.kind} chunk missing CAD source_coordinates"
    return None


def validate_chunks(chunks: list[Chunk]) -> ValidationOutcome:
    """Split chunks into those that may be written and those rejected with a reason."""
    valid: list[Chunk] = []
    rejected: list[tuple[Chunk, str]] = []
    for c in chunks:
        reason = _validate_chunk(c)
        if reason is None:
            valid.append(c)
        else:
            rejected.append((c, reason))
    return ValidationOutcome(valid=valid, rejected=rejected)
