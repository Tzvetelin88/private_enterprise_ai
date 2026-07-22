-- Migration 001: Create documents and chunks tables with pgvector HNSW index
-- Run once after enabling the pgvector extension:
--   CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT        NOT NULL,
    content_type TEXT,
    status      TEXT        NOT NULL DEFAULT 'pending',  -- pending | indexed | failed
    rag_type    TEXT,                                    -- hybrid | agentic | graph
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chunks (
    id          UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID    NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    content     TEXT    NOT NULL,
    chunk_index INT     NOT NULL,
    embedding   vector(384)          -- bge-small-en-v1.5 produces 384-dim vectors
);

-- HNSW index for fast cosine similarity search
CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw_idx
    ON chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
