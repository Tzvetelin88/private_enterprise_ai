"""/v1/rag/* — proxy routes to each RAG service (hybrid, agentic, graph)."""
import logging

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.clients import rag

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/rag")


def _unavailable() -> JSONResponse:
    return JSONResponse(status_code=503, content={"error": "RAG service unavailable"})


# Hybrid RAG
@router.api_route("/hybrid/{path:path}", methods=["GET", "POST", "DELETE"])
async def proxy_hybrid(request: Request, path: str):
    if not rag.hybrid_client:
        return _unavailable()
    try:
        body = await request.body()
        response = await rag.hybrid_client.request(
            method=request.method,
            url=f"/{path}",
            content=body,
            headers={"Content-Type": request.headers.get("Content-Type", "application/json")},
        )
        return JSONResponse(status_code=response.status_code, content=response.json())
    except httpx.HTTPError as e:
        logger.error(f"Hybrid RAG error: {e}")
        return _unavailable()


# Agentic RAG
@router.api_route("/agentic/{path:path}", methods=["GET", "POST", "DELETE"])
async def proxy_agentic(request: Request, path: str):
    if not rag.agentic_client:
        return _unavailable()
    try:
        body = await request.body()
        response = await rag.agentic_client.request(
            method=request.method,
            url=f"/{path}",
            content=body,
            headers={"Content-Type": request.headers.get("Content-Type", "application/json")},
        )
        return JSONResponse(status_code=response.status_code, content=response.json())
    except httpx.HTTPError as e:
        logger.error(f"Agentic RAG error: {e}")
        return _unavailable()


# Graph RAG
@router.api_route("/graph/{path:path}", methods=["GET", "POST", "DELETE"])
async def proxy_graph(request: Request, path: str):
    if not rag.graph_client:
        return _unavailable()
    try:
        body = await request.body()
        response = await rag.graph_client.request(
            method=request.method,
            url=f"/{path}",
            content=body,
            headers={"Content-Type": request.headers.get("Content-Type", "application/json")},
        )
        return JSONResponse(status_code=response.status_code, content=response.json())
    except httpx.HTTPError as e:
        logger.error(f"Graph RAG error: {e}")
        return _unavailable()
