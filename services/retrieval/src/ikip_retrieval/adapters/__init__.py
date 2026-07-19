"""Adapters: concrete implementations of ports (pgvector, embedding client, reranker).

`LexicalIndex` is the first live adapter — a BM25 SearchChannel with no external
dependency. pgvector and the embedding client are still stubs pending infrastructure.
"""

from ikip_retrieval.adapters.lexical_index import IndexedChunk, LexicalIndex

__all__ = ["LexicalIndex", "IndexedChunk"]
