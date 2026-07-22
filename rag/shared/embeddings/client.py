"""Async wrapper around the Infinity-embeddings service."""
from __future__ import annotations

import asyncio
import logging
import os

import httpx

logger = logging.getLogger(__name__)

INFINITY_EMBEDDINGS_URL = os.getenv("INFINITY_EMBEDDINGS_URL", "http://infinity-embeddings:7997")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
_MAX_RETRIES = 3
_RETRY_DELAY = 1.0


async def embed(
    texts: list[str],
    model: str = EMBEDDING_MODEL,
    http_client: httpx.AsyncClient | None = None,
) -> list[list[float]]:
    """Return embeddings for a list of texts.

    Retries up to _MAX_RETRIES times on 503 (service overloaded).
    Raises httpx.HTTPStatusError on persistent failure.
    """
    own_client = http_client is None
    client = http_client or httpx.AsyncClient(base_url=INFINITY_EMBEDDINGS_URL, timeout=60)
    try:
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = await client.post(
                    "/embeddings",
                    json={"model": model, "input": texts},
                )
                if response.status_code == 503:
                    logger.warning(f"Infinity 503 (attempt {attempt}/{_MAX_RETRIES}) — retrying")
                    await asyncio.sleep(_RETRY_DELAY * attempt)
                    continue
                response.raise_for_status()
                data = response.json()
                return [item["embedding"] for item in data["data"]]
            except httpx.HTTPStatusError:
                if attempt == _MAX_RETRIES:
                    raise
                await asyncio.sleep(_RETRY_DELAY * attempt)
    finally:
        if own_client:
            await client.aclose()
    return []


async def embed_single(text: str, **kwargs) -> list[float]:
    """Convenience wrapper for embedding a single text."""
    results = await embed([text], **kwargs)
    return results[0] if results else []
