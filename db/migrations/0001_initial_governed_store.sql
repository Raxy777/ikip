-- 0001 initial governed store (skeleton).
-- Forward-only migrations. The governed store co-locates ACLs, metadata, chunks,
-- vectors, entities, relationships, provenance, and answer/audit metadata so that
-- authorization filtering and retrieval stay transactionally consistent (ADR-0002).

-- Requires the pgvector extension. Kept behind the VectorStore port in code so the
-- engine can be swapped if the ADR-0002 scale trigger fires.
CREATE EXTENSION IF NOT EXISTS vector;

-- Immutable originals are referenced by stable ID; the bytes live in object storage.
CREATE TABLE IF NOT EXISTS document (
    document_id      TEXT PRIMARY KEY,
    owner            TEXT NOT NULL,
    checksum         TEXT NOT NULL,
    revision         TEXT NOT NULL,
    authority        TEXT NOT NULL DEFAULT 'draft',   -- approved|draft|superseded|withdrawn
    retention_policy TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Document-level ACL. source_of_truth + synced_at drive freshness/staleness (deny-by-default).
CREATE TABLE IF NOT EXISTS document_acl (
    document_id           TEXT PRIMARY KEY REFERENCES document(document_id),
    sites                 TEXT[] NOT NULL DEFAULT '{}',
    roles_allowed         TEXT[] NOT NULL DEFAULT '{}',
    classification        TEXT,
    source_of_truth       TEXT NOT NULL,
    synced_at             TIMESTAMPTZ,
    max_staleness_seconds INTEGER
);

-- Chunks + embeddings. Dimension is a placeholder; set to the chosen embedding model.
CREATE TABLE IF NOT EXISTS chunk (
    chunk_id            TEXT PRIMARY KEY,
    document_id         TEXT NOT NULL REFERENCES document(document_id),
    text                TEXT NOT NULL,
    source_coordinates  JSONB,
    processing_versions JSONB NOT NULL,
    embedding           vector(1024)
);

-- TODO: entities, relationships, review_item, answer_record, audit_event, deletion_tombstone.
