"""Cross-encoder reranker via the Infinity-reranker service.

Falls back gracefully (preserves original order) when the reranker is unavailable.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

INFINITY_RERANKER_URL = os.getenv("INFINITY_RERANKER_URL", "http://infinity-reranker:7998")
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")


@dataclass
class RankedDoc:
    content: str
    score: float
    metadata: dict


async def rerank(
    query: str,
    documents: list[str],
    top_k: int | None = None,
    model: str = RERANKER_MODEL,
    http_client: httpx.AsyncClient | None = None,
) -> list[RankedDoc]:
    """Rerank documents by relevance to query using the cross-encoder model.

    Returns ranked docs ordered by score (highest first).
    Falls back to original order with score=0.0 if the reranker is unavailable.
    """
    own_client = http_client is None
    client = http_client or httpx.AsyncClient(base_url=INFINITY_RERANKER_URL, timeout=30)
    try:
        response = await client.post(
            "/rerank",
            json={"model": model, "query": query, "documents": documents, "return_documents": True},
        )
        response.raise_for_status()
        results = response.json()["results"]
        ranked = [
            RankedDoc(
                content=r.get("document", {}).get("text", documents[r["index"]]),
                score=r["relevance_score"],
                metadata={"index": r["index"]},
            )
            for r in results
        ]
        ranked.sort(key=lambda d: d.score, reverse=True)
        return ranked[:top_k] if top_k else ranked
    except Exception as e:
        logger.warning(f"Reranker unavailable ({e}) — falling back to original order")
        ranked = [RankedDoc(content=doc, score=0.0, metadata={"index": i}) for i, doc in enumerate(documents)]
        return ranked[:top_k] if top_k else ranked
    finally:
        if own_client:
            await client.aclose()
