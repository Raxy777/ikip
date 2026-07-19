"""Ingestion Workers — untrusted document -> governed knowledge.

Asynchronous, versioned, idempotent, and deletion-aware. Every imported document is
treated as untrusted content even from an approved source. Ambiguous or low-quality
results route to the human review queue. Writes carry provenance and processing versions.
"""

__all__: list[str] = []
