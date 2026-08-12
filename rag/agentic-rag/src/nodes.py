"""LangGraph nodes for the agentic RAG workflow.

Nodes:
  retrieve          — fetch top-k docs from hybrid-rag service
  grade_documents   — LLM binary relevance scoring (Pydantic-validated output)
  rewrite_query     — LLM query rephrasing
  generate          — final answer generation

LangChain patterns used:
  - All LLM calls go through a LangChain ChatOllama Runnable (llm_with_fallback),
    not raw httpx — this is what makes the Redis LLM cache (set_llm_cache())
    and .with_fallbacks() actually take effect; neither can intercept a raw
    httpx.post() call.
  - GradeResult (Pydantic BaseModel) + PydanticOutputParser is the primary
    grade-parsing path, guaranteeing grade is always "relevant" or "irrelevant".
    It retries up to 2 times on malformed output before falling back to a
    lenient regex/keyword heuristic (_parse_grade) as a last resort.
  - LLM fallback chain: primary_llm.with_fallbacks([fallback_llm]) for transparent failover.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Literal

import httpx
from langchain_core.exceptions import OutputParserException
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import RunnableConfig
from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field, ValidationError

from .config import settings
from .state import GraphState
from . import tracing

logger = logging.getLogger(__name__)


# ── Pydantic structured output model ─────────────────────────────────────────

class GradeResult(BaseModel):
    """Validated LLM grading output — grade is always 'relevant' or 'irrelevant'."""
    grade: Literal["relevant", "irrelevant"] = Field(
        ...,
        description="Whether the retrieved documents are relevant to the question.",
    )


_grade_parser = PydanticOutputParser(pydantic_object=GradeResult)


def _build_llm():
    """Build the primary+fallback LangChain chat model chain.

    Routing every node's LLM call through this Runnable (instead of raw httpx)
    is what makes F2 (transparent fallback), F3 (Redis response cache), and
    Langfuse's automatic per-call generation spans all work — they all key off
    LangChain's invocation path.
    """
    primary = ChatOllama(
        base_url=settings.llm_url,
        model=settings.llm_model,
        timeout=settings.llm_timeout,
        reasoning=settings.llm_reasoning_enabled,
    )
    fallback = ChatOllama(
        base_url=settings.llm_url,
        model=settings.fallback_llm_model,
        timeout=settings.llm_timeout,
        reasoning=settings.llm_reasoning_enabled,
    )
    return primary.with_fallbacks([fallback])


llm_with_fallback = _build_llm()


def _parse_grade(raw: str, retries_left: int = 2) -> str:
    """Lenient fallback parser used only after PydanticOutputParser has failed
    on every retry — attempts strict JSON extraction, then keyword matching.
    On final failure (retries_left == 0) defaults to 'relevant'.
    """
    # 1. Try extracting JSON from the response (LLM may wrap it in prose)
    json_match = re.search(r'\{[^}]*"grade"[^}]*\}', raw, re.IGNORECASE)
    if json_match:
        try:
            data = json.loads(json_match.group())
            result = GradeResult(**data)
            return result.grade
        except Exception:
            pass

    # 2. Try plain text containing the exact word
    lower = raw.strip().lower()
    if lower in ("relevant", "irrelevant"):
        return lower
    if "irrelevant" in lower:
        return "irrelevant"
    if "relevant" in lower:
        return "relevant"

    # 3. Retry or default
    if retries_left > 0:
        logger.debug("Grade parse failed on '%s', %d retries left — returning relevant", raw, retries_left)
    else:
        logger.warning("Grade parse exhausted retries on '%s' — defaulting to relevant", raw)
    return "relevant"


async def retrieve(state: GraphState, config: RunnableConfig | None = None) -> GraphState:
    """Retrieve documents from the hybrid-rag service."""
    question = state["question"]
    lf_trace = tracing.get_trace(state.get("trace_id", ""))
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


async def grade_documents(state: GraphState, config: RunnableConfig | None = None) -> GraphState:
    """Grade document relevance using the LLM.

    Primary path: PydanticOutputParser(GradeResult) against llm_with_fallback,
    retried up to 2 times on malformed output. If every attempt still fails to
    parse, falls back to the lenient _parse_grade heuristic on the last raw
    response, defaulting to 'relevant' only as an absolute last resort.
    The LLM call itself transparently fails over to fallback_llm_model via
    ChatOllama.with_fallbacks() if the primary model is unreachable.
    """
    question = state["question"]
    documents = state["documents"]
    lf_trace = tracing.get_trace(state.get("trace_id", ""))

    if not documents:
        return {**state, "grade": "irrelevant"}

    context = "\n".join(d.get("content", "")[:300] for d in documents[:3])
    format_instructions = _grade_parser.get_format_instructions()
    prompt = (
        f"Given the question: '{question}'\n\n"
        f"And the retrieved documents:\n{context}\n\n"
        f"Are these documents relevant to answering the question?\n"
        f"{format_instructions}"
    )
    messages = [HumanMessage(content=prompt)]
    gen = tracing.create_generation(lf_trace, "grade_documents", model=settings.llm_model, input=prompt)

    grade = "relevant"
    raw = ""
    usage = None
    max_attempts = 3  # 1 initial try + 2 retries, per F1's spec

    for attempt in range(max_attempts):
        try:
            response = await llm_with_fallback.ainvoke(messages, config=config)
            raw = (response.content or "").strip()
            usage = getattr(response, "usage_metadata", None)
            result = _grade_parser.parse(raw)
            grade = result.grade
            break
        except (OutputParserException, ValidationError) as e:
            logger.debug("grade_documents: parse attempt %d/%d failed (%s)", attempt + 1, max_attempts, e)
            continue
        except Exception as e:
            logger.warning("grade_documents: LLM call failed (%s) — defaulting to relevant", e)
            break
    else:
        # PydanticOutputParser failed on every attempt — try the lenient heuristic
        # on the last raw response before giving up entirely.
        grade = _parse_grade(raw, retries_left=0) if raw else "relevant"

    tracing.end_generation(gen, output=grade, usage=usage)
    return {**state, "grade": grade}


async def rewrite_query(state: GraphState, config: RunnableConfig | None = None) -> GraphState:
    """Rewrite the query using the LLM to improve retrieval."""
    question = state["question"]
    lf_trace = tracing.get_trace(state.get("trace_id", ""))
    prompt = (
        f"The following question did not retrieve relevant documents: '{question}'\n\n"
        f"Rewrite the question to be more specific and likely to find relevant information. "
        f"Return only the rewritten question, nothing else."
    )
    messages = [HumanMessage(content=prompt)]
    gen = tracing.create_generation(lf_trace, "rewrite_query", model=settings.llm_model, input=prompt)

    try:
        response = await llm_with_fallback.ainvoke(messages, config=config)
        new_question = (response.content or "").strip()
        tracing.end_generation(gen, output=new_question, usage=getattr(response, "usage_metadata", None))
    except Exception as e:
        logger.warning(f"Query rewrite failed ({e}) — keeping original")
        tracing.end_generation(gen, output=f"error: {e}")
        new_question = question

    rewrites = state.get("query_rewrites", [])
    return {**state, "question": new_question, "query_rewrites": rewrites + [new_question]}


async def generate(state: GraphState, config: RunnableConfig | None = None) -> GraphState:
    """Generate the final answer using retrieved context."""
    question = state["question"]
    documents = state["documents"]
    lf_trace = tracing.get_trace(state.get("trace_id", ""))

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
    messages = [HumanMessage(content=prompt)]
    gen = tracing.create_generation(lf_trace, "generate", model=settings.llm_model, input=prompt)

    try:
        response = await llm_with_fallback.ainvoke(messages, config=config)
        generation = response.content
        tracing.end_generation(gen, output=generation, usage=getattr(response, "usage_metadata", None))
    except Exception as e:
        logger.error(f"Generation failed: {e}")
        tracing.end_generation(gen, output=f"error: {e}")
        generation = "Generation failed — please retry."

    return {**state, "generation": generation}
