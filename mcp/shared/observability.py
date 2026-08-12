"""Tool-call observability via Langfuse (mirrors rag/agentic-rag/src/tracing.py).

trace_tool_call() must actually be called from mcp-hub's router.call_tool()
for any of this to have an effect — see mcp-hub/src/router.py.
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_BACKEND = os.getenv("TRACING_BACKEND", "langfuse").lower()

_langfuse_client = None
_client_init_attempted = False


def get_client():
    """Return a shared, lazily-initialised Langfuse client (cached across calls).

    Constructing a new Langfuse client per tool call (the previous behaviour)
    defeats the SDK's background batching/queueing and adds connection setup
    latency to every single tool invocation.
    """
    global _langfuse_client, _client_init_attempted
    if _langfuse_client is not None or _client_init_attempted:
        return _langfuse_client

    _client_init_attempted = True
    if _BACKEND != "langfuse":
        return None

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY", "")
    if not public_key or not secret_key:
        logger.warning("Langfuse keys not configured — MCP tool-call tracing disabled")
        return None

    try:
        from langfuse import Langfuse  # type: ignore[import-untyped]

        _langfuse_client = Langfuse(
            host=os.getenv("LANGFUSE_HOST", "http://langfuse:3000"),
            public_key=public_key,
            secret_key=secret_key,
        )
        logger.info("Langfuse tool-call tracing enabled")
    except ImportError:
        logger.warning("langfuse not installed — MCP tool-call tracing disabled")
    except Exception as e:
        logger.warning(f"Langfuse init failed ({e}) — MCP tool-call tracing disabled")

    return _langfuse_client


def trace_tool_call(tool_name: str, arguments: dict[str, Any], result: Any, latency_ms: int, success: bool, error: str | None = None) -> None:
    if _BACKEND == "none":
        return
    if _BACKEND == "langfuse":
        _langfuse_trace(tool_name, arguments, result, latency_ms, success, error)


def _langfuse_trace(tool_name: str, arguments: dict[str, Any], result: Any, latency_ms: int, success: bool, error: str | None) -> None:
    client = get_client()
    if client is None:
        return
    try:
        trace = client.trace(name=f"mcp.{tool_name}")
        trace.span(
            name="tool_call",
            input=arguments,
            output=result,
            metadata={"latency_ms": latency_ms, "success": success, "error": error},
        )
        # No client.flush() here — the SDK batches/sends in a background
        # thread; forcing a synchronous flush on every call would add
        # network latency to every tool invocation. flush() is called once
        # on service shutdown instead (see mcp-hub/src/main.py lifespan).
    except Exception as e:
        logger.debug(f"Langfuse trace failed ({e})")


def flush() -> None:
    """Flush any buffered Langfuse events. Call on service shutdown."""
    if _langfuse_client is not None:
        try:
            _langfuse_client.flush()
        except Exception as e:
            logger.debug(f"Langfuse flush failed ({e})")
