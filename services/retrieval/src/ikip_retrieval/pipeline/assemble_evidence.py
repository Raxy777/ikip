"""Assemble the minimum authorized evidence set from ranked candidates.

Takes the ranked, authorized candidates from merge_rerank and produces the list of
contract `Evidence` objects handed to compose_answer (and thence to the model). "Minimum"
means: enough top-ranked, distinct-document evidence to answer, capped by `max_evidence`,
so the model sees the smallest sufficient context rather than everything retrieved.

Candidates are already authorized and current-guidance-only by the time they reach here
(merge_rerank guarantees both). This stage only shapes and bounds the set; it makes no
authorization decision.
"""
from __future__ import annotations

from ikip_contracts import Evidence

from ikip_retrieval.pipeline.types import Candidate

DEFAULT_MAX_EVIDENCE = 12
# Cap per source document so one document cannot crowd out corroborating/ conflicting ones
# — important for conflict disclosure downstream.
DEFAULT_MAX_PER_DOCUMENT = 3


def assemble(
    ranked: list[Candidate],
    *,
    max_evidence: int = DEFAULT_MAX_EVIDENCE,
    max_per_document: int = DEFAULT_MAX_PER_DOCUMENT,
) -> list[Evidence]:
    """Convert the top ranked candidates into a bounded, diverse Evidence list."""
    selected: list[Candidate] = []
    per_doc: dict[str, int] = {}

    for cand in ranked:
        if len(selected) >= max_evidence:
            break
        if per_doc.get(cand.document_id, 0) >= max_per_document:
            continue
        selected.append(cand)
        per_doc[cand.document_id] = per_doc.get(cand.document_id, 0) + 1

    return [_to_evidence(c) for c in selected]


def _to_evidence(c: Candidate) -> Evidence:
    return Evidence(
        evidence_id=c.evidence_id,
        document_id=c.document_id,
        text=c.text,
        provenance=c.provenance,
        authority=c.authority,
        applicability=c.applicability,
        retrieval_score=c.retrieval_score,
        retrieved_by=c.channel,
    )
