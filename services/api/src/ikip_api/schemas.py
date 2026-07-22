"""HTTP request/response schemas for the API. Thin wrappers over the domain contracts.

The /answer response mirrors the domain `Answer` contract as-is — the API does not reshape
it, so what the web app consumes is exactly what the pipeline produced and validated.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from ikip_contracts import Answer, Evidence


class QueryRequest(BaseModel):
    """A search or answer request. `asset_ids`/`sites` narrow the retrieval scope."""

    question: str = Field(min_length=1)
    asset_ids: list[str] = Field(default_factory=list)
    sites: list[str] = Field(default_factory=list)


class EvidenceView(BaseModel):
    """A single authorized evidence item for the /search response."""

    evidence_id: str
    document_id: str
    text: str
    authority: str
    retrieval_score: float | None = None
    retrieved_by: str | None = None

    @classmethod
    def from_evidence(cls, e: Evidence) -> "EvidenceView":
        return cls(
            evidence_id=e.evidence_id,
            document_id=e.document_id,
            text=e.text,
            authority=e.authority.value,
            retrieval_score=e.retrieval_score,
            retrieved_by=e.retrieved_by.value if e.retrieved_by is not None else None,
        )


class SearchResponse(BaseModel):
    """Authorized, ranked evidence — no model synthesis. Safe to show as-is."""

    evidence: list[EvidenceView]
    count: int


class AnswerResponse(BaseModel):
    """The domain Answer, returned unchanged. Answered or abstained; never a raw draft."""

    answer: Answer

    @classmethod
    def from_answer(cls, answer: Answer) -> "AnswerResponse":
        return cls(answer=answer)


class RevokeRequest(BaseModel):
    document_id: str = Field(min_length=1)


class RevokeResponse(BaseModel):
    document_id: str
    revoked: bool
