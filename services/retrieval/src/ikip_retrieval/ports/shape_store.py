"""ShapeStore port: shape-descriptor vector store for the SHAPE retrieval channel (§C).

Mirrors the VectorStore port pattern. The adapter (pgvector_shape_store) lives behind this
so the search_shape channel never depends on a concrete store. Authorization filtering is
the caller's responsibility — the store receives an already-computed allowed_document_ids
set and must return nothing outside it (deny-by-default, same contract as VectorStore).
"""
from __future__ import annotations

import math
from typing import Protocol


class ShapeRecord:
    """A stored shape descriptor entry."""

    __slots__ = ("evidence_id", "document_id", "part_id", "descriptor")

    def __init__(
        self,
        evidence_id: str,
        document_id: str,
        part_id: str,
        descriptor: list[float],
    ) -> None:
        self.evidence_id = evidence_id
        self.document_id = document_id
        self.part_id = part_id
        self.descriptor = descriptor


class ShapeStore(Protocol):
    def shape_search(
        self,
        query_descriptor: list[float],
        *,
        allowed_document_ids: frozenset[str] | None,
        limit: int,
    ) -> list[tuple[ShapeRecord, float]]:
        """Return up to `limit` (record, cosine_similarity) pairs.

        `allowed_document_ids=None` means no pre-filter (channel returns all candidates;
        merge_rerank owns authorization). An empty frozenset must return no results
        (deny-by-default, used when the caller has already resolved an empty scope).
        """
        ...


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


class InMemoryShapeStore:
    """Reference ShapeStore for tests. Linear scan; not for production scale."""

    def __init__(self) -> None:
        self._records: list[ShapeRecord] = []

    def add(self, record: ShapeRecord) -> None:
        self._records.append(record)

    def shape_search(
        self,
        query_descriptor: list[float],
        *,
        allowed_document_ids: frozenset[str] | None,
        limit: int,
    ) -> list[tuple[ShapeRecord, float]]:
        if allowed_document_ids is not None and not allowed_document_ids:
            return []
        scored = [
            (rec, _cosine(query_descriptor, rec.descriptor))
            for rec in self._records
            if allowed_document_ids is None or rec.document_id in allowed_document_ids
        ]
        scored.sort(key=lambda t: t[1], reverse=True)
        return scored[:limit]


__all__ = ["InMemoryShapeStore", "ShapeRecord", "ShapeStore"]
