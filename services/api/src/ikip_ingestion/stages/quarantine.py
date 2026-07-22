"""Ingestion stage: quarantine — magic-byte gate + sandbox-failure routing.

First contact with an untrusted file (Trust Boundary TB-4). Two CAD-relevant jobs:

  1. MAGIC-BYTE GATE. Read the leading bytes and decide what the file *is*, independent of
     its declared name — a mislabeled or hostile extension cannot smuggle content past the
     gate. CAD files that a registered handler recognizes are admitted to the 5C route;
     unknown binaries are rejected.
  2. SANDBOX-FAILURE ROUTING. After extraction runs in the sandbox, map the outcome to a
     disposition: success -> proceed; UNAVAILABLE/NEEDS_CONVERSION -> review queue (the file
     is fine, we just cannot read it here); HANDLER_ERROR/UNSUPPORTED on a CAD-shaped file
     -> review or reject per policy. A crash never propagates; it becomes a routed outcome.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ikip_ingestion.extract.registry import MAGIC_READ_BYTES, HandlerRegistry
from ikip_ingestion.extract.sandbox import SandboxFailure, SandboxResult
from ikip_ingestion.extract.types import ExtractedModel, ExtractionTier


class Disposition(str, Enum):
    ADMIT = "admit"  # recognized; continue to extraction/5C
    REVIEW = "review"  # route to human review queue with a reason
    REJECT = "reject"  # not searchable; reason recorded


@dataclass(frozen=True)
class GateDecision:
    disposition: Disposition
    handler_key: str | None = None
    reason: str = ""


def gate(head: bytes, filename: str, registry: HandlerRegistry) -> GateDecision:
    """Magic-byte gate: does a registered handler recognize this file?

    `head` is the first MAGIC_READ_BYTES bytes. Detection uses magic + extension via the
    handler's own `sniff`, so the decision does not trust the extension alone.
    """
    handler = registry.detect(head[:MAGIC_READ_BYTES], filename)
    if handler is None:
        return GateDecision(Disposition.REJECT, reason=f"unrecognized file type: {filename!r}")
    return GateDecision(Disposition.ADMIT, handler_key=handler.format_key)


def route_extraction(result: SandboxResult) -> GateDecision:
    """Map a sandbox extraction outcome to a disposition.

    A file we simply cannot read here (toolkit missing) is NOT rejected — it is a valid file
    routed to review, so enabling the toolkit later recovers it. Only genuine parse failures
    and unrecognized content are candidates for rejection.
    """
    if result.ok:
        return GateDecision(Disposition.ADMIT)

    failure = result.failure
    if failure in (SandboxFailure.UNAVAILABLE,):
        return GateDecision(
            Disposition.REVIEW,
            reason=f"toolkit unavailable; needs conversion or handler install: {result.detail}",
        )
    if failure in (SandboxFailure.TIMEOUT,):
        return GateDecision(Disposition.REVIEW, reason=f"extraction timed out: {result.detail}")
    if failure in (SandboxFailure.HANDLER_ERROR,):
        # A recognized file that failed to parse: review so a human can decide (could be a
        # corrupt export or a format edge case), rather than silently dropping it.
        return GateDecision(Disposition.REVIEW, reason=f"extraction error: {result.detail}")
    # UNSUPPORTED: nothing claimed it.
    return GateDecision(Disposition.REJECT, reason=f"unsupported: {result.detail}")


def route_model(model: ExtractedModel) -> GateDecision:
    """Map a successfully-extracted model's tier to a disposition.

    FULL_GEOMETRY → proceed (ADMIT).
    METADATA_ONLY → proceed (ADMIT); downstream stages skip geometry steps.
    NEEDS_CONVERSION → review queue so a human or converter can act.
    BLOCKED → reject.
    """
    if model.tier is ExtractionTier.NEEDS_CONVERSION:
        reason = next((w for w in model.warnings if w), "needs conversion to neutral format")
        return GateDecision(Disposition.REVIEW, reason=reason)
    if model.tier is ExtractionTier.BLOCKED:
        return GateDecision(Disposition.REJECT, reason="format blocked by policy")
    return GateDecision(Disposition.ADMIT)
