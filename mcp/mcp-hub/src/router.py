"""MCP Hub router — tool catalog, routing, and audit log endpoints."""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from . import catalog, audit
from shared import observability

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_pool(request: Request):
    pool = getattr(request.app.state, "pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="Database not ready")
    return pool


@router.get("/tools")
async def list_tools(request: Request):
    pool = _get_pool(request)
    return await catalog.list_tools(pool)


@router.post("/tools", status_code=201)
async def register_tool(request: Request):
    pool = _get_pool(request)
    body = await request.json()
    try:
        tool = await catalog.create_tool(pool, body)
        return tool
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(status_code=409, detail="Tool already registered")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/tools/{name}")
async def delete_tool(name: str, request: Request):
    pool = _get_pool(request)
    deleted = await catalog.delete_tool(pool, name)
    if not deleted:
        raise HTTPException(status_code=404, detail="Tool not found")
    return {"deleted": name}


@router.post("/tools/{name}/call")
async def call_tool(name: str, request: Request):
    from .config import settings

    pool = _get_pool(request)
    tool = await catalog.get_tool(pool, name)

    if tool is None:
        raise HTTPException(status_code=404, detail="Tool not found")
    if not tool["enabled"]:
        raise HTTPException(status_code=403, detail="Tool is disabled")

    body = await request.json()
    arguments = body.get("arguments", {})

    start = time.monotonic()
    try:
        if tool["server_type"] == "local":
            target_url = settings.mcp_server_url
            payload = {"tool_name": name, "arguments": arguments}
            async with httpx.AsyncClient(base_url=target_url, timeout=120) as client:
                resp = await client.post(f"/tools/{name}/call", json=payload)
                resp.raise_for_status()
                result_data = resp.json()
        else:
            target_url = settings.mcp_client_url
            payload = {
                "url": tool["server_url"],
                "tool_name": name,
                "arguments": arguments,
            }
            async with httpx.AsyncClient(base_url=target_url, timeout=120) as client:
                resp = await client.post("/call", json=payload)
                resp.raise_for_status()
                result_data = resp.json()

        latency_ms = int((time.monotonic() - start) * 1000)
        result_data["latency_ms"] = latency_ms
        success = result_data.get("success", True)
        output = result_data.get("result")
        error = result_data.get("error")

        await audit.log_call(
            pool=pool,
            tool_name=name,
            input_data=arguments,
            output_data=output,
            latency_ms=latency_ms,
            success=success,
            error=error,
        )
        observability.trace_tool_call(name, arguments, output, latency_ms, success, error)
        return result_data

    except httpx.ConnectError:
        latency_ms = int((time.monotonic() - start) * 1000)
        await audit.log_call(pool, name, arguments, None, latency_ms, False, "Remote MCP server unavailable")
        observability.trace_tool_call(name, arguments, None, latency_ms, False, "Remote MCP server unavailable")
        raise HTTPException(status_code=503, detail="Remote MCP server unavailable")
    except httpx.HTTPError as e:
        latency_ms = int((time.monotonic() - start) * 1000)
        await audit.log_call(pool, name, arguments, None, latency_ms, False, str(e))
        observability.trace_tool_call(name, arguments, None, latency_ms, False, str(e))
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/audit")
async def get_audit(request: Request, limit: int = 100):
    pool = _get_pool(request)
    return await audit.list_audit(pool, limit=limit)
