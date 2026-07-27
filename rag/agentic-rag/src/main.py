"""Agentic RAG FastAPI service — LangGraph self-correcting retrieval."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from shared.ingestion.parsers import parse
from shared.ingestion.chunker import chunk_text

from .config import settings
from .workflow import compiled_graph
from . import tracing

logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

_ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md", ".markdown", ".rst"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"LangGraph max_iterations={settings.max_iterations}")
    logger.info(f"Tracing backend: {settings.tracing_backend}")
    # Eagerly initialise Langfuse so key errors surface at startup
    tracing.get_client()
    yield
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)


class QueryRequest(BaseModel):
    query: str
    top_k: int = 5


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "agentic-rag"}


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    """Upload a document — delegates to hybrid-rag for indexing."""
    import httpx
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
    """Run the agentic self-correcting RAG pipeline."""
    lf_trace = tracing.start_trace(
        name="agentic-rag-query",
        input={"query": request.query, "top_k": request.top_k},
        metadata={"service": "agentic-rag"},
    )

    initial_state = {
        "question": request.query,
        "documents": [],
        "generation": "",
        "iterations": 0,
        "grade": "",
        "query_rewrites": [],
        "trace_url": "",
        "lf_trace": lf_trace,
    }

    try:
        final_state = await compiled_graph.ainvoke(initial_state)
    except Exception as e:
        logger.error(f"Graph execution failed: {e}")
        tracing.end_trace(lf_trace, output={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"Pipeline error: {e}")

    tracing.end_trace(
        lf_trace,
        output={
            "answer": final_state.get("generation", ""),
            "iterations": final_state.get("iterations", 0),
            "final_grade": final_state.get("grade", ""),
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

    return {
        "answer": final_state.get("generation", ""),
        "sources": sources,
        "metadata": {
            "iterations": final_state.get("iterations", 0),
            "final_grade": final_state.get("grade", ""),
            "query_rewrites": final_state.get("query_rewrites", []),
            "trace_url": final_state.get("trace_url", ""),
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=settings.debug)
