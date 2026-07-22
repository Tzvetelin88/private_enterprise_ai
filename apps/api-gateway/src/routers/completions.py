"""POST /v1/completions — OpenAI-compatible text completions."""
import logging

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.clients import llm

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/v1/completions")
async def completions(request: Request):
    if not llm.client:
        return JSONResponse(status_code=503, content={"error": "Service initializing"})
    try:
        body = await request.json()
        response = await llm.client.post("/v1/completions", json=body)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        logger.error(f"Error in completion: {e}")
        return JSONResponse(status_code=503, content={"error": "vLLM backend error"})
