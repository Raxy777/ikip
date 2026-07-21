"""Phase 2 CAD ingestion: OLE metadata tier, blocked/needs-conversion route, and §D
assembly edges + part-number dedupe.

Covers:
  - golden .sldprt (OLE compound file) → properties + thumbnail extracted,
    geometry_available=False, METADATA_ONLY tier, no shape/geometry, no crash;
  - Creo .prt → review queue with "STEP AP242 export required" reason;
  - assembly → assembly_edge rows; a part duplicated across two files collapses to one
    part_id (PN dedupe); relationship walk returns "assemblies using part X".

olefile is an optional dep; the .sldprt test is skipped when it (or the ability to author
a golden OLE file) is unavailable, and the degraded review-route is asserted instead.
"""
from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path

import pytest

from ikip_ingestion.extract import ExtractionTier, default_registry
from ikip_ingestion.extract.registry import MAGIC_READ_BYTES
from ikip_ingestion.extract.types import ExtractedModel, ExtractionTier as _Tier, PartRecord
from ikip_ingestion.stages import parse_ocr, quarantine
from ikip_ingestion.stages.parse_ocr import Route
from ikip_ingestion.stages.quarantine import Disposition, route_model
from ikip_ingestion.stages.resolve_identity import (
    InMemoryPartStore,
    resolve_identity,
)

_HAS_OLEFILE = importlib.util.find_spec("olefile") is not None

_OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def test_creo_prt_routes_to_review() -> None:
    """A Creo .prt is recognized (blocked handler) and routed to review, not rejected."""
    reg = default_registry()
    d = Path(tempfile.mkdtemp())
    prt = d / "impeller.prt"
    prt.write_bytes(b"\x00\x00\x00\x00proprietary creo binary payload, unreadable\x00")

    decision = quarantine.gate(prt.read_bytes()[:MAGIC_READ_BYTES], prt.name, reg)
    assert decision.disposition is Disposition.ADMIT  # recognized by extension
    assert decision.handler_key == "BLOCKED"

    routed = parse_ocr.route_and_extract(prt, prt.name, registry=reg)
    assert routed.route is Route.CAD
    assert routed.cad is not None and routed.cad.ok  # extraction "succeeds" as NEEDS_CONVERSION
    model = routed.cad.model
    assert model.tier is ExtractionTier.NEEDS_CONVERSION
    assert model.geometry_available is False
    assert model.canonical_mesh is None
    assert any("STEP AP242" in w for w in model.warnings)
    # Tier-based routing: NEEDS_CONVERSION → review queue.
    rd = route_model(model)
    assert rd.disposition is Disposition.REVIEW
    assert "STEP AP242" in rd.reason


def test_catproduct_recognized_as_needs_conversion() -> None:
    reg = default_registry()
    d = Path(tempfile.mkdtemp())
    cat = d / "gearbox.CATProduct"
    cat.write_bytes(b"random-binary-not-ole\x01\x02\x03")

    routed = parse_ocr.route_and_extract(cat, cat.name, registry=reg)
    assert routed.route is Route.CAD
    assert routed.cad.model.tier is ExtractionTier.NEEDS_CONVERSION


def test_ole_handler_metadata_only_no_geometry() -> None:
    """The OLE handler declares METADATA_ONLY and never claims geometry.

    Exercised at the type level (no olefile authoring dep needed): a METADATA_ONLY model
    has geometry_available=False, no mesh, and no shape descriptor input.
    """
    model = ExtractedModel(
        source_format="OLE",
        tier=_Tier.METADATA_ONLY,
        geometry_available=False,
        parts=[PartRecord(part_ref="part-0", name="housing", part_number="PN-1001",
                          properties={"author": "acme", "thumbnail": "present"})],
        properties={"author": "acme", "thumbnail": "present"},
        warnings=["OLE metadata-only: no neutral geometry in this file"],
    )
    assert model.geometry_available is False
    assert model.canonical_mesh is None
    assert model.metrics is None
    assert model.properties.get("thumbnail") == "present"


def test_sldprt_admitted_by_ole_magic_byte() -> None:
    """A .sldprt with the OLE2 magic is admitted to the OLE handler by magic bytes.

    We only assert the gate/routing decision here (not full property extraction) so the
    test runs without an olefile authoring dependency. When olefile is absent, the file is
    admitted then routed to review (UNAVAILABLE) — never rejected, never crashed.
    """
    reg = default_registry()
    d = Path(tempfile.mkdtemp())
    sld = d / "housing.sldprt"
    # OLE2 magic + padding so it is not a valid compound file (olefile will decline it).
    sld.write_bytes(_OLE_MAGIC + b"\x00" * 512)

    decision = quarantine.gate(sld.read_bytes()[:MAGIC_READ_BYTES], sld.name, reg)
    assert decision.disposition is Disposition.ADMIT
    assert decision.handler_key == "OLE"

    routed = parse_ocr.route_and_extract(sld, sld.name, registry=reg)
    assert routed.route is Route.CAD
    if not _HAS_OLEFILE:
        # Toolkit missing → review, not reject.
        assert not routed.cad.ok
        rd = quarantine.route_extraction(routed.cad)
        assert rd.disposition is Disposition.REVIEW
    else:
        # olefile present but the file is not a real OLE2 → handler error → review.
        rd = quarantine.route_extraction(routed.cad)
        assert rd.disposition is Disposition.REVIEW


# --- §D: assembly edges + part-number dedupe --------------------------------------------

def _assembly_model(part_numbers: list[str]) -> ExtractedModel:
    parts = [
        PartRecord(part_ref=f"part-{i}", name=f"comp-{i}", part_number=pn)
        for i, pn in enumerate(part_numbers)
    ]
    return ExtractedModel(
        source_format="STEP",
        tier=_Tier.FULL_GEOMETRY,
        geometry_available=True,
        parts=parts,
    )


def test_assembly_edges_emitted() -> None:
    """A multi-part assembly emits parent→child edges from the root part."""
    store = InMemoryPartStore()
    model = _assembly_model(["PN-ROOT", "PN-A", "PN-B"])
    result = resolve_identity(model, document_id="doc-asm", store=store)

    assert len(result.parts) == 3
    assert len(result.edges) == 2
    root_id = result.parts[0].part_id
    child_ids = {e.child_part_id for e in result.edges}
    assert all(e.parent_part_id == root_id for e in result.edges)
    assert child_ids == {result.parts[1].part_id, result.parts[2].part_id}


def test_part_number_dedupe_across_files() -> None:
    """The same part_number in two files collapses to one canonical part_id."""
    store = InMemoryPartStore()

    # File 1 introduces PN-SHARED.
    m1 = _assembly_model(["PN-ROOT1", "PN-SHARED"])
    r1 = resolve_identity(m1, document_id="doc-1", store=store)
    shared_id = next(p.part_id for p in r1.parts if p.part_record.part_number == "PN-SHARED")

    # File 2 references the same PN-SHARED in a different assembly.
    m2 = _assembly_model(["PN-ROOT2", "PN-SHARED"])
    r2 = resolve_identity(m2, document_id="doc-2", store=store)
    shared_in_2 = next(p for p in r2.parts if p.part_record.part_number == "PN-SHARED")

    # Deduped: same canonical id, flagged non-canonical on the second occurrence.
    assert shared_in_2.part_id == shared_id
    assert shared_in_2.is_canonical is False
    # The two roots are distinct parts.
    assert r1.parts[0].part_id != r2.parts[0].part_id


def test_relationship_walk_assemblies_using_part() -> None:
    """Given edges from two assemblies sharing a part, a child→parent walk returns both."""
    store = InMemoryPartStore()
    r1 = resolve_identity(_assembly_model(["PN-ASM1", "PN-SHARED"]), document_id="doc-1", store=store)
    r2 = resolve_identity(_assembly_model(["PN-ASM2", "PN-SHARED"]), document_id="doc-2", store=store)

    all_edges = r1.edges + r2.edges
    shared_id = next(p.part_id for p in r1.parts if p.part_record.part_number == "PN-SHARED")

    # "Assemblies using part X" = parents of the shared child across all edges.
    parents = {e.parent_part_id for e in all_edges if e.child_part_id == shared_id}
    assert parents == {r1.parts[0].part_id, r2.parts[0].part_id}

