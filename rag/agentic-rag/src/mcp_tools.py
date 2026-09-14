"""Dynamic MCP tool discovery and invocation for the agentic-rag LLM loop.

This is what makes tool use *dynamic*: the tool list is fetched from mcp-hub's
catalog at runtime (not hardcoded), so registering a new tool there — including
a remote/external one — makes it available to the agent with no code change.

Calls go through mcp-hub's real routing endpoint (`POST /tools/{name}/call`),
not a side-channel, so they land in `mcp_audit_log` and get a Langfuse trace via
mcp-hub's own observability hook — the same path a manual `curl` would take.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

from .config import settings

logger = logging.getLogger(__name__)

# This service's own MCP-registered tool — filtered out of the catalog handed
# to the LLM so the agent can never pick a tool call that recurses into itself.
_SELF_TOOL_NAME = "rag_agentic_query"

_catalog_cache: list[dict[str, Any]] = []
_catalog_cache_at: float = 0.0


async def fetch_tool_catalog(force_refresh: bool = False) -> list[dict[str, Any]]:
    """Return the usable MCP tool catalog, cached in-process for mcp_tools_cache_ttl
    seconds so a rarely-changing catalog isn't refetched on every graph run.

    Excludes this service's own tool (self-recursion guard) and any tool the
    hub has marked disabled. Returns [] on any connection error — never raises
    — so callers can treat an empty catalog as "fall back to the legacy path".
    """
    global _catalog_cache, _catalog_cache_at

    if not force_refresh and _catalog_cache and (time.monotonic() - _catalog_cache_at) < settings.mcp_tools_cache_ttl:
        return _catalog_cache

    try:
        async with httpx.AsyncClient(base_url=settings.mcp_hub_url, timeout=settings.mcp_timeout) as client:
            resp = await client.get("/tools")
            resp.raise_for_status()
            tools = resp.json()
    except Exception as e:
        logger.warning("mcp_tools: could not fetch catalog from hub (%s) — returning stale/empty cache", e)
        return _catalog_cache

    filtered = [t for t in tools if t.get("name") != _SELF_TOOL_NAME and t.get("enabled", True)]
    _catalog_cache = filtered
    _catalog_cache_at = time.monotonic()
    return filtered


def to_openai_tool_schema(tool: dict[str, Any]) -> dict[str, Any]:
    """Convert an MCP ToolDefinition into the OpenAI-style function schema
    LangChain's bind_tools() expects."""
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description") or "",
            "parameters": tool.get("input_schema") or {"type": "object", "properties": {}},
        },
    }


async def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Invoke an MCP tool through mcp-hub's real routing/audit/tracing path.

    Never raises — a failed call comes back as {"success": False, "error": ...}
    so it becomes an observation the graph can react to (e.g. grade as
    irrelevant and retry) instead of crashing the node.
    """
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(base_url=settings.mcp_hub_url, timeout=settings.mcp_timeout) as client:
            resp = await client.post(f"/tools/{name}/call", json={"tool_name": name, "arguments": arguments})
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        latency_ms = int((time.monotonic() - start) * 1000)
        logger.warning("mcp_tools: call_tool(%s) failed (%s)", name, e)
        return {"tool_name": name, "result": None, "latency_ms": latency_ms, "success": False, "error": str(e)}


def normalize_to_documents(tool_name: str, tool_result: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize any MCP tool's ToolCallResult into the {content, document_name,
    score} shape grade_documents/generate already expect, so those nodes stay
    tool-agnostic.

    rag_* tools return {"answer", "sources": [{content, document_name, score}]}
    — sources are used directly. Anything else (llm_chat, embed_text, a future
    external tool) is wrapped as a single pseudo-document.
    """
    if not tool_result.get("success", False):
        return []

    result = tool_result.get("result")
    if not result:
        return []

    sources = result.get("sources") if isinstance(result, dict) else None
    if isinstance(sources, list) and sources:
        return sources

    content = result.get("answer") if isinstance(result, dict) else None
    if not content:
        content = json.dumps(result)
    return [{"content": content, "document_name": tool_name, "score": 1.0}]
