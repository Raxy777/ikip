"""ikip-statements — the safety-critical claim layer.

Two responsibilities:
  1. Statement classification — is a claim a historical observation, a recommendation, an
     approved procedure, completed work, or an inference? (see docs/safety/statement-classification.md)
  2. Claim-support & citation-coverage validation — does every claim cite authorized
     evidence, carry a defensible class, and disclose conflicts when they exist?

Conflating statement classes is the primary way this platform could contribute to
industrial harm, so this package carries the highest test bar and feeds
evaluation/suites/grounding_and_citation. `validate_answer` is deterministic and must
ALWAYS hold regardless of model quality; semantic entailment grading is a separate,
model-assisted concern in evaluation/graders.
"""

from ikip_statements.validator import (
    ValidationResult,
    Violation,
    ViolationCode,
    validate_answer,
)

__all__ = [
    "ValidationResult",
    "Violation",
    "ViolationCode",
    "validate_answer",
]
