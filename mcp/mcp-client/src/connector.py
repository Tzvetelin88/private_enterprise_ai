"""Per-server httpx.AsyncClient pool for external MCP servers."""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_clients: dict[str, httpx.AsyncClient] = {}


def get_client(url: str, timeout: int = 60) -> httpx.AsyncClient:
    if url not in _clients:
        _clients[url] = httpx.AsyncClient(base_url=url, timeout=timeout)
        logger.info(f"Created HTTP client for external MCP server: {url}")
    return _clients[url]


async def close_all() -> None:
    for url, client in list(_clients.items()):
        await client.aclose()
        logger.info(f"Closed client for: {url}")
    _clients.clear()
