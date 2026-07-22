"""Unified RAG query/response Pydantic models shared by all three RAG services."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class RAGQueryRequest(BaseModel):
    query: str
    collection: str | None = None
    top_k: int = 5
    pipeline: Literal["hybrid", "agentic", "graph"] = "hybrid"


class RAGQueryResponse(BaseModel):
    answer: str
    sources: list[dict[str, Any]]
    metadata: dict[str, Any]
