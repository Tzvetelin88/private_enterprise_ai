"""Hybrid RAG pipeline — ingestion and query orchestration."""
from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path
from typing import Any

import asyncpg
import httpx
from elasticsearch import AsyncElasticsearch

from shared.ingestion.parsers import parse
from shared.ingestion.chunker import chunk_text
from shared.embeddings.client import embed

from .retriever import hybrid_retrieve

logger = logging.getLogger(__name__)


async def ingest_document(
    pool: asyncpg.Pool,
    es: AsyncElasticsearch,
    es_index: str,
    filename: str,
    content: bytes,
    infinity_embeddings_url: str,
    embedding_model: str,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> dict:
    """Parse, chunk, embed, and store a document. Returns {document_id, document_name, chunks_created}."""
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
                chunk_id = str(uuid.uuid4())
                await conn.execute(
                    "INSERT INTO chunks (id, document_id, tenant_id, content, chunk_index, embedding) "
                    "VALUES ($1, $2, (SELECT id FROM tenants WHERE name='default'), $3, $4, $5::vector)",
                    uuid.UUID(chunk_id), uuid.UUID(doc_id), chunk.content, i, str(embedding),
                )

        # Index full text in Elasticsearch for BM25
        try:
            await es.index(
                index=es_index,
                id=doc_id,
                document={"content": text, "document_name": filename, "document_id": doc_id},
            )
        except Exception as e:
            logger.warning(f"ES indexing failed ({e}) — BM25 search will miss this document")

        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE documents SET status = 'indexed' WHERE id = $1",
                uuid.UUID(doc_id),
            )

    except Exception as e:
        logger.error(f"Ingestion failed for {filename}: {e}")
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE documents SET status = 'failed' WHERE id = $1",
                uuid.UUID(doc_id),
            )
        raise

    return {"document_id": doc_id, "document_name": filename, "chunks_created": len(chunks)}


async def query_pipeline(
    pool: asyncpg.Pool,
    es: AsyncElasticsearch,
    es_index: str,
    query: str,
    infinity_embeddings_url: str,
    infinity_reranker_url: str,
    llm_url: str,
    llm_model: str,
    embedding_model: str,
    reranker_model: str,
    top_k: int = 5,
) -> dict[str, Any]:
    """End-to-end query: embed → retrieve → rerank → generate."""
    t0 = time.monotonic()

    async with httpx.AsyncClient(base_url=infinity_embeddings_url, timeout=60) as client:
        embeddings = await embed([query], model=embedding_model, http_client=client)
    query_embedding = embeddings[0]

    docs, reranked = await hybrid_retrieve(
        pool=pool,
        es=es,
        es_index=es_index,
        query_embedding=query_embedding,
        query_text=query,
        top_k=top_k,
        reranker_url=infinity_reranker_url,
        reranker_model=reranker_model,
    )

    context = "\n\n".join(d["content"] for d in docs)
    if not context.strip():
        answer = "No relevant information found in the knowledge base."
    else:
        prompt = (
            f"Answer the following question based only on the provided context.\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {query}\n\nAnswer:"
        )
        async with httpx.AsyncClient(base_url=llm_url, timeout=120) as client:
            resp = await client.post(
                "/v1/chat/completions",
                json={
                    "model": llm_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                },
            )
            resp.raise_for_status()
            answer = resp.json()["choices"][0]["message"]["content"]

    latency_ms = int((time.monotonic() - t0) * 1000)
    sources = [
        {
            "content": d["content"],
            "document_id": d.get("document_id", ""),
            "document_name": d.get("document_name", ""),
            "score": d["rerank_score"] if reranked else d.get("rrf_score", d.get("score", 0.0)),
        }
        for d in docs
    ]

    return {
        "answer": answer,
        "sources": sources,
        "metadata": {
            "dense_hits": len(docs),
            "bm25_hits": len(docs),
            "reranked": reranked,
            "latency_ms": latency_ms,
        },
    }
