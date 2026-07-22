-- Durable upload vertical slice. Originals remain in object storage; these rows hold state and derivatives.
CREATE TABLE IF NOT EXISTS uploaded_document (
 document_id TEXT PRIMARY KEY, filename TEXT NOT NULL, media_type TEXT NOT NULL,
 format TEXT NOT NULL CHECK(format IN ('PDF','STL','STEP')), size_bytes BIGINT NOT NULL CHECK(size_bytes > 0),
 checksum TEXT NOT NULL, object_key TEXT NOT NULL UNIQUE, owner TEXT NOT NULL,
 sites TEXT[] NOT NULL, roles TEXT[] NOT NULL, state TEXT NOT NULL,
 message TEXT, metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS uploaded_document_state_idx ON uploaded_document(state);
CREATE TABLE IF NOT EXISTS uploaded_chunk (
 chunk_id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES uploaded_document(document_id) ON DELETE CASCADE,
 text TEXT NOT NULL, source_coordinates JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS uploaded_chunk_document_idx ON uploaded_chunk(document_id);
CREATE INDEX IF NOT EXISTS uploaded_chunk_search_idx ON uploaded_chunk USING GIN(to_tsvector('english', text));
CREATE TABLE IF NOT EXISTS uploaded_shape (
 shape_id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES uploaded_document(document_id) ON DELETE CASCADE,
 part_id TEXT NOT NULL, descriptor DOUBLE PRECISION[] NOT NULL, geometry JSONB NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE(document_id,part_id)
);
