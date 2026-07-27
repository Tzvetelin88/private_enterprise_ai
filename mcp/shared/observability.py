"""Tool-call observability via Langfuse (mirrors rag/shared/observability/tracing.py)."""
from __future__ import annotations

import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)

_BACKEND = os.getenv("TRACING_BACKEND", "langfuse").lower()


def trace_tool_call(tool_name: str, arguments: dict[str, Any], result: Any, latency_ms: int, success: bool, error: str | None = None) -> None:
    if _BACKEND == "none":
        return
    if _BACKEND == "langfuse":
        _langfuse_trace(tool_name, arguments, result, latency_ms, success, error)


def _langfuse_trace(tool_name: str, arguments: dict[str, Any], result: Any, latency_ms: int, success: bool, error: str | None) -> None:
    try:
        from langfuse import Langfuse  # type: ignore[import-untyped]

        lf = Langfuse(
            host=os.getenv("LANGFUSE_HOST", "http://langfuse:3000"),
            public_key=os.getenv("LANGFUSE_PUBLIC_KEY", ""),
            secret_key=os.getenv("LANGFUSE_SECRET_KEY", ""),
        )
        trace = lf.trace(name=f"mcp.{tool_name}")
        trace.span(
            name="tool_call",
            input=arguments,
            output=result,
            metadata={"latency_ms": latency_ms, "success": success, "error": error},
        )
        lf.flush()
    except ImportError:
        logger.debug("langfuse not installed — tool-call tracing disabled")
    except Exception as e:
        logger.debug(f"Langfuse trace failed ({e})")
