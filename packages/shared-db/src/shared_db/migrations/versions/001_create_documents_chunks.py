"""Create documents and chunks tables with pgvector HNSW index.

Revision ID: 001_create_documents_chunks
Revises:
"""
from alembic import op

revision = "001_create_documents_chunks"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Needed for chunks.embedding below — the original raw-SQL version of this
    # migration assumed the extension was already enabled elsewhere (initdb),
    # which isn't true when running this chain against a fresh database.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            name        TEXT        NOT NULL,
            content_type TEXT,
            status      TEXT        NOT NULL DEFAULT 'pending',  -- pending | indexed | failed
            rag_type    TEXT,                                    -- hybrid | agentic | graph
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS chunks (
            id          UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id UUID    NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            content     TEXT    NOT NULL,
            chunk_index INT     NOT NULL,
            embedding   vector(384)          -- bge-small-en-v1.5 produces 384-dim vectors
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw_idx
            ON chunks USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS chunks_embedding_hnsw_idx")
    op.execute("DROP TABLE IF EXISTS chunks")
    op.execute("DROP TABLE IF EXISTS documents")
