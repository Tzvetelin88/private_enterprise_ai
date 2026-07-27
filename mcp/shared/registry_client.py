from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class RegistryClient:
    def __init__(self, hub_url: str, timeout: int = 30) -> None:
        self._client = httpx.AsyncClient(base_url=hub_url, timeout=timeout)

    async def register_tool(self, tool: dict[str, Any]) -> dict[str, Any]:
        response = await self._client.post("/tools", json=tool)
        response.raise_for_status()
        return response.json()

    async def list_tools(self) -> list[dict[str, Any]]:
        response = await self._client.get("/tools")
        response.raise_for_status()
        return response.json()

    async def aclose(self) -> None:
        await self._client.aclose()
