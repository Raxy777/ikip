"""OLE compound-file handler: metadata + thumbnail extraction. Tier 2 (METADATA_ONLY).

Handles proprietary CAD formats stored as OLE2 compound documents (.sldprt, .sldasm,
.catpart, etc.). These files carry SummaryInformation / DocumentSummaryInformation property
streams and often a thumbnail stream, but no neutral geometry. The handler extracts whatever
it can and returns geometry_available=False so downstream stages know not to expect a mesh.

olefile is a pure-Python dep (no native libs). When absent, available() returns False and
the registry routes these files to review rather than crashing.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from ikip_ingestion.extract.sandbox import HandlerUnavailable
from ikip_ingestion.extract.types import ExtractedModel, ExtractionTier, PartRecord

# OLE2 magic: D0 CF 11 E0 A1 B1 1A E1
_OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

# Property stream names in OLE2 compound files.
_SUMMARY_STREAM = "\x05SummaryInformation"
_DOC_SUMMARY_STREAM = "\x05DocumentSummaryInformation"

# Known thumbnail stream names used by SolidWorks / CATIA / generic OLE hosts.
_THUMBNAIL_STREAMS = ("PreviewPicture", "\x05SummaryInformation", "MsoDataStore")


def _olefile_installed() -> bool:
    return importlib.util.find_spec("olefile") is not None


def _read_ole_properties(ole) -> dict[str, str]:
    """Extract string properties from SummaryInformation and DocumentSummaryInformation."""
    props: dict[str, str] = {}
    for stream in (_SUMMARY_STREAM, _DOC_SUMMARY_STREAM):
        if not ole.exists(stream):
            continue
        try:
            meta = ole.get_metadata()
            # olefile exposes decoded metadata on the OleMetadata object.
            for attr in (
                "title", "subject", "author", "keywords", "comments",
                "last_saved_by", "company", "manager",
            ):
                val = getattr(meta, attr, None)
                if val:
                    props[attr] = val.decode("utf-8", errors="replace") if isinstance(val, bytes) else str(val)
        except Exception:  # noqa: BLE001
            pass
        break  # metadata object covers both streams; only need one pass
    return props


def _has_thumbnail(ole) -> bool:
    for name in _THUMBNAIL_STREAMS:
        try:
            if ole.exists(name):
                return True
        except Exception:  # noqa: BLE001
            pass
    return False


class OlePropsHandler:
    """Extract OLE2 compound-file metadata and thumbnail presence. No geometry."""

    format_key = "OLE"

    def sniff(self, head: bytes, filename: str) -> bool:
        # OLE2 has a definitive 8-byte magic; extension is secondary confirmation.
        if head[:8] == _OLE_MAGIC:
            return True
        # Some tools strip the magic; fall back to known proprietary extensions.
        name = filename.lower()
        return name.endswith((".sldprt", ".sldasm", ".slddrw"))

    def available(self) -> bool:
        return _olefile_installed()

    def extract(self, path: Path) -> ExtractedModel:
        if not _olefile_installed():
            raise HandlerUnavailable("olefile not installed")

        import olefile  # local import: optional dep

        if not olefile.isOleFile(str(path)):
            raise ValueError(f"not a valid OLE2 file: {path.name!r}")

        with olefile.OleFileIO(str(path)) as ole:
            properties = _read_ole_properties(ole)
            has_thumb = _has_thumbnail(ole)

        if has_thumb:
            properties["thumbnail"] = "present"

        part_name = properties.get("title") or path.stem
        part_number = properties.get("subject") or None

        return ExtractedModel(
            source_format="OLE",
            tier=ExtractionTier.METADATA_ONLY,
            geometry_available=False,
            metrics=None,
            canonical_mesh=None,
            parts=[PartRecord(part_ref="part-0", name=part_name, part_number=part_number, properties=properties)],
            pmi=[],
            properties=properties,
            geometry_kernel=None,
            tessellation=None,
            warnings=["OLE metadata-only: no neutral geometry in this file"],
        )
