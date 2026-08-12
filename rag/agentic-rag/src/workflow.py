"""LangGraph StateGraph for the self-correcting RAG workflow.

Graph:
  retrieve → grade_documents → generate (if relevant)
                             → rewrite_query → retrieve (if irrelevant, max 3 iterations)

LangGraph patterns used:
  - AsyncPostgresSaver checkpointer: workflow state persists to PostgreSQL; survives restarts
  - interrupt_before=["generate"]: HITL pause before generate node when hitl_enabled=True
"""
from __future__ import annotations

import logging

from langgraph.graph import END, StateGraph  # type: ignore[import-untyped]

from .config import settings
from .nodes import generate, grade_documents, retrieve, rewrite_query
from .state import GraphState

logger = logging.getLogger(__name__)


def _should_generate(state: GraphState) -> str:
    """Edge: decide whether to generate or rewrite based on grade + iteration cap."""
    if state.get("grade") == "relevant":
        return "generate"
    if state.get("iterations", 0) >= settings.max_iterations:
        return "generate"  # generate with best available docs after max retries
    return "rewrite_query"


async def build_graph(pool=None):
    """Build and compile the LangGraph StateGraph.

    Args:
        pool: asyncpg connection pool for PostgreSQL checkpointing.
              When None or checkpointing_enabled=False, compiles without a checkpointer.

    Returns:
        A compiled LangGraph CompiledGraph ready for ainvoke().
    """
    graph = StateGraph(GraphState)

    graph.add_node("retrieve", retrieve)
    graph.add_node("grade_documents", grade_documents)
    graph.add_node("rewrite_query", rewrite_query)
    graph.add_node("generate", generate)

    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "grade_documents")
    graph.add_conditional_edges(
        "grade_documents",
        _should_generate,
        {"generate": "generate", "rewrite_query": "rewrite_query"},
    )
    graph.add_edge("rewrite_query", "retrieve")
    graph.add_edge("generate", END)

    checkpointer = None
    if settings.checkpointing_enabled and pool is not None:
        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver  # type: ignore[import-untyped]
            checkpointer = AsyncPostgresSaver(pool)
            await checkpointer.setup()  # creates checkpoint tables if absent
            logger.info("LangGraph checkpointing enabled (PostgreSQL)")
        except Exception as exc:
            logger.warning("Could not enable PostgreSQL checkpointer: %s — running without persistence", exc)

    interrupt_before = ["generate"] if settings.hitl_enabled else []
    if interrupt_before:
        logger.info("HITL enabled — workflow will pause before 'generate' node")

    return graph.compile(checkpointer=checkpointer, interrupt_before=interrupt_before)
