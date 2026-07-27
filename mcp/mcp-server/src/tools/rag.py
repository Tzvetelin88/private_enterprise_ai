"""RAG tool implementations — proxy calls to the three RAG services."""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


async def rag_hybrid_query(arguments: dict[str, Any], base_url: str, timeout: int) -> Any:
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        response = await client.post("/query", json=arguments)
        response.raise_for_status()
        return response.json()


async def rag_agentic_query(arguments: dict[str, Any], base_url: str, timeout: int) -> Any:
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        response = await client.post("/query", json=arguments)
        response.raise_for_status()
        return response.json()


async def rag_graph_query(arguments: dict[str, Any], base_url: str, timeout: int) -> Any:
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        response = await client.post("/query", json=arguments)
        response.raise_for_status()
        return response.json()
