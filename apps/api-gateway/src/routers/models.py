"""GET /v1/models — list available models from LLM backend."""
import logging

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.clients import llm

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/v1/models")
async def list_models():
    if not llm.client:
        return JSONResponse(status_code=503, content={"error": "Service initializing"})
    try:
        response = await llm.client.get("/v1/models")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        logger.error(f"Error fetching models: {e}")
        return JSONResponse(status_code=503, content={"error": "vLLM backend unavailable"})
