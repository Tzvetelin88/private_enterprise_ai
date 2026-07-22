"""Infinity Embeddings backend client."""
import logging

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

client: httpx.AsyncClient | None = None


async def startup() -> None:
    global client
    client = httpx.AsyncClient(
        base_url=settings.infinity_url,
        timeout=settings.infinity_timeout,
    )
    logger.info(f"Infinity backend: {settings.infinity_url}")


async def shutdown() -> None:
    global client
    if client:
        await client.aclose()
        client = None
