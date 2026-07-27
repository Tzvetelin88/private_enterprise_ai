"""API Gateway — app factory. Mounts per-domain routers."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_client import make_asgi_app

from src.config import settings
from src.clients import llm, embeddings, rag, mcp
from src.routers import models, chat, completions, embeddings as embeddings_router, rag as rag_router, mcp as mcp_router

logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    await llm.startup()
    await embeddings.startup()
    await rag.startup()
    await mcp.startup()
    yield
    await llm.shutdown()
    await embeddings.shutdown()
    await rag.shutdown()
    await mcp.shutdown()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.include_router(models.router)
app.include_router(chat.router)
app.include_router(completions.router)
app.include_router(embeddings_router.router)
app.include_router(rag_router.router)
app.include_router(mcp_router.router)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "api-gateway"}


if settings.enable_metrics:
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
