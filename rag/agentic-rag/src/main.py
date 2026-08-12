"""Agentic RAG FastAPI service — LangGraph self-correcting retrieval.

Production patterns activated in this service:
  - Pydantic structured output parsing for grade_documents, via a real
    PydanticOutputParser against a LangChain LLM call (nodes.py)
  - LLM fallback chain: ChatOllama.with_fallbacks() (nodes.py)
  - Redis LLM response cache (setup_llm_cache, startup) — effective because
    all node LLM calls go through LangChain, which is what set_llm_cache()
    intercepts
  - LangGraph PostgreSQL checkpointing (build_graph, startup); GraphState only
    carries a serialisable trace_id, never a live SDK object
  - Human-in-the-Loop (HITL) pause + POST /query/approve endpoint, which
    verifies the checkpoint exists, records hitl_approved=True, and resumes
    the same Langfuse trace
  - Langfuse visual tracing: one trace per request (trace_url + trace_id in
    the response), with node-level spans nested under it via a callback
    handler bound to that trace_id; POST /query/feedback attaches a score
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from uuid import uuid4

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from .config import settings
from .workflow import build_graph
from . import tracing

logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

_ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md", ".markdown", ".rst"}


def _get_trace_url(lf_trace) -> str:
    """Extract the Langfuse trace URL from a trace object, if available."""
    if lf_trace is None:
        return ""
    try:
        # Langfuse SDK v2: trace.get_trace_url() or trace.trace_url
        if hasattr(lf_trace, "get_trace_url"):
            return lf_trace.get_trace_url() or ""
        if hasattr(lf_trace, "trace_url"):
            return lf_trace.trace_url or ""
        # Fallback: construct URL from host + trace id
        if hasattr(lf_trace, "id"):
            host = settings.langfuse_host.rstrip("/")
            return f"{host}/trace/{lf_trace.id}"
    except Exception as exc:
        logger.debug("Could not extract trace URL: %s", exc)
    return ""


def _callbacks_for(trace_id: str) -> list:
    """Build the callback list for a LangGraph run config.

    For the langfuse backend, binds a CallbackHandler to *this* trace_id so
    node-level LLM spans nest under the trace already created via the
    low-level SDK (tracing.start_trace) instead of starting a second,
    disconnected trace. Other backends (e.g. langsmith) fall back to the
    generic shared callback helper, which doesn't need trace-id binding.
    """
    if settings.tracing_backend == "langfuse":
        handler = tracing.get_callback_handler(trace_id)
        return [handler] if handler else []

    from shared.observability.tracing import get_callbacks  # noqa: PLC0415
    return get_callbacks()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s v%s", settings.app_name, settings.app_version)
    logger.info("LangGraph max_iterations=%d  hitl_enabled=%s  checkpointing=%s",
                settings.max_iterations, settings.hitl_enabled, settings.checkpointing_enabled)
    logger.info("Tracing backend: %s", settings.tracing_backend)

    # Eagerly initialise Langfuse so key errors surface at startup
    tracing.get_client()

    # Redis LLM response cache (graceful fallback — warning only if unavailable)
    try:
        from shared.cache.redis_cache import setup_llm_cache
        setup_llm_cache(settings.redis_url, settings.llm_cache_ttl)
    except Exception as exc:
        logger.warning("Redis cache setup failed: %s", exc)

    # Build the LangGraph graph (async — sets up checkpointer + HITL)
    pool = None
    if settings.checkpointing_enabled:
        try:
            import asyncpg  # type: ignore[import-untyped]
            pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=5)
            logger.info("asyncpg pool created for LangGraph checkpointing")
        except Exception as exc:
            logger.warning("Could not create asyncpg pool for checkpointing: %s", exc)

    app.state.compiled_graph = await build_graph(pool)
    app.state.db_pool = pool
    logger.info("LangGraph graph compiled and ready")

    yield

    if pool:
        await pool.close()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)


class QueryRequest(BaseModel):
    query: str
    top_k: int = 5


class ApproveRequest(BaseModel):
    thread_id: str


class FeedbackRequest(BaseModel):
    trace_id: str
    score: float
    comment: str | None = None


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "agentic-rag"}


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    """Upload a document — delegates to hybrid-rag for indexing."""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {ext}")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="File is empty")

    async with httpx.AsyncClient(base_url=settings.hybrid_rag_url, timeout=120) as client:
        resp = await client.post(
            "/upload",
            files={"file": (file.filename, content, file.content_type)},
        )
        resp.raise_for_status()
        return resp.json()


@app.post("/query")
async def query(request: QueryRequest):
    """Run the agentic self-correcting RAG pipeline.

    When hitl_enabled=True the workflow pauses before the generate node and
    returns status="paused" with the checkpoint_id.  Use POST /query/approve
    to resume.
    """
    compiled_graph = app.state.compiled_graph

    thread_id = str(uuid4())
    lf_trace = tracing.start_trace(
        name="agentic-rag-query",
        input={"query": request.query, "top_k": request.top_k},
        metadata={"service": "agentic-rag", "thread_id": thread_id},
    )
    trace_id = lf_trace.id if lf_trace is not None else ""

    initial_state = {
        "question": request.query,
        "documents": [],
        "generation": "",
        "iterations": 0,
        "grade": "",
        "query_rewrites": [],
        "trace_url": "",
        # Only the trace_id (a plain string) goes into GraphState — it gets
        # checkpointed to PostgreSQL, and a live Langfuse SDK object would not
        # survive that round-trip. Nodes rehydrate a trace handle from this id.
        "trace_id": trace_id,
        "hitl_approved": False,
        "thread_id": thread_id,  # GraphState field — "checkpoint_id" is reserved by LangGraph
    }

    # Build the LangGraph invocation config: thread_id for checkpointing, plus a
    # callback handler *bound to this request's trace_id* so every LLM span
    # LangChain/LangGraph create nest under the same trace as trace_url below —
    # not a second, disconnected trace.
    run_config: dict = {
        "callbacks": _callbacks_for(trace_id),
        "configurable": {"thread_id": thread_id},
    }

    try:
        final_state = await compiled_graph.ainvoke(initial_state, config=run_config)
    except Exception as e:
        logger.error("Graph execution failed: %s", e)
        tracing.end_trace(lf_trace, output={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"Pipeline error: {e}")

    # Populate trace_url from the Langfuse trace object
    trace_url = _get_trace_url(lf_trace)

    tracing.end_trace(
        lf_trace,
        output={
            "answer": final_state.get("generation", ""),
            "iterations": final_state.get("iterations", 0),
            "final_grade": final_state.get("grade", ""),
            "trace_url": trace_url,
        },
    )

    sources = [
        {
            "content": d.get("content", ""),
            "document_id": d.get("document_id", ""),
            "document_name": d.get("document_name", ""),
            "score": d.get("score", 0.0),
        }
        for d in final_state.get("documents", [])
    ]

    # HITL: if the workflow paused before generate, return paused status
    if settings.hitl_enabled and not final_state.get("generation"):
        return {
            "status": "paused",
            "checkpoint_id": thread_id,
            "documents": sources,
            "metadata": {
                "iterations": final_state.get("iterations", 0),
                "final_grade": final_state.get("grade", ""),
                "query_rewrites": final_state.get("query_rewrites", []),
                "trace_url": trace_url,
                "trace_id": trace_id,
                "checkpoint_id": thread_id,
            },
        }

    return {
        "answer": final_state.get("generation", ""),
        "sources": sources,
        "metadata": {
            "iterations": final_state.get("iterations", 0),
            "final_grade": final_state.get("grade", ""),
            "query_rewrites": final_state.get("query_rewrites", []),
            "trace_url": trace_url,
            "trace_id": trace_id,
            "checkpoint_id": thread_id if settings.checkpointing_enabled else "",
        },
    }


@app.post("/query/approve")
async def approve(request: ApproveRequest):
    """Resume a HITL-paused workflow after human approval.

    The workflow was paused before the generate node (interrupt_before=["generate"]).
    Calling this endpoint resumes it with the saved checkpoint state.

    Request body: {"thread_id": "<checkpoint_id from /query response>"}
    """
    if not settings.hitl_enabled:
        raise HTTPException(status_code=400, detail="HITL is not enabled (HITL_ENABLED=false)")
    if not settings.checkpointing_enabled:
        raise HTTPException(status_code=400, detail="Checkpointing is required for HITL resume")

    compiled_graph = app.state.compiled_graph
    resume_config = {"configurable": {"thread_id": request.thread_id}}

    # Check the checkpoint actually exists before touching it — relying on
    # exception-message sniffing here is fragile (message text is not a
    # stable contract across AsyncPostgresSaver versions).
    try:
        snapshot = await compiled_graph.aget_state(resume_config)
    except Exception as e:
        logger.error("Could not read checkpoint for thread_id=%s: %s", request.thread_id, e)
        raise HTTPException(status_code=500, detail=f"Checkpoint lookup error: {e}")

    if not snapshot or not snapshot.values:
        raise HTTPException(status_code=404, detail="Checkpoint not found")

    # Continue the same Langfuse trace the paused run started, and set
    # hitl_approved=True on the persisted state as a real audit signal.
    trace_id = snapshot.values.get("trace_id", "")
    resume_config = {
        "callbacks": _callbacks_for(trace_id),
        "configurable": {"thread_id": request.thread_id},
    }

    try:
        await compiled_graph.update_state(resume_config, {"hitl_approved": True})
        # Passing None as input resumes the workflow from the last checkpoint
        final_state = await compiled_graph.ainvoke(None, config=resume_config)
    except Exception as e:
        logger.error("HITL resume failed for thread_id=%s: %s", request.thread_id, e)
        raise HTTPException(status_code=500, detail=f"Resume error: {e}")

    sources = [
        {
            "content": d.get("content", ""),
            "document_id": d.get("document_id", ""),
            "document_name": d.get("document_name", ""),
            "score": d.get("score", 0.0),
        }
        for d in final_state.get("documents", [])
    ]

    return {
        "answer": final_state.get("generation", ""),
        "sources": sources,
        "metadata": {
            "iterations": final_state.get("iterations", 0),
            "final_grade": final_state.get("grade", ""),
            "query_rewrites": final_state.get("query_rewrites", []),
            "trace_url": final_state.get("trace_url", ""),
            "trace_id": trace_id,
            "checkpoint_id": request.thread_id,
        },
    }


@app.post("/query/feedback")
async def feedback(request: FeedbackRequest):
    """Record a user-feedback score against a Langfuse trace.

    Request body: {"trace_id": "<trace_id from /query response metadata>",
                    "score": <float>, "comment": "<optional>"}
    """
    recorded = tracing.score_trace(
        request.trace_id, name="user-feedback", value=request.score, comment=request.comment
    )
    if not recorded:
        raise HTTPException(status_code=503, detail="Tracing backend unavailable — feedback not recorded")
    return {"status": "recorded", "trace_id": request.trace_id}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=settings.debug)
