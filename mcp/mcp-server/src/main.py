"""MCP Server FastAPI service."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from .config import settings
from .router import TOOL_DEFINITIONS, router

logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def _seed_tools_to_hub() -> None:
    try:
        async with httpx.AsyncClient(base_url=settings.mcp_hub_url, timeout=10) as client:
            for tool in TOOL_DEFINITIONS:
                try:
                    await client.post("/tools", json=tool)
                    logger.info(f"Seeded tool '{tool['name']}' to hub")
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 409:
                        logger.debug(f"Tool '{tool['name']}' already registered")
                    else:
                        logger.warning(f"Failed to seed tool '{tool['name']}': {e}")
    except Exception as e:
        logger.warning(f"Hub not reachable at startup — tools not seeded: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    await _seed_tools_to_hub()
    yield
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "mcp-server"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=settings.debug)
