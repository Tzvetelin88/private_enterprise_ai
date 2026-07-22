"""LangGraph StateGraph for the self-correcting RAG workflow.

Graph:
  retrieve → grade_documents → generate (if relevant)
                             → rewrite_query → retrieve (if irrelevant, max 3 iterations)
"""
from __future__ import annotations

from langgraph.graph import END, StateGraph  # type: ignore[import-untyped]

from .config import settings
from .nodes import generate, grade_documents, retrieve, rewrite_query
from .state import GraphState


def _should_generate(state: GraphState) -> str:
    """Edge: decide whether to generate or rewrite based on grade + iteration cap."""
    if state.get("grade") == "relevant":
        return "generate"
    if state.get("iterations", 0) >= settings.max_iterations:
        return "generate"  # generate with best available docs after max retries
    return "rewrite_query"


def build_graph() -> StateGraph:
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

    return graph.compile()


# Module-level compiled graph — built once on import
compiled_graph = build_graph()
