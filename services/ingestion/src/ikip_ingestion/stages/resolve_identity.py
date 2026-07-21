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
from typing import Protocol, runtime_checkable

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


__all__ = [
    "AssemblyEdge",
    "IdentityResult",
    "InMemoryPartStore",
    "PartStore",
    "ResolvedPart",
    "resolve_identity",
]
