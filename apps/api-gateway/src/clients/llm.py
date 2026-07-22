"""LLM backend client (Ollama / vLLM)."""
import logging

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

client: httpx.AsyncClient | None = None


async def startup() -> None:
    global client
    client = httpx.AsyncClient(
        base_url=settings.vllm_url,
        timeout=settings.vllm_timeout,
    )
    logger.info(f"LLM backend: {settings.vllm_url}")


async def shutdown() -> None:
    global client
    if client:
        await client.aclose()
        client = None
