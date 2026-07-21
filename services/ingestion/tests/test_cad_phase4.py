"""Phase 4 CAD ingestion: conversion seam + proprietary/PLM governance (Tier 3 + §G).

Covers:
  - Tier-3 file + converter ENABLED → auto-converts to STEP → re-enters Tier 1 → indexed
    with geometry; converter DISABLED → review queue.
  - Loose file with no PLM record → authority=UNKNOWN, excluded from ranking until approved.
  - ITAR-flagged property → classification=RESTRICTED, fails closed.
  - FreecadHeadlessConverter is disabled (returns None) when no FreeCAD executable is found.
"""
from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import trimesh

from ikip_contracts import Authority, Classification
from ikip_ingestion.extract import ExtractionTier, default_registry
from ikip_ingestion.extract.converter import NoOpConverter
from ikip_ingestion.extract.converters.freecad_headless import FreecadHeadlessConverter
from ikip_ingestion.stages import parse_ocr
from ikip_ingestion.stages.parse_ocr import Route
from ikip_ingestion.stages.resolve_identity import (
    InMemoryPartStore,
    PlmRecord,
    govern_part,
    resolve_identity,
)
from ikip_ingestion.extract.types import ExtractedModel, PartRecord

class _FakeStepConverter:
    """A ModelConverter that 'converts' any Tier-3 file to a real STL-as-STEP stand-in.

    We can't run FreeCAD in the test env, so the fake writes a genuine box mesh the Tier-1
    STL handler can read, proving the convert→re-ingest→geometry path without the toolkit.
    It writes a .stl (the STL handler is always available) to keep the re-ingest real.
    """

    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled

    def can_convert(self, path: Path) -> bool:
        return self._enabled and Path(path).suffix.lower() in {".prt", ".catproduct", ".asm"}

    def convert(self, path: Path, output_dir: Path) -> Path | None:
        if not self._enabled:
            return None
        output_dir.mkdir(parents=True, exist_ok=True)
        out = output_dir / (Path(path).stem + ".stl")
        trimesh.creation.box(extents=(10.0, 20.0, 30.0)).export(str(out), file_type="stl")
        return out


def _make_prt() -> Path:
    d = Path(tempfile.mkdtemp())
    prt = d / "impeller.prt"
    prt.write_bytes(b"\x00\x00proprietary creo payload\x00")
    return prt


def test_tier3_converts_and_reenters_tier1() -> None:
    reg = default_registry()
    prt = _make_prt()

    routed = parse_ocr.route_and_extract(prt, prt.name, registry=reg, converter=_FakeStepConverter(enabled=True))
    assert routed.route is Route.CAD
    assert routed.converted is True
    assert routed.cad is not None and routed.cad.ok
    model = routed.cad.model
    # Recovered as Tier 1 with real geometry (the converted box).
    assert model.tier is ExtractionTier.FULL_GEOMETRY
    assert model.geometry_available is True
    assert model.canonical_mesh is not None
    assert model.metrics.face_count == 12


def test_tier3_converter_disabled_routes_to_review() -> None:
    reg = default_registry()
    prt = _make_prt()

    # Disabled converter → no recovery → NEEDS_CONVERSION result returned unchanged.
    routed = parse_ocr.route_and_extract(prt, prt.name, registry=reg, converter=_FakeStepConverter(enabled=False))
    assert routed.converted is False
    assert routed.cad.model.tier is ExtractionTier.NEEDS_CONVERSION

    # And with the default (no-op) converter, same outcome.
    routed_default = parse_ocr.route_and_extract(prt, prt.name, registry=reg)
    assert routed_default.converted is False
    assert routed_default.cad.model.tier is ExtractionTier.NEEDS_CONVERSION


def test_freecad_converter_disabled_without_executable() -> None:
    # No FreeCAD configured/installed in CI → converter disabled, convert() returns None.
    conv = FreecadHeadlessConverter(freecad_cmd="/nonexistent/freecadcmd")
    assert conv.enabled is False
    assert conv.can_convert(_make_prt()) is False
    assert conv.convert(_make_prt(), Path(tempfile.mkdtemp())) is None


# --- §G governance ----------------------------------------------------------------------

class _FakePlm:
    def __init__(self, records: dict[str, PlmRecord]) -> None:
        self._records = records

    def lookup(self, part_number: str | None):
        if part_number is None:
            return None
        return self._records.get(part_number)


def _resolve_one(part: PartRecord, document_id: str = "doc-1"):
    store = InMemoryPartStore()
    model = ExtractedModel(
        source_format="STEP",
        tier=ExtractionTier.FULL_GEOMETRY,
        geometry_available=True,
        parts=[part],
    )
    result = resolve_identity(model, document_id=document_id, store=store)
    return result.parts[0]


def test_loose_file_authority_unknown_excluded_from_ranking() -> None:
    resolved = _resolve_one(PartRecord(part_ref="part-0", name="mystery", part_number="PN-LOOSE"))
    plm = _FakePlm({})  # no record → loose file
    decision = govern_part(resolved, plm=plm, document_id="doc-1")

    assert decision.authority is Authority.UNKNOWN
    assert decision.acl is None
    assert decision.needs_review is True
    # UNKNOWN authority is not current guidance → ranker excludes it.
    assert decision.authority.is_current_guidance is False


def test_plm_synced_part_gets_acl() -> None:
    resolved = _resolve_one(PartRecord(part_ref="part-0", name="pump", part_number="PN-100"))
    plm = _FakePlm({
        "PN-100": PlmRecord(
            part_number="PN-100",
            source_of_truth="teamcenter",
            synced_at=datetime.now(timezone.utc),
            owner="reliability",
            sites=("site-a",),
            roles_allowed=("engineer",),
            authority=Authority.APPROVED,
            classification=Classification.INTERNAL,
            max_staleness_seconds=86_400,
        )
    })
    decision = govern_part(resolved, plm=plm, document_id="doc-1")

    assert decision.authority is Authority.APPROVED
    assert decision.acl is not None
    assert decision.acl.source_of_truth == "teamcenter"
    assert decision.acl.synced_at is not None
    assert decision.classification is Classification.INTERNAL
    assert decision.needs_review is False


def test_itar_property_forces_restricted_fail_closed() -> None:
    # Even a PLM-approved part is RESTRICTED if its properties declare export control.
    part = PartRecord(
        part_ref="part-0", name="nozzle", part_number="PN-ITAR",
        properties={"ITAR": "true", "material": "inconel"},
    )
    resolved = _resolve_one(part)
    plm = _FakePlm({
        "PN-ITAR": PlmRecord(
            part_number="PN-ITAR",
            source_of_truth="teamcenter",
            synced_at=datetime.now(timezone.utc),
            owner="defense",
            sites=("site-a",),
            roles_allowed=("cleared-engineer",),
            authority=Authority.APPROVED,
            classification=Classification.INTERNAL,  # PLM says INTERNAL...
            max_staleness_seconds=86_400,
        )
    })
    decision = govern_part(resolved, plm=plm, document_id="doc-1")

    # ...but export-control forces RESTRICTED, fail closed.
    assert decision.classification is Classification.RESTRICTED
    assert decision.acl.classification is Classification.RESTRICTED
    assert decision.needs_review is True
    assert "RESTRICTED" in decision.reason


def test_loose_itar_file_restricted_and_unknown() -> None:
    part = PartRecord(
        part_ref="part-0", name="secret", part_number="PN-X",
        properties={"export_control": "ITAR"},
    )
    resolved = _resolve_one(part)
    decision = govern_part(resolved, plm=_FakePlm({}), document_id="doc-1")
    # Loose AND export-controlled: unknown authority, restricted classification, review.
    assert decision.authority is Authority.UNKNOWN
    assert decision.classification is Classification.RESTRICTED
    assert decision.needs_review is True
