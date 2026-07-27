"""/v1/mcp/* — proxy routes to MCP Hub."""
import logging

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.clients import mcp

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/mcp")


def _unavailable() -> JSONResponse:
    return JSONResponse(status_code=503, content={"error": "MCP Hub unavailable"})


@router.api_route("/tools", methods=["GET", "POST"])
async def proxy_tools(request: Request):
    if not mcp.hub_client:
        return _unavailable()
    try:
        body = await request.body()
        response = await mcp.hub_client.request(
            method=request.method,
            url="/tools",
            content=body,
            headers={"Content-Type": request.headers.get("Content-Type", "application/json")},
        )
        return JSONResponse(status_code=response.status_code, content=response.json())
    except httpx.HTTPError as e:
        logger.error(f"MCP Hub error: {e}")
        return _unavailable()


@router.api_route("/tools/{path:path}", methods=["GET", "POST", "DELETE"])
async def proxy_tools_path(request: Request, path: str):
    if not mcp.hub_client:
        return _unavailable()
    try:
        body = await request.body()
        response = await mcp.hub_client.request(
            method=request.method,
            url=f"/tools/{path}",
            content=body,
            headers={"Content-Type": request.headers.get("Content-Type", "application/json")},
        )
        return JSONResponse(status_code=response.status_code, content=response.json())
    except httpx.HTTPError as e:
        logger.error(f"MCP Hub error: {e}")
        return _unavailable()


@router.api_route("/audit", methods=["GET"])
async def proxy_audit(request: Request):
    if not mcp.hub_client:
        return _unavailable()
    try:
        response = await mcp.hub_client.get("/audit")
        return JSONResponse(status_code=response.status_code, content=response.json())
    except httpx.HTTPError as e:
        logger.error(f"MCP Hub audit error: {e}")
        return _unavailable()
