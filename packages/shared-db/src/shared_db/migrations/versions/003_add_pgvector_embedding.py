"""Enable pgvector and add the embedding column to chunks.

Revision ID: 003_add_pgvector_embedding
Revises: 002_create_mcp_tables

infra/helm/private-ai/values-postgresql.yaml's initdb script deliberately
creates `chunks` without an embedding column, deferring it with the comment
"Embeddings table will be added in Stage 4 when pgvector is properly
installed" — but no script ever actually ran this before. Idempotent
(IF NOT EXISTS everywhere), so safe to apply whether or not 001 already
created the column.
"""
from alembic import op

revision = "003_add_pgvector_embedding"
down_revision = "002_create_mcp_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("ALTER TABLE chunks ADD COLUMN IF NOT EXISTS embedding vector(384)")  # bge-small-en-v1.5 output dim
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw_idx
            ON chunks USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS chunks_embedding_hnsw_idx")
    op.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS embedding")
