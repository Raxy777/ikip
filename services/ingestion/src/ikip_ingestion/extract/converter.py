"""ModelConverter port: seam for Tier-3 format conversion (Phase 4).

A converter takes a file that cannot be read directly (NEEDS_CONVERSION tier) and produces
a neutral-format file (STEP AP242) that re-enters the Tier-1 path. Phase 4 wires a real
implementation (e.g. FreeCAD headless) behind this port; until then the no-op default
returns None so callers route the file to review rather than crashing.

The seam is here so Phase 4 swaps the implementation without touching any stage.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class ModelConverter(Protocol):
    """Convert a proprietary CAD file to a neutral format (STEP AP242).

    Returns the path to the converted file on success, or None if conversion is not
    possible (unsupported variant, license unavailable, etc.). Never raises — failures
    are expressed as None so callers route to review cleanly.
    """

    def can_convert(self, path: Path) -> bool:
        """Return True if this converter handles the given file."""
        ...

    def convert(self, path: Path, output_dir: Path) -> Path | None:
        """Convert `path` and write the result into `output_dir`. Returns output path or None."""
        ...


class NoOpConverter:
    """Default converter: always declines. Replaced in Phase 4 by a real implementation."""

    def can_convert(self, path: Path) -> bool:  # noqa: ARG002
        return False

    def convert(self, path: Path, output_dir: Path) -> Path | None:  # noqa: ARG002
        return None


__all__ = ["ModelConverter", "NoOpConverter"]
