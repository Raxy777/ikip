"""Safe abstention construction. The pipeline routes here on any failure to ground."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Abstention:
    reason: str  # one of abstention.schema.json reasons
    message: str
    suggested_action: str | None = None


def insufficient() -> Abstention:
    return Abstention("insufficient", "No accessible evidence adequately answers this.",
                      "Refine the asset filter or contact the document owner.")


def unauthorized_scope() -> Abstention:
    # Phrased identically to `insufficient` so it never reveals restricted content exists.
    return Abstention("unauthorized_scope", "No accessible evidence adequately answers this.",
                      "Contact the document owner if you believe you should have access.")


def conflicting() -> Abstention:
    return Abstention("conflicting", "Authorized sources disagree and cannot be reconciled.",
                      "Review the conflicting sources with their owners.")
