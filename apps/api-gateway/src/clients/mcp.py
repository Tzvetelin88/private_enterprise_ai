"""MCP Hub client."""
import logging

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

hub_client: httpx.AsyncClient | None = None


async def startup() -> None:
    global hub_client
    hub_client = httpx.AsyncClient(
        base_url=settings.mcp_hub_url,
        timeout=settings.mcp_timeout,
    )
    logger.info(f"MCP Hub backend: {settings.mcp_hub_url}")


async def shutdown() -> None:
    global hub_client
    if hub_client:
        await hub_client.aclose()
    hub_client = None
