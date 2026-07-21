"""pgvector ShapeStore adapter stub (Phase 3 §C). Production wiring for Phase 4.

Mirrors pgvector_store.py. The real implementation issues a pgvector ANN query against
the model_shape table; this stub satisfies the ShapeStore protocol so the channel and
tests can be wired without a live database.
"""
from __future__ import annotations

from ikip_retrieval.ports.shape_store import ShapeRecord, ShapeStore


class PgvectorShapeStore:
    """pgvector-backed ShapeStore. Swap InMemoryShapeStore for this in production."""

    def shape_search(
        self,
        query_descriptor: list[float],
        *,
        allowed_document_ids: frozenset[str],
        limit: int,
    ) -> list[tuple[ShapeRecord, float]]:
        # TODO(Phase 4): issue pgvector cosine-distance query against model_shape.
        # SELECT evidence_id, document_id, part_id, descriptor,
        #        1 - (descriptor <=> %s::vector) AS similarity
        # FROM model_shape
        # WHERE document_id = ANY(%s)
        # ORDER BY descriptor <=> %s::vector
        # LIMIT %s
        raise NotImplementedError("PgvectorShapeStore not yet wired — use InMemoryShapeStore in tests")
