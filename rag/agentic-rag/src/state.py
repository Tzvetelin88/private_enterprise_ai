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
    # Langfuse trace id threaded through the graph. A plain string (not the live
    # SDK trace object) so this field stays serialisable when AsyncPostgresSaver
    # checkpoints GraphState to PostgreSQL — a live client object would either
    # fail to serialise or deserialise into a stale handle after a restart.
    trace_id: str
    # Human-in-the-Loop: set to True by POST /query/approve to resume a paused workflow
    hitl_approved: bool
    # The LangGraph thread_id used for checkpointing and HITL resume.
    # NOTE: named `thread_id`, not `checkpoint_id` — LangGraph reserves
    # "checkpoint_id" as an internal channel name (it's part of its own
    # checkpoint-tuple config schema) and refuses to compile a graph whose
    # state schema uses it: ValueError("Channel name 'checkpoint_id' is
    # reserved"). The public API field is still called checkpoint_id
    # (unchanged contract) — only this internal GraphState key differs.
    thread_id: str
