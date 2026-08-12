-- Migration 003: Enable pgvector and add the embedding column to chunks
--
-- infra/helm/private-ai/values-postgresql.yaml's initdb script deliberately
-- creates `chunks` without an embedding column, deferring it with the comment
-- "Embeddings table will be added in Stage 4 when pgvector is properly
-- installed" — but no script (install-stage4.sh included) ever actually runs
-- this. Previously this was done by hand and lost on cluster recreation.
-- Apply after Stage 1 (PostgreSQL) is up:
--   kubectl exec -i postgresql-0 -- env PGPASSWORD=changeme-postgres-admin \
--     psql -U postgres -d private_ai -f - < packages/shared-db/src/shared_db/migrations/003_add_pgvector_embedding.sql

CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE chunks ADD COLUMN IF NOT EXISTS embedding vector(384);  -- bge-small-en-v1.5 output dim

CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw_idx
    ON chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
