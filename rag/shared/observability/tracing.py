"""Langfuse / LangSmith tracing setup for LangGraph and LangChain pipelines.

Toggle via environment variables:
  TRACING_BACKEND=langfuse  (default)
  TRACING_BACKEND=langsmith
  TRACING_BACKEND=none      (disable)

Langfuse env vars:
  LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY

LangSmith env vars:
  LANGCHAIN_API_KEY, LANGCHAIN_PROJECT
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_BACKEND = os.getenv("TRACING_BACKEND", "langfuse").lower()


def get_callbacks() -> list[Any]:
    """Return the appropriate LangChain/LangGraph callback list for the configured backend."""
    if _BACKEND == "none":
        return []

    if _BACKEND == "langsmith":
        return _langsmith_callbacks()

    return _langfuse_callbacks()


def _langfuse_callbacks() -> list[Any]:
    try:
        from langfuse.callback import CallbackHandler  # type: ignore[import-untyped]

        handler = CallbackHandler(
            host=os.getenv("LANGFUSE_HOST", "http://langfuse:3000"),
            public_key=os.getenv("LANGFUSE_PUBLIC_KEY", ""),
            secret_key=os.getenv("LANGFUSE_SECRET_KEY", ""),
        )
        logger.info("Langfuse tracing enabled")
        return [handler]
    except ImportError:
        logger.warning("langfuse not installed — tracing disabled")
        return []
    except Exception as e:
        logger.warning(f"Langfuse init failed ({e}) — tracing disabled")
        return []


def _langsmith_callbacks() -> list[Any]:
    try:
        from langchain.callbacks.tracers import LangChainTracer  # type: ignore[import-untyped]

        tracer = LangChainTracer(project_name=os.getenv("LANGCHAIN_PROJECT", "private-ai"))
        logger.info("LangSmith tracing enabled")
        return [tracer]
    except ImportError:
        logger.warning("LangSmith tracer not installed — tracing disabled")
        return []
    except Exception as e:
        logger.warning(f"LangSmith init failed ({e}) — tracing disabled")
        return []
