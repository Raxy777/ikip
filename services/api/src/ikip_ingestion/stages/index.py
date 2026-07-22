"""Ingestion stage: index — write chunk rows to the governed store.

Takes validated CAD chunks and writes one row per chunk. Writing goes through a
`ChunkWriter` protocol so the store (Postgres in production, in-memory for tests) is
swappable without changing the stage — the same seam pattern the retrieval adapters use.

Each row carries the chunk text (for the semantic/lexical channels), its kind, the CAD
source_coordinates, and the flattened provenance versions, so an indexed CAD chunk is fully
reproducible and citable. Embedding generation itself is the enrich/semantic concern; index
persists the row and the text the embedder will consume.
"""
from __future__ import annotations

from typing import Protocol

from ikip_ingestion.stages.chunk import Chunk


class ChunkRow(dict):
    """A flat, storage-ready representation of a chunk. Plain dict for engine neutrality."""


def to_row(chunk: Chunk) -> ChunkRow:
    pv = chunk.provenance.processing_versions
    return ChunkRow(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        kind=chunk.kind,
        text=chunk.text,
        source_coordinates=dict(chunk.source_coordinates or {}),
        parser=pv.parser,
        chunker=pv.chunker,
        embedding_model=pv.embedding_model,
        geometry_kernel=pv.geometry_kernel,
        tessellation=pv.tessellation,
        extraction_tier=pv.extraction_tier,
        source_document_id=chunk.provenance.source_document_id,
        source_revision=chunk.provenance.source_revision,
    )


class ChunkWriter(Protocol):
    """Persists chunk rows. Postgres impl lives in adapters; tests use InMemoryChunkWriter."""

    def write(self, rows: list[ChunkRow]) -> int:
        """Persist rows idempotently (by chunk_id). Returns the number written."""
        ...


def index_chunks(chunks: list[Chunk], writer: ChunkWriter) -> int:
    """Convert validated chunks to rows and persist them. Returns rows written."""
    rows = [to_row(c) for c in chunks]
    return writer.write(rows)


class InMemoryChunkWriter:
    """Reference ChunkWriter: idempotent by chunk_id. For tests and single-process use."""

    def __init__(self) -> None:
        self.rows: dict[str, ChunkRow] = {}

    def write(self, rows: list[ChunkRow]) -> int:
        written = 0
        for row in rows:
            cid = row["chunk_id"]
            if cid not in self.rows:
                written += 1
            self.rows[cid] = row
        return written

    def by_kind(self, kind: str) -> list[ChunkRow]:
        return [r for r in self.rows.values() if r["kind"] == kind]
