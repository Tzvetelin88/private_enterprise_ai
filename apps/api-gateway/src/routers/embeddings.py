"""POST /v1/embeddings — OpenAI-compatible embeddings via Infinity."""
import logging

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.clients import embeddings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/v1/embeddings")
async def create_embeddings(request: Request):
    if not embeddings.client:
        return JSONResponse(status_code=503, content={"error": "Service initializing"})
    try:
        body = await request.json()
        response = await embeddings.client.post("/embeddings", json=body)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        logger.error(f"Error in embeddings: {e}")
        return JSONResponse(status_code=503, content={"error": "Infinity backend error"})
