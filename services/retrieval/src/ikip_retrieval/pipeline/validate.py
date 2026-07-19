"""Post-generation validation stage.

Wraps ikip-statements around the model draft. This is the enforcement point for
sequence-diagram step 53 ("Verify claim support, citation coverage, conflicts, and
statement labels") and the "Output invalid or claims unsupported" branch: a draft that
fails validation is never returned to the user.

The validator is deterministic and takes the SAME authorized evidence set that was sent
to the model, so a draft citing anything outside that set is rejected — this catches both
model hallucination and any attempt to cite content the user is not authorized to see.
"""
from __future__ import annotations

from ikip_contracts import Answer, Evidence
from ikip_statements import ValidationResult, validate_answer


def validate_draft(draft: Answer, authorized_evidence: list[Evidence]) -> ValidationResult:
    """Return the validation result for a model draft.

    Callers MUST NOT show the draft unless `result.ok`. On failure the pipeline routes to
    a safe abstention or an evidence-only fallback.
    """
    return validate_answer(draft, authorized_evidence)
