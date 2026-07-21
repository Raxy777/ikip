-- 0002 CAD models (Phase 1: Tier-1 STEP + STL geometry).
-- Forward-only. Adds the part/geometry/asset-link tables the CAD ingestion path writes.
-- Chunk rows for CAD (part cards, PMI, properties) reuse the existing `chunk` table from
-- 0001; these tables hold the structured geometry and identity that back those chunks.

-- A part: the identity unit. A STEP assembly yields several; an STL or part file yields one.
-- part_number is the dedupe key across files (populated further in Phase 2 §D).
CREATE TABLE IF NOT EXISTS part (
    part_id          TEXT PRIMARY KEY,
    document_id      TEXT NOT NULL REFERENCES document(document_id),
    part_ref         TEXT NOT NULL,             -- handler-local ref within the source file
    name             TEXT,
    part_number      TEXT,
    -- Tier of the best extraction we have for this part (Phase 2 adds geometry_available).
    extraction_tier  TEXT NOT NULL,             -- full_geometry|metadata_only|needs_conversion|blocked
    properties       JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, part_ref)
);
CREATE INDEX IF NOT EXISTS part_part_number_idx ON part (part_number);

-- Phase 2 (§D): geometry_available makes the tiered model explicit at the part level.
-- A metadata-only part (proprietary file, no neutral geometry) sets this False so ranking
-- and shape-similarity (Phase 3) skip it without inferring from a null mesh.
ALTER TABLE part ADD COLUMN IF NOT EXISTS geometry_available BOOLEAN NOT NULL DEFAULT TRUE;

-- The canonical tessellation + deterministic metrics for a part's geometry.
-- Mesh is stored engine-neutral (flat arrays as JSONB here; a binary/columnar store can be
-- swapped later). Metrics are denormalized for the part card and cheap filtering.
CREATE TABLE IF NOT EXISTS model_geometry (
    geometry_id      TEXT PRIMARY KEY,
    part_id          TEXT NOT NULL REFERENCES part(part_id) ON DELETE CASCADE,
    source_format    TEXT NOT NULL,             -- STEP|STL
    units            TEXT NOT NULL DEFAULT 'mm',
    vertex_count     INTEGER NOT NULL,
    face_count       INTEGER NOT NULL,
    bbox_min         DOUBLE PRECISION[3],
    bbox_max         DOUBLE PRECISION[3],
    volume           DOUBLE PRECISION,
    surface_area     DOUBLE PRECISION,
    is_watertight    BOOLEAN,
    geometry_kernel  TEXT,                       -- provenance: B-rep kernel (null for STL)
    tessellation     TEXT,                       -- provenance: tessellation engine/version
    canonical_mesh   JSONB,                      -- {vertices:[[x,y,z]...], faces:[[a,b,c]...]}
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS model_geometry_part_idx ON model_geometry (part_id);

-- Links a part to an asset in the Asset System of Record (canonical asset identity).
-- Enables "which asset does this model belong to" without overloading the part table.
-- Populated as identity resolution matures; the link table exists from Phase 1 so the
-- foreign relationship is stable.
CREATE TABLE IF NOT EXISTS model_asset (
    part_id          TEXT NOT NULL REFERENCES part(part_id) ON DELETE CASCADE,
    asset_id         TEXT NOT NULL,             -- canonical id from the SoR
    relationship     TEXT NOT NULL DEFAULT 'models',  -- models|documents|references
    confidence       DOUBLE PRECISION,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (part_id, asset_id, relationship)
);
CREATE INDEX IF NOT EXISTS model_asset_asset_idx ON model_asset (asset_id);

-- Phase 2 (§D): assembly structure as a directed graph. A parent part "contains" a child
-- part; the relationship channel walks these edges to answer "assemblies using part X".
-- Edges reference canonical (deduped) part_ids, so a part shared across files has one node.
CREATE TABLE IF NOT EXISTS assembly_edge (
    parent_part_id   TEXT NOT NULL REFERENCES part(part_id) ON DELETE CASCADE,
    child_part_id    TEXT NOT NULL REFERENCES part(part_id) ON DELETE CASCADE,
    document_id      TEXT NOT NULL REFERENCES document(document_id),
    relationship     TEXT NOT NULL DEFAULT 'contains',  -- contains|references
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (parent_part_id, child_part_id, relationship)
);
-- Reverse lookup: "which assemblies contain this part" walks child → parent.
CREATE INDEX IF NOT EXISTS assembly_edge_child_idx ON assembly_edge (child_part_id);
CREATE INDEX IF NOT EXISTS assembly_edge_parent_idx ON assembly_edge (parent_part_id);

-- Phase 3 (§C): shape-similarity descriptors. One row per part with a computed geometric
-- descriptor (D2 shape-distribution histogram, L2-normalized). The SHAPE retrieval channel
-- ranks parts by cosine distance to a reference descriptor. Only FULL_GEOMETRY parts get a
-- descriptor; metadata-only parts have no geometry to describe.
--
-- The descriptor is stored as a pgvector column so ANN indexing is available at scale. The
-- dimension MUST match the ingestion enrich N_BINS (64). If pgvector is not installed, the
-- column can fall back to DOUBLE PRECISION[] and search does an exact scan.
CREATE TABLE IF NOT EXISTS model_shape (
    shape_id         TEXT PRIMARY KEY,
    part_id          TEXT NOT NULL REFERENCES part(part_id) ON DELETE CASCADE,
    document_id      TEXT NOT NULL REFERENCES document(document_id),
    descriptor_kind  TEXT NOT NULL DEFAULT 'd2-histogram',
    descriptor_dim   INTEGER NOT NULL DEFAULT 64,
    -- Prefer pgvector: `descriptor vector(64)`. Portable fallback shown here; the migration
    -- runner upgrades to vector(64) when the pgvector extension is present.
    descriptor       DOUBLE PRECISION[] NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (part_id, descriptor_kind)
);
CREATE INDEX IF NOT EXISTS model_shape_part_idx ON model_shape (part_id);
CREATE INDEX IF NOT EXISTS model_shape_document_idx ON model_shape (document_id);
-- With pgvector: CREATE INDEX model_shape_descriptor_idx ON model_shape
--   USING ivfflat (descriptor vector_cosine_ops) WITH (lists = 100);
