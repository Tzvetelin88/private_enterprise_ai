"""POST /v1/chat/completions — OpenAI-compatible chat completions."""
import logging

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.clients import llm

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/v1/chat/completions")
async def chat_completions(request: Request):
    if not llm.client:
        return JSONResponse(status_code=503, content={"error": "Service initializing"})
    try:
        body = await request.json()
        response = await llm.client.post("/v1/chat/completions", json=body)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        logger.error(f"Error in chat completion: {e}")
        return JSONResponse(status_code=503, content={"error": "vLLM backend error"})
