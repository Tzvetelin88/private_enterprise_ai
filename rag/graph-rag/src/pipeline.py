"""Graph RAG pipeline — ingestion and query orchestration."""
from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path
from typing import Any

import asyncpg
import httpx

from shared.ingestion.parsers import parse
from shared.ingestion.chunker import chunk_text
from shared.embeddings.client import embed

from .extractor import extract_entities_and_relationships
from .graph import Neo4jClient

logger = logging.getLogger(__name__)


async def ingest_document(
    pool: asyncpg.Pool,
    neo4j: Neo4jClient,
    filename: str,
    content: bytes,
    infinity_embeddings_url: str,
    embedding_model: str,
    llm_url: str,
    llm_model: str,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> str:
    doc_id = str(uuid.uuid4())
    content_type = Path(filename).suffix.lstrip(".") or "txt"

    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO documents (id, tenant_id, filename, content_type, status) "
            "VALUES ($1, (SELECT id FROM tenants WHERE name='default'), $2, $3, 'pending')",
            uuid.UUID(doc_id), filename, content_type,
        )

    try:
        text = parse(filename, content)
        if not text.strip():
            raise ValueError("Document is empty after parsing")

        chunks = chunk_text(text, chunk_size=chunk_size, overlap=chunk_overlap)
        texts = [c.content for c in chunks]

        async with httpx.AsyncClient(base_url=infinity_embeddings_url, timeout=60) as client:
            embeddings = await embed(texts, model=embedding_model, http_client=client)

        async with pool.acquire() as conn:
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                await conn.execute(
                    "INSERT INTO chunks (id, document_id, tenant_id, content, chunk_index, embedding) "
                    "VALUES ($1, $2, (SELECT id FROM tenants WHERE name='default'), $3, $4, $5::vector)",
                    uuid.UUID(str(uuid.uuid4())), uuid.UUID(doc_id), chunk.content, i, str(embedding),
                )

        # Entity/relationship extraction
        extraction = await extract_entities_and_relationships(text, llm_url, llm_model)
        await neo4j.upsert_document(doc_id, filename)
        if extraction["entities"]:
            await neo4j.upsert_entities(extraction["entities"], doc_id)
        if extraction["relationships"]:
            await neo4j.upsert_relationships(extraction["relationships"])

        async with pool.acquire() as conn:
            await conn.execute("UPDATE documents SET status = 'indexed' WHERE id = $1", uuid.UUID(doc_id))

    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        async with pool.acquire() as conn:
            await conn.execute("UPDATE documents SET status = 'failed' WHERE id = $1", uuid.UUID(doc_id))
        raise

    return doc_id


async def query_pipeline(
    pool: asyncpg.Pool,
    neo4j: Neo4jClient,
    query: str,
    infinity_embeddings_url: str,
    llm_url: str,
    llm_model: str,
    embedding_model: str,
    traversal_depth: int = 2,
    top_k: int = 5,
) -> dict[str, Any]:
    t0 = time.monotonic()

    async with httpx.AsyncClient(base_url=infinity_embeddings_url, timeout=60) as client:
        embeddings = await embed([query], model=embedding_model, http_client=client)
    query_embedding = embeddings[0]

    # Extract query entities and traverse graph
    extraction = await extract_entities_and_relationships(query, llm_url, llm_model)
    query_entities = extraction.get("entities", [])
    connected_entities, graph_paths = await neo4j.traverse(query_entities, depth=traversal_depth)

    # Vector similarity search (filter to traversed entity context)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT c.content, d.filename AS document_name, d.id::text AS document_id,
                   1 - (c.embedding <=> $1::vector) AS score
            FROM chunks c JOIN documents d ON d.id = c.document_id
            WHERE d.status = 'indexed'
            ORDER BY c.embedding <=> $1::vector LIMIT $2
            """,
            str(query_embedding), top_k,
        )
    docs = [dict(r) for r in rows]

    context = "\n\n".join(d["content"] for d in docs)
    graph_context = f"Related entities: {', '.join(connected_entities[:10])}" if connected_entities else ""
    full_context = f"{graph_context}\n\n{context}".strip() if graph_context else context

    if not full_context:
        answer = "No relevant information found in the knowledge base."
    else:
        prompt = (
            f"Answer the question based only on the context.\n\nContext:\n{full_context}\n\n"
            f"Question: {query}\n\nAnswer:"
        )
        async with httpx.AsyncClient(base_url=llm_url, timeout=120) as client:
            resp = await client.post(
                "/v1/chat/completions",
                json={"model": llm_model, "messages": [{"role": "user", "content": prompt}]},
            )
            resp.raise_for_status()
            answer = resp.json()["choices"][0]["message"]["content"]

    return {
        "answer": answer,
        "sources": [{"content": d["content"], "document_id": d.get("document_id", ""), "score": d.get("score", 0.0)} for d in docs],
        "metadata": {
            "entities_found": query_entities,
            "graph_paths": graph_paths,
            "traversal_depth": traversal_depth,
            "latency_ms": int((time.monotonic() - t0) * 1000),
        },
    }
