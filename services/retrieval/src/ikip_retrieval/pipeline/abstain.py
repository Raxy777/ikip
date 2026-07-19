"""Safe abstention construction. The pipeline routes here on any failure to ground.

Uses the shared `Abstention`/`Answer` contracts from ikip-contracts rather than a local
type, so the abstention shape cannot drift from what the API and web consume.
"""
from __future__ import annotations

from ikip_contracts import Abstention, AbstentionReason, Answer, Outcome

# User-facing messages. UNAUTHORIZED_SCOPE is phrased identically to INSUFFICIENT so it
# never reveals that restricted content exists (Security invariant #1 / abstention policy).
_INSUFFICIENT_MSG = "No accessible evidence adequately answers this."


def insufficient() -> Abstention:
    return Abstention(
        reason=AbstentionReason.INSUFFICIENT,
        message=_INSUFFICIENT_MSG,
        suggested_action="Refine the asset filter or contact the document owner.",
    )


def unauthorized_scope() -> Abstention:
    # Deliberately indistinguishable from `insufficient` to the user.
    return Abstention(
        reason=AbstentionReason.UNAUTHORIZED_SCOPE,
        message=_INSUFFICIENT_MSG,
        suggested_action="Contact the document owner if you believe you should have access.",
    )


def conflicting() -> Abstention:
    return Abstention(
        reason=AbstentionReason.CONFLICTING,
        message="Authorized sources disagree and cannot be reconciled from the evidence.",
        suggested_action="Review the conflicting sources with their owners.",
    )


def unavailable() -> Abstention:
    return Abstention(
        reason=AbstentionReason.UNAVAILABLE,
        message="The answer service is temporarily degraded.",
        suggested_action="Retry shortly, or use search to view authorized evidence directly.",
    )


def as_answer(request_id: str, config_version: str, abstention: Abstention) -> Answer:
    """Wrap an abstention reason in a complete, validatable Answer."""
    return Answer(
        request_id=request_id,
        outcome=Outcome.ABSTAINED,
        config_version=config_version,
        abstention=abstention,
    )
