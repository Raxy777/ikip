"""Handler registry: detect a file's format and dispatch to the right extractor.

This is the CAD analogue of the retrieval service's port registry. `parse_ocr`'s 5C route
asks the registry to handle a file; the registry sniffs magic bytes + extension, picks a
handler, and runs it through the sandbox. Adding a format is `register(handler)` — stages
never change.

Detection is deliberately conservative: STEP is identified by its ``ISO-10303-21`` header,
ASCII STL by a ``solid`` prefix, and binary STL by extension + 84-byte-minimum + triangle-
count sanity (binary STL has no magic number, so extension is load-bearing there).
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from ikip_ingestion.extract.sandbox import (
    HandlerUnavailable,
    SandboxFailure,
    SandboxResult,
    run_sandboxed,
)
from ikip_ingestion.extract.types import ExtractedModel

# How many leading bytes stages should read and pass to the registry for sniffing.
MAGIC_READ_BYTES = 512


@runtime_checkable
class Handler(Protocol):
    """A format extractor. Implementations live in extract/handlers/."""

    format_key: str

    def sniff(self, head: bytes, filename: str) -> bool:
        """Return True if this handler recognizes the file from its head bytes + name."""
        ...

    def available(self) -> bool:
        """Return False if the handler's toolkit is not installed (routes to review)."""
        ...

    def extract(self, path: Path) -> ExtractedModel:
        """Extract a normalized model. May raise; the registry runs this in the sandbox."""
        ...


class HandlerRegistry:
    """Ordered list of handlers; first to `sniff` a file wins."""

    def __init__(self) -> None:
        self._handlers: list[Handler] = []

    def register(self, handler: Handler) -> None:
        self._handlers.append(handler)

    def detect(self, head: bytes, filename: str) -> Handler | None:
        for h in self._handlers:
            if h.sniff(head, filename):
                return h
        return None

    def handle(self, path: Path, head: bytes, filename: str) -> SandboxResult:
        """Detect + extract under the sandbox. Never raises.

        Returns UNSUPPORTED if nothing sniffs the file, UNAVAILABLE if the matching
        handler's toolkit is absent, and otherwise the handler's success/error result.
        """
        handler = self.detect(head, filename)
        if handler is None:
            return SandboxResult.failed(SandboxFailure.UNSUPPORTED, f"no handler for {filename!r}")
        if not handler.available():
            return SandboxResult.failed(
                SandboxFailure.UNAVAILABLE,
                f"{handler.format_key}: required toolkit not installed",
            )

        def _run() -> ExtractedModel:
            # Re-check availability at call time so a handler can raise HandlerUnavailable
            # if its import succeeds but a runtime capability is missing.
            return handler.extract(path)

        return run_sandboxed(_run, label=handler.format_key)


def default_registry() -> HandlerRegistry:
    """Build the registry with Tier-1 (STEP, STL) and Tier-2/3 (OLE, blocked) handlers.

    Registration order matters: STEP and STL are checked first (magic-byte reliable);
    OLE is next (definitive 8-byte magic covers SolidWorks/CATIA compound files);
    BlockedHandler is last (extension-only fallback for known-but-unreadable formats).
    """
    from ikip_ingestion.extract.handlers.blocked import BlockedHandler
    from ikip_ingestion.extract.handlers.ole_props import OlePropsHandler
    from ikip_ingestion.extract.handlers.step_occt import StepOcctHandler
    from ikip_ingestion.extract.handlers.stl_trimesh import StlTrimeshHandler

    reg = HandlerRegistry()
    reg.register(StepOcctHandler())
    reg.register(StlTrimeshHandler())
    reg.register(OlePropsHandler())
    reg.register(BlockedHandler())
    return reg


__all__ = [
    "Handler",
    "HandlerRegistry",
    "HandlerUnavailable",
    "MAGIC_READ_BYTES",
    "default_registry",
]
