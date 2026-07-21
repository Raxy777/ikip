"""Blocked/needs-conversion handler: recognizes proprietary formats that require a converter.

Tier 3 (NEEDS_CONVERSION). Handles Creo .prt/.asm, CATIA .CATProduct/.CATPart, and other
formats that are identifiable by extension but have no direct reader. Returns a structured
ExtractedModel with tier=NEEDS_CONVERSION so the registry routes the file to review with a
clear reason rather than treating it as unknown.

No toolkit required: sniffing is extension-only. available() always returns True so the
registry never routes these to UNAVAILABLE — the correct disposition is NEEDS_CONVERSION.
"""
from __future__ import annotations

from pathlib import Path

from ikip_ingestion.extract.types import ExtractedModel, ExtractionTier, PartRecord

# Extensions that are recognized but require a converter (Tier 3).
_NEEDS_CONVERSION_EXTS = frozenset({
    # Creo / Pro/E
    ".prt", ".asm", ".xpr", ".xas",
    # CATIA V5
    ".catpart", ".catproduct", ".catdrawing",
    # NX / Unigraphics
    ".prt",  # NX also uses .prt; sniff order in registry determines which wins
    # Inventor
    ".ipt", ".iam",
    # Solid Edge
    ".par", ".psm", ".asm",
})

# Review reason surfaced to the human queue.
_REVIEW_REASON = (
    "STEP AP242 export required: this proprietary format has no direct reader. "
    "Export to STEP from the originating CAD application and re-ingest."
)


class BlockedHandler:
    """Recognize proprietary CAD formats and return NEEDS_CONVERSION — never crash."""

    format_key = "BLOCKED"

    def sniff(self, head: bytes, filename: str) -> bool:
        return Path(filename).suffix.lower() in _NEEDS_CONVERSION_EXTS

    def available(self) -> bool:
        # Always available: no toolkit needed to recognize and block a format.
        return True

    def extract(self, path: Path) -> ExtractedModel:
        return ExtractedModel(
            source_format=Path(path).suffix.lstrip(".").upper() or "UNKNOWN",
            tier=ExtractionTier.NEEDS_CONVERSION,
            geometry_available=False,
            metrics=None,
            canonical_mesh=None,
            parts=[PartRecord(part_ref="part-0", name=path.stem)],
            pmi=[],
            properties={},
            geometry_kernel=None,
            tessellation=None,
            warnings=[_REVIEW_REASON],
        )
