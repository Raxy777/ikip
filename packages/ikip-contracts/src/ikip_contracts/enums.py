"""Enumerations shared across contracts. Mirror the JSON Schema `enum` values exactly."""
from __future__ import annotations

import enum


class StatementClass(str, enum.Enum):
    """Classification of a claim. Conflating these is the primary industrial-harm risk.

    Mirrors contracts/schemas/statement-class.schema.json.
    """

    HISTORICAL_OBSERVATION = "historical_observation"
    RECOMMENDATION = "recommendation"
    APPROVED_PROCEDURE = "approved_procedure"
    COMPLETED_WORK = "completed_work"
    INFERENCE = "inference"


class Authority(str, enum.Enum):
    """Governance authority state of a source at retrieval time."""

    APPROVED = "approved"
    DRAFT = "draft"
    SUPERSEDED = "superseded"
    WITHDRAWN = "withdrawn"
    UNKNOWN = "unknown"

    @property
    def is_current_guidance(self) -> bool:
        """Only approved/draft may inform current guidance; superseded/withdrawn are history."""
        return self in (Authority.APPROVED, Authority.DRAFT)


class RetrievalChannel(str, enum.Enum):
    EXACT = "exact"
    LEXICAL = "lexical"
    SEMANTIC = "semantic"
    RELATIONSHIP = "relationship"


class Outcome(str, enum.Enum):
    ANSWERED = "answered"
    ABSTAINED = "abstained"


class AbstentionReason(str, enum.Enum):
    """Machine-readable abstention reasons. Mirrors abstention.schema.json.

    `UNAUTHORIZED_SCOPE` must be surfaced to users identically to `INSUFFICIENT` so the
    existence of restricted content is never revealed.
    """

    INSUFFICIENT = "insufficient"
    AMBIGUOUS = "ambiguous"
    STALE = "stale"
    CONFLICTING = "conflicting"
    UNAUTHORIZED_SCOPE = "unauthorized_scope"
    UNAVAILABLE = "unavailable"


class Classification(str, enum.Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    RESTRICTED = "restricted"
    CONFIDENTIAL = "confidential"
