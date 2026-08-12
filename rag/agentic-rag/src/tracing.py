"""Langfuse tracing helpers for the agentic-rag service.

Uses the low-level Langfuse SDK so that raw httpx LLM calls are captured
alongside LangGraph node spans.  The module is a thin wrapper that degrades
gracefully to no-ops when Langfuse is disabled or misconfigured.
"""
from __future__ import annotations

import logging
from typing import Any

from .config import settings

logger = logging.getLogger(__name__)

_langfuse_client = None


def get_client():
    """Return a shared Langfuse client (lazy-initialised, cached)."""
    global _langfuse_client
    if _langfuse_client is not None:
        return _langfuse_client

    if settings.tracing_backend != "langfuse":
        return None
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        logger.warning("Langfuse keys not configured — tracing disabled")
        return None

    try:
        from langfuse import Langfuse

        _langfuse_client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
        logger.info("Langfuse tracing enabled → %s", settings.langfuse_host)
    except Exception as exc:
        logger.warning("Failed to initialise Langfuse client: %s", exc)
        _langfuse_client = None

    return _langfuse_client


def start_trace(name: str, input: Any = None, metadata: dict | None = None):
    """Create and return a Langfuse Trace object, or None if tracing is off."""
    client = get_client()
    if client is None:
        return None
    try:
        return client.trace(name=name, input=input, metadata=metadata or {})
    except Exception as exc:
        logger.debug("Could not start trace: %s", exc)
        return None


def end_trace(trace, output: Any = None):
    """Update the trace with its final output and flush."""
    if trace is None:
        return
    try:
        trace.update(output=output)
        get_client().flush()
    except Exception as exc:
        logger.debug("Could not end trace: %s", exc)


def create_span(trace, name: str, input: Any = None, metadata: dict | None = None):
    """Create a child span on *trace*; returns None if tracing is off."""
    if trace is None:
        return None
    try:
        return trace.span(name=name, input=input, metadata=metadata or {})
    except Exception as exc:
        logger.debug("Could not create span '%s': %s", name, exc)
        return None


def end_span(span, output: Any = None, level: str = "DEFAULT"):
    """Finish a span with its output."""
    if span is None:
        return
    try:
        span.end(output=output, level=level)
    except Exception as exc:
        logger.debug("Could not end span: %s", exc)


def create_generation(
    trace,
    name: str,
    model: str,
    input: Any = None,
    metadata: dict | None = None,
):
    """Create a Generation observation (LLM call) on *trace*."""
    if trace is None:
        return None
    try:
        return trace.generation(
            name=name,
            model=model,
            input=input,
            metadata=metadata or {},
        )
    except Exception as exc:
        logger.debug("Could not create generation '%s': %s", name, exc)
        return None


def end_generation(generation, output: Any = None, usage: dict | None = None):
    """Finish a Generation observation."""
    if generation is None:
        return
    try:
        kwargs: dict[str, Any] = {"output": output}
        if usage:
            kwargs["usage"] = usage
        generation.end(**kwargs)
    except Exception as exc:
        logger.debug("Could not end generation: %s", exc)


def get_trace(trace_id: str):
    """Rehydrate a trace handle from a serialised trace_id.

    Langfuse's ``trace(id=...)`` call has upsert semantics: passing an id that
    already exists continues that trace instead of creating a new one. This
    lets nodes create manual spans against the *same* trace shown in the
    response's trace_url even though only the trace_id (not the live SDK
    object) survives GraphState/checkpointing.
    """
    if not trace_id:
        return None
    client = get_client()
    if client is None:
        return None
    try:
        return client.trace(id=trace_id)
    except Exception as exc:
        logger.debug("Could not rehydrate trace '%s': %s", trace_id, exc)
        return None


def get_callback_handler(trace_id: str):
    """Return a LangChain CallbackHandler bound to an existing Langfuse trace_id.

    The installed langfuse 2.x SDK's CallbackHandler has no `trace_id=` kwarg
    (that's a v3+ API) — the v2 mechanism is to rehydrate a StatefulTraceClient
    via get_trace() and ask *it* for a bound handler. Binding this way (rather
    than constructing a bare, unbound CallbackHandler) is what makes LLM spans
    created by LangChain/LangGraph nest under the *same* trace as the manual
    spans in this module and the trace_url returned to the client — an unbound
    handler would start its own disconnected trace per invocation instead.
    """
    if not trace_id or settings.tracing_backend != "langfuse":
        return None
    trace = get_trace(trace_id)
    if trace is None:
        return None
    try:
        return trace.get_langchain_handler(update_parent=True)
    except Exception as exc:
        logger.warning("Could not build Langfuse callback handler: %s", exc)
        return None


def score_trace(trace_id: str, name: str, value: float, comment: str | None = None) -> bool:
    """Attach a user-feedback score to an existing trace. Returns True on success."""
    if not trace_id:
        return False
    client = get_client()
    if client is None:
        return False
    try:
        client.score(trace_id=trace_id, name=name, value=value, comment=comment)
        client.flush()
        return True
    except Exception as exc:
        logger.warning("Could not record score for trace '%s': %s", trace_id, exc)
        return False
