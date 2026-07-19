"""ikip-contracts — typed models mirroring /contracts (single source of truth).

The JSON Schemas under contracts/schemas are authoritative. These Python models are kept
in lock-step with them and are strict (`extra="forbid"`) so unexpected fields fail
validation rather than passing silently. When `just codegen` is wired up, generated shapes
supersede these hand-written ones.
"""

from ikip_contracts.enums import (
    AbstentionReason,
    Authority,
    Classification,
    Outcome,
    RetrievalChannel,
    StatementClass,
)
from ikip_contracts.models import (
    AclPolicy,
    Abstention,
    Answer,
    Citation,
    Claim,
    Conflict,
    Evidence,
    ProcessingVersions,
    Provenance,
)

__all__ = [
    # enums
    "AbstentionReason",
    "Authority",
    "Classification",
    "Outcome",
    "RetrievalChannel",
    "StatementClass",
    # models
    "AclPolicy",
    "Abstention",
    "Answer",
    "Citation",
    "Claim",
    "Conflict",
    "Evidence",
    "ProcessingVersions",
    "Provenance",
]
