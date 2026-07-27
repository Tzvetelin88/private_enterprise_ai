"""GraphState TypedDict for the LangGraph agentic RAG workflow."""
from __future__ import annotations

from typing import Any, Optional, TypedDict


class GraphState(TypedDict):
    question: str
    documents: list[dict[str, Any]]
    generation: str
    iterations: int
    grade: str  # "relevant" | "irrelevant"
    query_rewrites: list[str]
    trace_url: str
    # Langfuse trace object threaded through the graph (not serialised)
    lf_trace: Optional[Any]
