"""Hybrid retriever: parallel dense (pgvector) + BM25 (Elasticsearch) with RRF fusion and reranking."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import asyncpg
import httpx
from elasticsearch import AsyncElasticsearch

from shared.reranking.reranker import rerank

logger = logging.getLogger(__name__)

_RRF_K = 60  # RRF constant — standard value for production use


def _rrf_score(ranks: list[int]) -> float:
    return sum(1.0 / (_RRF_K + r) for r in ranks)


async def dense_search(
    pool: asyncpg.Pool,
    embedding: list[float],
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """pgvector cosine similarity search. Returns list of {id, content, score}."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT c.id::text, c.content, d.filename AS document_name, d.id::text AS document_id,
                   1 - (c.embedding <=> $1::vector) AS score
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE d.status = 'indexed'
            ORDER BY c.embedding <=> $1::vector
            LIMIT $2
            """,
            str(embedding),
            top_k,
        )
    return [dict(r) for r in rows]


async def bm25_search(
    es: AsyncElasticsearch,
    index: str,
    query: str,
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """Elasticsearch multi_match BM25 search. Returns list of {id, content, score}."""
    try:
        result = await es.search(
            index=index,
            body={
                "query": {"multi_match": {"query": query, "fields": ["content", "document_name"]}},
                "size": top_k,
            },
        )
        hits = result["hits"]["hits"]
        return [
            {
                "id": h["_id"],
                "content": h["_source"].get("content", ""),
                "document_name": h["_source"].get("document_name", ""),
                "document_id": h["_source"].get("document_id", ""),
                "score": h["_score"],
            }
            for h in hits
        ]
    except Exception as e:
        logger.warning(f"BM25 search failed ({e}) — returning empty results")
        return []


def rrf_fusion(dense: list[dict], bm25: list[dict], top_k: int) -> list[dict]:
    """Reciprocal Rank Fusion over dense and BM25 result lists."""
    scores: dict[str, dict] = {}

    for rank, doc in enumerate(dense, start=1):
        key = doc["id"]
        if key not in scores:
            scores[key] = {"doc": doc, "ranks": []}
        scores[key]["ranks"].append(rank)

    for rank, doc in enumerate(bm25, start=1):
        key = doc["id"]
        if key not in scores:
            scores[key] = {"doc": doc, "ranks": []}
        scores[key]["ranks"].append(rank)

    fused = [
        {**entry["doc"], "rrf_score": _rrf_score(entry["ranks"])}
        for entry in scores.values()
    ]
    fused.sort(key=lambda d: d["rrf_score"], reverse=True)
    return fused[:top_k]


async def hybrid_retrieve(
    pool: asyncpg.Pool,
    es: AsyncElasticsearch,
    es_index: str,
    query_embedding: list[float],
    query_text: str,
    top_k: int = 5,
    reranker_url: str = "http://infinity-reranker:7998",
    reranker_model: str = "BAAI/bge-reranker-v2-m3",
) -> tuple[list[dict], bool]:
    """Full hybrid retrieval pipeline.

    Returns (ranked_docs, reranked_flag).
    """
    dense_task = dense_search(pool, query_embedding, top_k=top_k * 2)
    bm25_task = bm25_search(es, es_index, query_text, top_k=top_k * 2)

    dense_results, bm25_results = await asyncio.gather(dense_task, bm25_task)
    fused = rrf_fusion(dense_results, bm25_results, top_k=top_k * 2)

    contents = [d["content"] for d in fused]
    async with httpx.AsyncClient(base_url=reranker_url, timeout=30) as client:
        ranked = await rerank(
            query=query_text,
            documents=contents,
            top_k=top_k,
            model=reranker_model,
            http_client=client,
        )

    reranked_flag = any(r.score > 0 for r in ranked)
    result_docs = []
    for r in ranked:
        orig_idx = r.metadata.get("index", 0)
        base = fused[orig_idx] if orig_idx < len(fused) else {}
        result_docs.append({**base, "content": r.content, "rerank_score": r.score})

    return result_docs, reranked_flag
