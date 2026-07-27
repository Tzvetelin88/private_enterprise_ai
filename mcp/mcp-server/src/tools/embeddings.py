"""Text embedding tool implementation."""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


async def embed_text(arguments: dict[str, Any], infinity_url: str, embedding_model: str) -> Any:
    text = arguments.get("text", "")
    payload = {"input": text, "model": embedding_model}
    async with httpx.AsyncClient(base_url=infinity_url, timeout=60) as client:
        response = await client.post("/v1/embeddings", json=payload)
        response.raise_for_status()
        data = response.json()
        return {"embedding": data["data"][0]["embedding"], "model": embedding_model}
