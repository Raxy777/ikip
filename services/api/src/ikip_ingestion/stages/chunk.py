"""Ingestion stage: chunk — CAD chunking (§B).

Turns an ExtractedModel into governed chunks. For CAD this is not fixed-length text
splitting; it is structure-aware:

  - PART CARD  : one chunk per part summarizing name, part number, tier, format, and
                 geometry metrics (bbox, volume, area, watertight). This is the primary
                 retrievable text, so a plain text query ("pump housing 30mm bore") can
                 surface the part through the existing semantic channel.
  - PMI        : one chunk per PMI note (GD&T, tolerances, datums), each carrying the CAD
                 source coordinate of the entity it annotates.
  - PROPERTY   : one chunk of the file's named properties (material, mass, custom fields).

Every chunk carries full provenance including CAD source_coordinates, so any claim built on
it can be cited back to the exact part/face/PMI entity.
"""
from __future__ import annotations

from dataclasses import dataclass

from ikip_contracts import Provenance

from ikip_ingestion.extract.types import ExtractedModel

CHUNKER_VERSION = "cad-structural:0.1"


@dataclass(frozen=True)
class Chunk:
    """A governed, indexable unit with provenance. `kind` distinguishes CAD chunk types."""

    chunk_id: str
    document_id: str
    kind: str  # "part_card" | "pmi" | "property" | "text"
    text: str
    source_coordinates: dict
    provenance: Provenance


def _fmt_metrics(model: ExtractedModel) -> str:
    m = model.metrics
    if m is None:
        return "geometry: not available"
    parts = [f"triangles={m.face_count}", f"vertices={m.vertex_count}"]
    if m.bounding_box is not None:
        sx, sy, sz = (round(v, 2) for v in m.bounding_box.size)
        parts.append(f"bbox={sx}x{sy}x{sz}")
    if m.volume is not None:
        parts.append(f"volume={round(m.volume, 2)}")
    if m.surface_area is not None:
        parts.append(f"area={round(m.surface_area, 2)}")
    if m.is_watertight is not None:
        parts.append(f"watertight={m.is_watertight}")
    return "geometry: " + ", ".join(parts)


def chunk_model(
    model: ExtractedModel,
    *,
    document_id: str,
    provenance: Provenance,
) -> list[Chunk]:
    """Produce part-card, PMI, and property chunks from an ExtractedModel.

    `provenance` is the base provenance for this document version; each chunk records its
    own CAD source_coordinates so citations resolve to the right entity.
    """
    chunks: list[Chunk] = []
    n = 0

    # --- Part cards (one per part; a single part file yields exactly one) ---------------
    for part in model.parts or []:
        coord = {
            "cad_entity_type": "part",
            "cad_part_ref": part.part_ref,
            "cad_label": part.name,
        }
        header = f"Part: {part.name or part.part_ref}"
        if part.part_number:
            header += f" (P/N {part.part_number})"
        text = "\n".join(
            [header, f"format: {model.source_format}, tier: {model.tier.value}", _fmt_metrics(model)]
        )
        chunks.append(
            Chunk(
                chunk_id=f"{document_id}:part_card:{n}",
                document_id=document_id,
                kind="part_card",
                text=text,
                source_coordinates=coord,
                provenance=provenance,
            )
        )
        n += 1

    # --- PMI notes ----------------------------------------------------------------------
    for i, note in enumerate(model.pmi or []):
        chunks.append(
            Chunk(
                chunk_id=f"{document_id}:pmi:{i}",
                document_id=document_id,
                kind="pmi",
                text=note.text,
                source_coordinates=note.coordinate.as_dict(),
                provenance=provenance,
            )
        )

    # --- Properties (one combined chunk when present) -----------------------------------
    if model.properties:
        prop_text = "\n".join(f"{k}: {v}" for k, v in sorted(model.properties.items()))
        chunks.append(
            Chunk(
                chunk_id=f"{document_id}:property:0",
                document_id=document_id,
                kind="property",
                text="Properties\n" + prop_text,
                source_coordinates={"cad_entity_type": "property"},
                provenance=provenance,
            )
        )

    return chunks
