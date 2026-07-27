"""MCP Client router — /call proxies to external MCP servers."""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .connector import get_client
from .config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


class CallRequest(BaseModel):
    url: str
    tool_name: str
    arguments: dict[str, Any] = {}


@router.post("/call")
async def call_external(request: CallRequest):
    client = get_client(request.url, timeout=settings.request_timeout)
    payload = {"tool_name": request.tool_name, "arguments": request.arguments}

    start = time.monotonic()
    try:
        resp = await client.post(f"/tools/{request.tool_name}/call", json=payload)
        resp.raise_for_status()
        latency_ms = int((time.monotonic() - start) * 1000)
        result_data = resp.json()
        result_data["latency_ms"] = latency_ms
        return result_data
    except (httpx.ConnectError, httpx.ConnectTimeout):
        latency_ms = int((time.monotonic() - start) * 1000)
        logger.error(f"External MCP server unreachable: {request.url}")
        return JSONResponse(
            status_code=503,
            content={
                "tool_name": request.tool_name,
                "result": None,
                "latency_ms": latency_ms,
                "success": False,
                "error": "Remote MCP server unavailable",
            },
        )
    except httpx.HTTPError as e:
        latency_ms = int((time.monotonic() - start) * 1000)
        logger.error(f"External MCP HTTP error: {e}")
        return JSONResponse(
            status_code=502,
            content={
                "tool_name": request.tool_name,
                "result": None,
                "latency_ms": latency_ms,
                "success": False,
                "error": str(e),
            },
        )
