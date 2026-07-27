"""MCP Server router — /tools and /tools/{name}/call."""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "rag_hybrid_query",
        "description": "Hybrid (dense + BM25) RAG pipeline query",
        "server_type": "local",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
        "output_schema": {"type": "object"},
    },
    {
        "name": "rag_agentic_query",
        "description": "Agentic multi-hop RAG pipeline query",
        "server_type": "local",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
        "output_schema": {"type": "object"},
    },
    {
        "name": "rag_graph_query",
        "description": "Graph RAG pipeline with Neo4j entity traversal",
        "server_type": "local",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
        "output_schema": {"type": "object"},
    },
    {
        "name": "llm_chat",
        "description": "Direct LLM chat completion",
        "server_type": "local",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string"},
                "messages": {"type": "array"},
            },
        },
        "output_schema": {"type": "object"},
    },
    {
        "name": "embed_text",
        "description": "Generate text embeddings",
        "server_type": "local",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        "output_schema": {"type": "object"},
    },
]


class ToolCallRequest(BaseModel):
    tool_name: str
    arguments: dict[str, Any] = {}


@router.get("/tools")
async def list_tools():
    return TOOL_DEFINITIONS


@router.post("/tools/{name}/call")
async def call_tool(name: str, request: Request):
    from .config import settings
    from .tools import rag as rag_tools, llm as llm_tools, embeddings as emb_tools

    body = await request.json()
    arguments = body.get("arguments", {})

    start = time.monotonic()
    try:
        if name == "rag_hybrid_query":
            result = await rag_tools.rag_hybrid_query(arguments, settings.hybrid_rag_url, settings.request_timeout)
        elif name == "rag_agentic_query":
            result = await rag_tools.rag_agentic_query(arguments, settings.agentic_rag_url, settings.request_timeout)
        elif name == "rag_graph_query":
            result = await rag_tools.rag_graph_query(arguments, settings.graph_rag_url, settings.request_timeout)
        elif name == "llm_chat":
            result = await llm_tools.llm_chat(arguments, settings.llm_url, settings.llm_model, settings.llm_timeout)
        elif name == "embed_text":
            result = await emb_tools.embed_text(arguments, settings.infinity_embeddings_url, settings.embedding_model)
        else:
            raise HTTPException(status_code=404, detail=f"Tool '{name}' not found")

        latency_ms = int((time.monotonic() - start) * 1000)
        return {"tool_name": name, "result": result, "latency_ms": latency_ms, "success": True, "error": None}

    except HTTPException:
        raise
    except httpx.HTTPError as e:
        latency_ms = int((time.monotonic() - start) * 1000)
        logger.error(f"Tool '{name}' HTTP error: {e}")
        return JSONResponse(
            status_code=503,
            content={"tool_name": name, "result": None, "latency_ms": latency_ms, "success": False, "error": str(e)},
        )
    except Exception as e:
        latency_ms = int((time.monotonic() - start) * 1000)
        logger.error(f"Tool '{name}' error: {e}")
        return JSONResponse(
            status_code=500,
            content={"tool_name": name, "result": None, "latency_ms": latency_ms, "success": False, "error": str(e)},
        )
