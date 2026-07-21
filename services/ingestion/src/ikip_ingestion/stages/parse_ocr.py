"""Ingestion stage: parse_ocr — routing, including the 5C CAD route.

Historically this stage picks an extraction route: 5A direct text parse, 5B OCR for scans.
Route **5C** handles CAD/mesh files: when the quarantine gate admits a file a CAD handler
recognized, parse_ocr asks the extraction registry to produce an ExtractedModel inside the
sandbox and returns it for chunking. Text/OCR routes (5A/5B) are unrelated document paths
and remain out of scope for this CAD phase.

The 5C route touches no model provider and executes nothing from the file — extraction is
pure reading of untrusted bytes behind the sandbox.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from ikip_ingestion.extract.converter import ModelConverter, NoOpConverter
from ikip_ingestion.extract.registry import MAGIC_READ_BYTES, HandlerRegistry, default_registry
from ikip_ingestion.extract.sandbox import SandboxResult
from ikip_ingestion.extract.types import ExtractionTier


class Route(str, Enum):
    DIRECT_PARSE = "5A"  # digital text
    OCR = "5B"  # scanned pages
    CAD = "5C"  # CAD / mesh geometry


@dataclass(frozen=True)
class RouteResult:
    route: Route
    cad: SandboxResult | None = None
    # True when the model was recovered by converting a Tier-3 file to STEP and re-ingesting.
    converted: bool = False


def read_head(path: Path) -> bytes:
    with path.open("rb") as fh:
        return fh.read(MAGIC_READ_BYTES)


def route_and_extract(
    path: Path,
    filename: str,
    *,
    registry: HandlerRegistry | None = None,
    converter: ModelConverter | None = None,
) -> RouteResult:
    """Route a file. If a CAD handler recognizes it, run 5C extraction in the sandbox.

    When extraction yields a Tier-3 (NEEDS_CONVERSION) model AND a converter is enabled for
    the file, the file is converted to STEP and re-ingested through Tier 1 — recovering
    geometry automatically. When no converter can handle it, the NEEDS_CONVERSION result is
    returned unchanged so quarantine routes it to review.

    Returns the CAD SandboxResult for 5C; non-CAD files fall through to the text routes,
    which are handled elsewhere and not implemented in this phase.
    """
    reg = registry or default_registry()
    conv = converter or NoOpConverter()
    head = read_head(path)

    if reg.detect(head, filename) is not None:
        result = reg.handle(path, head, filename)
        # Tier-3 recovery: convert to a neutral format, then re-enter Tier 1.
        if (
            result.ok
            and result.model is not None
            and result.model.tier is ExtractionTier.NEEDS_CONVERSION
            and conv.can_convert(path)
        ):
            recovered = _convert_and_reingest(path, conv, reg)
            if recovered is not None:
                return recovered
        return RouteResult(route=Route.CAD, cad=result)

    # Non-CAD: defer to the text/OCR routes (out of scope here).
    return RouteResult(route=Route.DIRECT_PARSE)


def _convert_and_reingest(
    path: Path,
    converter: ModelConverter,
    registry: HandlerRegistry,
) -> RouteResult | None:
    """Convert a Tier-3 file to STEP and re-ingest it as Tier 1. Returns None if unrecoverable.

    The converted STEP re-enters the SAME registry path (magic-byte detect → sandbox), so a
    conversion output gets exactly the same untrusted-input treatment as any other file.
    """
    import tempfile

    out_dir = Path(tempfile.mkdtemp(prefix="cad-convert-"))
    step_path = converter.convert(path, out_dir)
    if step_path is None or not step_path.is_file():
        return None

    step_head = read_head(step_path)
    if registry.detect(step_head, step_path.name) is None:
        return None
    result = registry.handle(step_path, step_head, step_path.name)
    return RouteResult(route=Route.CAD, cad=result, converted=True)
