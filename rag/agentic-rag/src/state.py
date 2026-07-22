"""GraphState TypedDict for the LangGraph agentic RAG workflow."""
from __future__ import annotations

from typing import Any, TypedDict


class GraphState(TypedDict):
    question: str
    documents: list[dict[str, Any]]
    generation: str
    iterations: int
    grade: str  # "relevant" | "irrelevant"
    query_rewrites: list[str]
    trace_url: str
