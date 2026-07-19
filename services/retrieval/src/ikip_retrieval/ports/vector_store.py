"""The VectorStore port. pgvector lives behind this (ADR-0002).

Replacing the vector engine when the scale trigger fires is an adapter change here, not a
rewrite of retrieval. The port takes an already-authorized filter so no adapter can
retrieve outside the caller's authorization scope.
"""
from __future__ import annotations

from typing import Protocol


class VectorStore(Protocol):
    def semantic_search(
        self,
        query_embedding: list[float],
        *,
        allowed_document_ids: frozenset[str],
        limit: int,
    ) -> list[object]:
        """Return candidates restricted to `allowed_document_ids`.

        The authorization filter is a REQUIRED argument, not optional. An empty set must
        return no results (deny-by-default), never "all".
        """
        ...
