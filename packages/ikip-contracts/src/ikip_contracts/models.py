"""Typed models mirroring contracts/schemas/*.

These are the hand-written counterparts to the JSON Schemas. When codegen is wired up
(`just codegen`), the generated shapes replace the hand-written ones; until then these are
the authoritative Python models and are kept in lock-step with the schemas. Field names,
required-ness, and enum values must match the JSON exactly.

`model_config` uses `extra="forbid"` to mirror `additionalProperties: false`, so a payload
with an unexpected field fails validation rather than being silently accepted — important
for a safety contract.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ikip_contracts.enums import (
    AbstentionReason,
    Authority,
    Classification,
    Outcome,
    RetrievalChannel,
    StatementClass,
)

_STRICT = ConfigDict(extra="forbid", frozen=True)


class ProcessingVersions(BaseModel):
    """Exact versions of every processing step, enabling reproduction and invalidation."""

    model_config = _STRICT

    parser: str
    chunker: str
    embedding_model: str
    ocr_engine: str | None = None
    prompt_template: str | None = None
    schema_version: str | None = None
    # CAD extraction provenance (optional; present for CAD-derived artifacts). See
    # provenance.schema.json and docs/architecture/06-ingestion-pipeline.md (route 5C).
    geometry_kernel: str | None = None
    tessellation: str | None = None
    extraction_tier: str | None = None


class Provenance(BaseModel):
    """Lineage on every derived artifact and answer. Mirrors provenance.schema.json."""

    model_config = _STRICT

    source_document_id: str
    source_revision: str
    processing_versions: ProcessingVersions
    source_checksum: str | None = None
    source_coordinates: dict | None = None
    created_at: datetime | None = None


class AclPolicy(BaseModel):
    """Document-level authorization. Evaluated by ikip-authz BEFORE retrieval.

    Mirrors acl-policy.schema.json. `source_of_truth`/`synced_at`/`max_staleness_seconds`
    drive freshness — a stale ACL must fail closed (see docs/safety/acl-sync-and-freshness).
    """

    model_config = _STRICT

    document_id: str
    owner: str
    sites: list[str]
    roles_allowed: list[str]
    source_of_truth: str
    classification: Classification | None = None
    synced_at: datetime | None = None
    max_staleness_seconds: int | None = None


class Evidence(BaseModel):
    """A single authorized retrieved passage. Text is DATA, never instruction.

    Mirrors evidence.schema.json. Only evidence that passed ikip-authz filtering should be
    constructed; this model does not itself authorize.
    """

    model_config = _STRICT

    evidence_id: str
    document_id: str
    text: str
    provenance: Provenance
    authority: Authority
    applicability: dict = Field(default_factory=dict)
    retrieval_score: float | None = None
    retrieved_by: RetrievalChannel | None = None


class Citation(BaseModel):
    """Claim-level citation. Mirrors citation.schema.json.

    `evidence_ids` requires at least one entry: a claim with no supporting evidence may not
    appear in an answer.
    """

    model_config = _STRICT

    claim_id: str
    evidence_ids: list[str] = Field(min_length=1)
    statement_class: StatementClass
    source_coordinates: dict | None = None
    authority: Authority | None = None


class Claim(BaseModel):
    """One claim within an answer. Every claim MUST carry a citation."""

    model_config = _STRICT

    claim_id: str
    text: str
    citation: Citation

    @model_validator(mode="after")
    def _citation_matches_claim(self) -> "Claim":
        if self.citation.claim_id != self.claim_id:
            raise ValueError(
                f"citation.claim_id {self.citation.claim_id!r} != claim_id {self.claim_id!r}"
            )
        return self


class Conflict(BaseModel):
    """A material disagreement between sources, disclosed rather than silently resolved."""

    model_config = ConfigDict(extra="allow", frozen=True)

    description: str | None = None


class Abstention(BaseModel):
    """A safe refusal. Mirrors abstention.schema.json.

    The user-facing `message` for UNAUTHORIZED_SCOPE must not reveal restricted content
    exists; that phrasing is enforced by the abstention factories, not here.
    """

    model_config = _STRICT

    reason: AbstentionReason
    message: str
    suggested_action: str | None = None


class Answer(BaseModel):
    """A grounded answer OR an abstention. Mirrors answer.schema.json.

    Enforces the schema's conditional requirements as validation:
      - outcome=answered  -> claims present and non-empty, abstention absent
      - outcome=abstained -> abstention present, claims absent
    Claim IDs must be unique.
    """

    model_config = _STRICT

    request_id: str
    outcome: Outcome
    config_version: str
    claims: list[Claim] | None = None
    conflicts: list[Conflict] | None = None
    abstention: Abstention | None = None

    @model_validator(mode="after")
    def _outcome_shape(self) -> "Answer":
        if self.outcome is Outcome.ANSWERED:
            if not self.claims:
                raise ValueError("answered outcome requires at least one claim")
            if self.abstention is not None:
                raise ValueError("answered outcome must not carry an abstention")
        else:  # ABSTAINED
            if self.abstention is None:
                raise ValueError("abstained outcome requires an abstention")
            if self.claims:
                raise ValueError("abstained outcome must not carry claims")
        if self.claims:
            ids = [c.claim_id for c in self.claims]
            if len(ids) != len(set(ids)):
                raise ValueError("claim_id values must be unique within an answer")
        return self
