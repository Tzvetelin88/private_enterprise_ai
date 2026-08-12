"""MCP Hub FastAPI service."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI

from shared import observability

from .config import settings
from .router import router

logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    pool = await asyncpg.create_pool(settings.database_url, min_size=2, max_size=10)
    app.state.pool = pool
    logger.info("Connected to PostgreSQL")
    yield
    await pool.close()
    # Flush any buffered Langfuse tool-call trace events before exit — the SDK
    # batches in a background thread, so without this, spans from calls made
    # just before shutdown could be lost.
    observability.flush()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "mcp-hub"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=settings.debug)
