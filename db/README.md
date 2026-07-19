# Governed Knowledge Store

Forward-only SQL migrations for PostgreSQL + pgvector (ADR-0002). The store co-locates
ACLs, metadata, chunks, vectors, entities, relationships, provenance, and audit state so
authorization filtering and retrieval remain transactionally consistent.

- `migrations/` — numbered, forward-only. Apply with `just migrate`.
- `fixtures/` — non-sensitive seed data for local/dev only. Never real documents.

Vector access in application code goes through the `VectorStore` port, so the engine can
be replaced without rewriting retrieval if the ADR-0002 scale trigger fires.
