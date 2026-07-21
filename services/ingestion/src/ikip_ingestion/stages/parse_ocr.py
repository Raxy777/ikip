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

from ikip_ingestion.extract.registry import MAGIC_READ_BYTES, HandlerRegistry, default_registry
from ikip_ingestion.extract.sandbox import SandboxResult


class Route(str, Enum):
    DIRECT_PARSE = "5A"  # digital text
    OCR = "5B"  # scanned pages
    CAD = "5C"  # CAD / mesh geometry


@dataclass(frozen=True)
class RouteResult:
    route: Route
    cad: SandboxResult | None = None


def read_head(path: Path) -> bytes:
    with path.open("rb") as fh:
        return fh.read(MAGIC_READ_BYTES)


def route_and_extract(
    path: Path,
    filename: str,
    *,
    registry: HandlerRegistry | None = None,
) -> RouteResult:
    """Route a file. If a CAD handler recognizes it, run 5C extraction in the sandbox.

    Returns the CAD SandboxResult for 5C; non-CAD files fall through to the text routes,
    which are handled elsewhere and not implemented in this phase.
    """
    reg = registry or default_registry()
    head = read_head(path)

    if reg.detect(head, filename) is not None:
        result = reg.handle(path, head, filename)
        return RouteResult(route=Route.CAD, cad=result)

    # Non-CAD: defer to the text/OCR routes (out of scope here).
    return RouteResult(route=Route.DIRECT_PARSE)
