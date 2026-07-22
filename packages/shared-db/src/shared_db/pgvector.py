"""pgvector helpers — HNSW index creation and similarity search utilities."""
from __future__ import annotations

from typing import Any

import asyncpg


async def ensure_pgvector_extension(conn: asyncpg.Connection) -> None:
    """Enable the pgvector extension if not already enabled."""
    await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")


async def similarity_search(
    conn: asyncpg.Connection,
    table: str,
    embedding: list[float],
    top_k: int = 5,
    column: str = "embedding",
    id_column: str = "id",
    extra_columns: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Cosine similarity search against a pgvector HNSW index.

    Returns a list of row dicts ordered by similarity (closest first).
    """
    select_cols = ", ".join([id_column] + (extra_columns or []))
    query = f"""
        SELECT {select_cols},
               1 - ({column} <=> $1::vector) AS score
        FROM {table}
        ORDER BY {column} <=> $1::vector
        LIMIT $2
    """
    rows = await conn.fetch(query, embedding, top_k)
    return [dict(r) for r in rows]


async def create_hnsw_index(
    conn: asyncpg.Connection,
    table: str,
    column: str = "embedding",
    lists: int = 100,
) -> None:
    """Create an HNSW index for cosine distance on the given column."""
    await conn.execute(
        f"CREATE INDEX IF NOT EXISTS {table}_{column}_hnsw_idx "
        f"ON {table} USING hnsw ({column} vector_cosine_ops) WITH (m = 16, ef_construction = {lists})"
    )
