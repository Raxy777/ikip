"""Ingestion stage: resolve_identity — assembly edges + part-number dedupe (§D).

Two jobs:

  1. ASSEMBLY EDGES. A STEP assembly yields multiple PartRecords with a parent/child
     structure implied by the handler. This stage emits AssemblyEdge rows (parent_part_id →
     child_part_id) so the relationship channel can answer "assemblies using part X".

  2. PART-NUMBER DEDUPE. The same physical part may appear in multiple files (different
     revisions, different assemblies). When two PartRecords share a part_number, they
     collapse to one canonical part_id. The deduplication key is part_number; the winning
     record is the one already in the store (first-write wins; later writes update metadata
     but keep the original part_id).

Both operations are deterministic and idempotent: re-running with the same input produces
the same part_ids and edge set.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable

from ikip_contracts import AclPolicy, Authority, Classification

from ikip_ingestion.extract.types import ExtractedModel, PartRecord


@dataclass(frozen=True)
class ResolvedPart:
    """A PartRecord with a stable, globally-unique part_id assigned."""

    part_id: str
    document_id: str
    part_record: PartRecord
    is_canonical: bool  # False when this part_number already existed → deduped to existing id


@dataclass(frozen=True)
class AssemblyEdge:
    """A directed parent→child relationship between two resolved parts."""

    parent_part_id: str
    child_part_id: str
    document_id: str
    relationship: str = "contains"


@dataclass(frozen=True)
class IdentityResult:
    parts: list[ResolvedPart]
    edges: list[AssemblyEdge]


# ---------------------------------------------------------------------------
# Part-number store protocol (production: Postgres; tests: in-memory)
# ---------------------------------------------------------------------------

@runtime_checkable
class PartStore(Protocol):
    """Read/write part identity. Implementations live in adapters/."""

    def find_by_part_number(self, part_number: str) -> str | None:
        """Return the canonical part_id for a part_number, or None if unseen."""
        ...

    def register(self, part_id: str, part_number: str | None) -> None:
        """Record part_id → part_number mapping (idempotent)."""
        ...


class InMemoryPartStore:
    """Reference PartStore for tests and single-process use."""

    def __init__(self) -> None:
        self._pn_to_id: dict[str, str] = {}

    def find_by_part_number(self, part_number: str) -> str | None:
        return self._pn_to_id.get(part_number)

    def register(self, part_id: str, part_number: str | None) -> None:
        if part_number and part_number not in self._pn_to_id:
            self._pn_to_id[part_number] = part_id


# ---------------------------------------------------------------------------
# Core resolution logic
# ---------------------------------------------------------------------------

def _make_part_id(document_id: str, part_ref: str) -> str:
    """Deterministic part_id from document + handler-local ref."""
    safe_ref = part_ref.replace("/", "_").replace(":", "_")
    return f"{document_id}:{safe_ref}"


def resolve_identity(
    model: ExtractedModel,
    *,
    document_id: str,
    store: PartStore,
) -> IdentityResult:
    """Assign stable part_ids, dedupe by part_number, and emit assembly edges.

    Assembly structure: for a multi-part model the first part is treated as the assembly
    root; all subsequent parts are children of the root. This matches the flat list that
    STEP handlers currently produce (a richer tree can be added when handlers expose it).
    """
    resolved: list[ResolvedPart] = []
    edges: list[AssemblyEdge] = []

    root_part_id: str | None = None

    for i, part in enumerate(model.parts or []):
        candidate_id = _make_part_id(document_id, part.part_ref)

        # Dedupe: if a canonical part_id already exists for this part_number, use it.
        canonical_id: str
        is_canonical: bool
        if part.part_number:
            existing = store.find_by_part_number(part.part_number)
            if existing is not None:
                canonical_id = existing
                is_canonical = False
            else:
                canonical_id = candidate_id
                store.register(canonical_id, part.part_number)
                is_canonical = True
        else:
            canonical_id = candidate_id
            store.register(canonical_id, None)
            is_canonical = True

        resolved.append(
            ResolvedPart(
                part_id=canonical_id,
                document_id=document_id,
                part_record=part,
                is_canonical=is_canonical,
            )
        )

        # Assembly edges: first part is root; subsequent parts are its children.
        if i == 0:
            root_part_id = canonical_id
        elif root_part_id is not None:
            edges.append(
                AssemblyEdge(
                    parent_part_id=root_part_id,
                    child_part_id=canonical_id,
                    document_id=document_id,
                )
            )

    return IdentityResult(parts=resolved, edges=edges)


# ---------------------------------------------------------------------------
# Governance mapping (§G): PLM-synced vs loose-file, authority, export control
# ---------------------------------------------------------------------------

# Property keys that, when present, indicate export-controlled content. Matching is
# case-insensitive on the key; ANY hit forces a fail-closed RESTRICTED classification.
_EXPORT_CONTROL_KEYS = frozenset({
    "itar", "ear", "export_control", "export-control", "exportcontrol",
    "eccn", "usml_category", "classification",
})
# Property values (lowercased) that signal export control regardless of key.
_EXPORT_CONTROL_VALUES = frozenset({"itar", "ear99", "restricted", "export controlled"})


@dataclass(frozen=True)
class PlmRecord:
    """A record from the PLM system of truth for a part. Absence = loose file.

    `source_of_truth` and `synced_at` flow straight into the AclPolicy so the freshness gate
    treats a PLM-synced part exactly like any other governed document.
    """

    part_number: str
    source_of_truth: str
    synced_at: datetime
    owner: str
    sites: tuple[str, ...]
    roles_allowed: tuple[str, ...]
    authority: Authority = Authority.APPROVED
    classification: Classification | None = None
    max_staleness_seconds: int | None = None


@runtime_checkable
class PlmSync(Protocol):
    """Read-only lookup into the PLM system of truth, keyed by part_number."""

    def lookup(self, part_number: str | None) -> PlmRecord | None:
        """Return the PLM record for a part_number, or None for a loose (un-synced) file."""
        ...


@dataclass(frozen=True)
class GovernanceDecision:
    """The governance verdict for a resolved part.

    `acl` is None when the part is a loose file with no PLM record — it cannot be authorized
    and `needs_review` is True. `authority` is UNKNOWN for loose files, which the retrieval
    ranker already excludes from current guidance (Authority.is_current_guidance is False).
    """

    part_id: str
    authority: Authority
    classification: Classification | None
    acl: AclPolicy | None
    needs_review: bool
    reason: str = ""


def _export_controlled(properties: dict[str, str]) -> bool:
    """True if any property key/value signals export control."""
    for k, v in properties.items():
        if k.lower() in _EXPORT_CONTROL_KEYS:
            return True
        if isinstance(v, str) and v.strip().lower() in _EXPORT_CONTROL_VALUES:
            return True
    return False


def govern_part(
    resolved: ResolvedPart,
    *,
    plm: PlmSync,
    document_id: str,
) -> GovernanceDecision:
    """Map a resolved part to its governance verdict.

    Rules (fail closed):
      - Loose file (no PLM record) → authority=UNKNOWN, no ACL, needs_review=True. It is
        excluded from ranking until a reviewer approves it (UNKNOWN is not current guidance).
      - PLM-synced → build an AclPolicy from the PLM record (source_of_truth/synced_at carry
        through to the freshness gate); authority comes from PLM.
      - Export-controlled (ITAR/EAR/etc. in properties) → classification forced to RESTRICTED
        regardless of PLM classification. Fails closed: even a PLM-approved part is RESTRICTED
        if its properties declare export control.
    """
    part = resolved.part_record
    export_controlled = _export_controlled(part.properties)

    plm_record = plm.lookup(part.part_number)

    if plm_record is None:
        # Loose file: unknown authority, no ACL, must be reviewed before it can rank.
        classification = Classification.RESTRICTED if export_controlled else None
        return GovernanceDecision(
            part_id=resolved.part_id,
            authority=Authority.UNKNOWN,
            classification=classification,
            acl=None,
            needs_review=True,
            reason="loose file: no PLM record; authority UNKNOWN, excluded from ranking until approved",
        )

    # PLM-synced: classification is RESTRICTED if export-controlled, else PLM's value.
    classification = (
        Classification.RESTRICTED if export_controlled else plm_record.classification
    )
    acl = AclPolicy(
        document_id=document_id,
        owner=plm_record.owner,
        sites=list(plm_record.sites),
        roles_allowed=list(plm_record.roles_allowed),
        source_of_truth=plm_record.source_of_truth,
        classification=classification,
        synced_at=plm_record.synced_at,
        max_staleness_seconds=plm_record.max_staleness_seconds,
    )
    needs_review = export_controlled  # RESTRICTED content gets a review touch even when synced
    reason = "export-controlled: classification forced RESTRICTED (fail closed)" if export_controlled else ""
    return GovernanceDecision(
        part_id=resolved.part_id,
        authority=plm_record.authority,
        classification=classification,
        acl=acl,
        needs_review=needs_review,
        reason=reason,
    )


__all__ = [
    "AssemblyEdge",
    "GovernanceDecision",
    "IdentityResult",
    "InMemoryPartStore",
    "PartStore",
    "PlmRecord",
    "PlmSync",
    "ResolvedPart",
    "govern_part",
    "resolve_identity",
]
