"""Claim-support and citation-coverage validation.

This is the gate between an LLM draft and what a user is allowed to see. Model output is
UNTRUSTED: an answer is only shown if every claim is supported by authorized evidence,
cites it, carries a defensible statement class, and — when sources disagree — discloses
the conflict. Anything short of that must abstain, never invent.

The checks here are deterministic and do not call a model. Semantic "does this evidence
actually entail this claim" grading is a separate, model-assisted concern that belongs in
evaluation/graders and feeds calibration; this module enforces the structural guarantees
that must ALWAYS hold regardless of model quality.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field

from ikip_contracts import Answer, Evidence, Outcome, StatementClass


class ViolationCode(str, enum.Enum):
    CLAIM_WITHOUT_EVIDENCE = "claim_without_evidence"
    EVIDENCE_NOT_AUTHORIZED = "evidence_not_authorized"
    UNKNOWN_EVIDENCE_ID = "unknown_evidence_id"
    MISSING_STATEMENT_CLASS = "missing_statement_class"
    UNDISCLOSED_CONFLICT = "undisclosed_conflict"
    INFERENCE_WITHOUT_BASIS = "inference_without_basis"


@dataclass(frozen=True)
class Violation:
    code: ViolationCode
    claim_id: str | None
    detail: str


@dataclass(frozen=True)
class ValidationResult:
    """The outcome of validating a draft answer against its authorized evidence.

    `ok` is True only when there are zero violations. A caller that receives `ok is False`
    MUST abstain or fall back to an evidence list — it must not show the draft.
    """

    ok: bool
    violations: list[Violation] = field(default_factory=list)

    @classmethod
    def passed(cls) -> "ValidationResult":
        return cls(ok=True, violations=[])

    @classmethod
    def failed(cls, violations: list[Violation]) -> "ValidationResult":
        return cls(ok=False, violations=violations)


def validate_answer(
    answer: Answer,
    authorized_evidence: list[Evidence],
) -> ValidationResult:
    """Validate a draft answer against the evidence the user is authorized to see.

    `authorized_evidence` is the ONLY evidence considered valid support. It must already
    be authorization-filtered by ikip-authz; any citation referencing an ID outside this
    set is a violation, which also catches a model that fabricated an evidence reference.
    """
    # Abstentions carry no claims to support; nothing structural to validate here.
    if answer.outcome is Outcome.ABSTAINED:
        return ValidationResult.passed()

    authorized_ids = {e.evidence_id for e in authorized_evidence}
    violations: list[Violation] = []

    for claim in answer.claims or []:
        cited = claim.citation.evidence_ids

        # 1. Every claim must cite at least one piece of evidence.
        if not cited:
            violations.append(
                Violation(ViolationCode.CLAIM_WITHOUT_EVIDENCE, claim.claim_id, "no evidence cited")
            )
            continue

        # 2. Every cited ID must be a known, authorized piece of evidence.
        for eid in cited:
            if eid not in authorized_ids:
                violations.append(
                    Violation(
                        ViolationCode.UNKNOWN_EVIDENCE_ID,
                        claim.claim_id,
                        f"cited evidence {eid!r} is not in the authorized set",
                    )
                )

        # 3. A statement class is mandatory (the model layer enforces the type; we assert
        #    it is present and, for inference, that it still cites a basis).
        if claim.citation.statement_class is None:  # defensive; schema requires it
            violations.append(
                Violation(ViolationCode.MISSING_STATEMENT_CLASS, claim.claim_id, "no statement class")
            )
        elif claim.citation.statement_class is StatementClass.INFERENCE and not cited:
            violations.append(
                Violation(
                    ViolationCode.INFERENCE_WITHOUT_BASIS,
                    claim.claim_id,
                    "inference must cite the evidence it was synthesized from",
                )
            )

    # 4. Conflict disclosure: if the authorized evidence contains a material disagreement,
    #    the answer must disclose at least one conflict rather than silently pick a side.
    if _has_material_conflict(authorized_evidence) and not (answer.conflicts or []):
        violations.append(
            Violation(
                ViolationCode.UNDISCLOSED_CONFLICT,
                None,
                "authorized evidence conflicts but the answer discloses no conflict",
            )
        )

    return ValidationResult.passed() if not violations else ValidationResult.failed(violations)


def _has_material_conflict(evidence: list[Evidence]) -> bool:
    """Heuristic conflict signal for the STRUCTURAL check.

    A full definition of "material conflict" is an open design item
    (docs/safety/conflict-and-authority-ranking.md). For now we flag the clearest case:
    two current-guidance sources for the same applicability whose authored positions are
    marked as opposing via the `applicability` payload's optional `position` key. This is
    intentionally conservative — real semantic conflict detection is model-assisted and
    lives in evaluation graders. The structural rule only ensures that when a conflict IS
    known, it cannot be hidden.
    """
    positions: dict[tuple, set[str]] = {}
    for e in evidence:
        if not e.authority.is_current_guidance:
            continue
        pos = e.applicability.get("position")
        if pos is None:
            continue
        key = (e.document_id.split(":")[0], tuple(sorted(e.applicability.get("scope", []))))
        positions.setdefault(key, set()).add(str(pos))
    return any(len(v) > 1 for v in positions.values())
