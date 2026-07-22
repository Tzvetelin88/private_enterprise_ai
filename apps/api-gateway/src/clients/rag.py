"""RAG service clients (hybrid, agentic, graph)."""
import logging

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

hybrid_client: httpx.AsyncClient | None = None
agentic_client: httpx.AsyncClient | None = None
graph_client: httpx.AsyncClient | None = None


async def startup() -> None:
    global hybrid_client, agentic_client, graph_client
    hybrid_client = httpx.AsyncClient(
        base_url=settings.hybrid_rag_url,
        timeout=settings.rag_timeout,
    )
    agentic_client = httpx.AsyncClient(
        base_url=settings.agentic_rag_url,
        timeout=settings.rag_timeout,
    )
    graph_client = httpx.AsyncClient(
        base_url=settings.graph_rag_url,
        timeout=settings.rag_timeout,
    )
    logger.info(f"RAG backends: hybrid={settings.hybrid_rag_url}, agentic={settings.agentic_rag_url}, graph={settings.graph_rag_url}")


async def shutdown() -> None:
    global hybrid_client, agentic_client, graph_client
    for c in (hybrid_client, agentic_client, graph_client):
        if c:
            await c.aclose()
    hybrid_client = None
    agentic_client = None
    graph_client = None
