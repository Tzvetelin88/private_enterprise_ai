"""LangGraph nodes for the agentic RAG workflow.

Nodes:
  retrieve          — fetch top-k docs from hybrid-rag service
  grade_documents   — LLM binary relevance scoring
  rewrite_query     — LLM query rephrasing
  generate          — final answer generation
"""
from __future__ import annotations

import logging

import httpx

from .config import settings
from .state import GraphState
from . import tracing

logger = logging.getLogger(__name__)


async def retrieve(state: GraphState) -> GraphState:
    """Retrieve documents from the hybrid-rag service."""
    question = state["question"]
    lf_trace = state.get("lf_trace")
    span = tracing.create_span(lf_trace, "retrieve", input={"query": question, "top_k": settings.top_k})

    async with httpx.AsyncClient(base_url=settings.hybrid_rag_url, timeout=60) as client:
        try:
            resp = await client.post(
                "/query",
                json={"query": question, "top_k": settings.top_k},
            )
            resp.raise_for_status()
            data = resp.json()
            documents = data.get("sources", [])
        except Exception as e:
            logger.warning(f"Retrieval failed ({e}) — empty docs")
            documents = []

    tracing.end_span(span, output={"documents_count": len(documents)})
    return {
        **state,
        "documents": documents,
        "iterations": state.get("iterations", 0) + 1,
    }


async def grade_documents(state: GraphState) -> GraphState:
    """Grade document relevance using the LLM."""
    question = state["question"]
    documents = state["documents"]
    lf_trace = state.get("lf_trace")
    messages = [{"role": "user", "content": ""}]  # filled below

    if not documents:
        return {**state, "grade": "irrelevant"}

    context = "\n".join(d.get("content", "")[:300] for d in documents[:3])
    prompt = (
        f"Given the question: '{question}'\n\n"
        f"And the retrieved documents:\n{context}\n\n"
        f"Are these documents relevant to answering the question? "
        f"Reply with exactly 'relevant' or 'irrelevant' (no explanation)."
    )
    messages = [{"role": "user", "content": prompt}]
    gen = tracing.create_generation(lf_trace, "grade_documents", model=settings.llm_model, input=messages)

    async with httpx.AsyncClient(base_url=settings.llm_url, timeout=settings.llm_timeout) as client:
        try:
            resp = await client.post(
                "/v1/chat/completions",
                json={
                    "model": settings.llm_model,
                    "messages": messages,
                    "max_tokens": 10,
                },
            )
            resp.raise_for_status()
            resp_json = resp.json()
            grade = resp_json["choices"][0]["message"]["content"].strip().lower()
            usage = resp_json.get("usage")
            if "irrelevant" in grade:
                grade = "irrelevant"
            else:
                grade = "relevant"
            tracing.end_generation(gen, output=grade, usage=usage)
        except Exception as e:
            logger.warning(f"Grading failed ({e}) — defaulting to relevant")
            tracing.end_generation(gen, output=f"error: {e}")
            grade = "relevant"

    return {**state, "grade": grade}


async def rewrite_query(state: GraphState) -> GraphState:
    """Rewrite the query using the LLM to improve retrieval."""
    question = state["question"]
    lf_trace = state.get("lf_trace")
    prompt = (
        f"The following question did not retrieve relevant documents: '{question}'\n\n"
        f"Rewrite the question to be more specific and likely to find relevant information. "
        f"Return only the rewritten question, nothing else."
    )
    messages = [{"role": "user", "content": prompt}]
    gen = tracing.create_generation(lf_trace, "rewrite_query", model=settings.llm_model, input=messages)

    async with httpx.AsyncClient(base_url=settings.llm_url, timeout=settings.llm_timeout) as client:
        try:
            resp = await client.post(
                "/v1/chat/completions",
                json={
                    "model": settings.llm_model,
                    "messages": messages,
                    "max_tokens": 100,
                },
            )
            resp.raise_for_status()
            resp_json = resp.json()
            new_question = resp_json["choices"][0]["message"]["content"].strip()
            tracing.end_generation(gen, output=new_question, usage=resp_json.get("usage"))
        except Exception as e:
            logger.warning(f"Query rewrite failed ({e}) — keeping original")
            tracing.end_generation(gen, output=f"error: {e}")
            new_question = question

    rewrites = state.get("query_rewrites", [])
    return {**state, "question": new_question, "query_rewrites": rewrites + [new_question]}


async def generate(state: GraphState) -> GraphState:
    """Generate the final answer using retrieved context."""
    question = state["question"]
    documents = state["documents"]
    lf_trace = state.get("lf_trace")

    context = "\n\n".join(d.get("content", "") for d in documents)
    if not context.strip():
        tracing.end_span(
            tracing.create_span(lf_trace, "generate", input={"question": question}),
            output="No relevant information found in the knowledge base.",
        )
        return {**state, "generation": "No relevant information found in the knowledge base."}

    prompt = (
        f"Answer the following question based only on the provided context.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {question}\n\nAnswer:"
    )
    messages = [{"role": "user", "content": prompt}]
    gen = tracing.create_generation(lf_trace, "generate", model=settings.llm_model, input=messages)

    async with httpx.AsyncClient(base_url=settings.llm_url, timeout=settings.llm_timeout) as client:
        try:
            resp = await client.post(
                "/v1/chat/completions",
                json={
                    "model": settings.llm_model,
                    "messages": messages,
                },
            )
            resp.raise_for_status()
            resp_json = resp.json()
            generation = resp_json["choices"][0]["message"]["content"]
            tracing.end_generation(gen, output=generation, usage=resp_json.get("usage"))
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            tracing.end_generation(gen, output=f"error: {e}")
            generation = "Generation failed — please retry."

    return {**state, "generation": generation}
