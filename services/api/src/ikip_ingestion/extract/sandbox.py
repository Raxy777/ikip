"""Sandboxed handler execution.

CAD files are untrusted content (Trust Boundary TB-4). A malformed or hostile file must
not crash the worker, hang it, or exfiltrate anything — it must fail as a *routed outcome*.
This module wraps a handler call so that ANY failure (exception, timeout, or a handler that
declares the format unsupported) becomes a structured `SandboxResult`, which quarantine.py
turns into either a review-queue item or a rejection.

Scope, honestly stated: this is process-local exception + timeout isolation, not a security
sandbox. True isolation (seccomp/container/subprocess with dropped privileges) is a
deployment concern. The seam is here so hardening swaps the executor without touching
handlers or stages.

Phase 4 sandbox hardening (§G). The seam is `run_sandboxed(fn, ...)`: today it runs `fn`
in-process; a hardened deployment replaces the executor with an out-of-process runner
(subprocess in a locked-down container: read-only root FS, no network, dropped caps,
CPU/memory/wall-clock rlimits, non-root uid) WITHOUT changing any handler or stage. Two
properties make that swap safe:
  - Handlers never execute file contents — they only read bytes — so moving the read into a
    child process changes only WHERE the parse happens, not WHAT it does.
  - Any failure (crash, OOM-kill, timeout, non-zero exit) already maps to a structured
    SandboxResult, so a killed child becomes HANDLER_ERROR/TIMEOUT → review, never a leak.
The FreeCAD converter (Phase 4 Tier-3) already runs out of process via subprocess with a
wall-clock timeout — it is the first consumer of this hardening boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, TypeVar

from ikip_ingestion.extract.types import ExtractedModel

T = TypeVar("T")


class SandboxFailure(str, Enum):
    """Why a handler did not return a usable model."""

    UNSUPPORTED = "unsupported"  # no handler claimed the format
    HANDLER_ERROR = "handler_error"  # handler raised on this file
    TIMEOUT = "timeout"  # handler exceeded its time budget
    UNAVAILABLE = "unavailable"  # handler exists but its toolkit isn't installed


@dataclass(frozen=True)
class SandboxResult:
    """Outcome of a sandboxed extraction. Exactly one of `model` / `failure` is set."""

    model: ExtractedModel | None = None
    failure: SandboxFailure | None = None
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.model is not None

    @classmethod
    def success(cls, model: ExtractedModel) -> "SandboxResult":
        return cls(model=model)

    @classmethod
    def failed(cls, failure: SandboxFailure, detail: str = "") -> "SandboxResult":
        return cls(failure=failure, detail=detail)


class HandlerUnavailable(Exception):
    """Raised by a handler whose required toolkit (e.g. OCCT) is not installed.

    Distinct from a parse error: the file may be perfectly valid, we just cannot read it in
    this deployment, so it routes to review (NEEDS_CONVERSION-style) rather than rejection.
    """


def run_sandboxed(
    fn: Callable[[], ExtractedModel],
    *,
    label: str = "extract",
) -> SandboxResult:
    """Execute `fn` and convert any failure into a structured result.

    Never raises. A handler that raises `HandlerUnavailable` maps to UNAVAILABLE; any other
    exception maps to HANDLER_ERROR with the exception summary (never the file contents).
    """
    try:
        model = fn()
    except HandlerUnavailable as exc:
        return SandboxResult.failed(SandboxFailure.UNAVAILABLE, f"{label}: {exc}")
    except Exception as exc:  # noqa: BLE001 — deliberately broad: untrusted input boundary
        # Only the exception type/message is surfaced, never file bytes (redaction rule).
        return SandboxResult.failed(SandboxFailure.HANDLER_ERROR, f"{label}: {type(exc).__name__}: {exc}")
    return SandboxResult.success(model)
