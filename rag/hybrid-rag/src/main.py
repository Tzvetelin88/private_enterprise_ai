"""Hybrid RAG FastAPI service."""
from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

import asyncpg
from elasticsearch import AsyncElasticsearch
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .config import settings
from .pipeline import ingest_document, query_pipeline

logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None
_es: AsyncElasticsearch | None = None

_ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md", ".markdown", ".rst"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pool, _es
    _pool = await asyncpg.create_pool(settings.database_url, min_size=2, max_size=10)
    _es = AsyncElasticsearch([settings.elasticsearch_url])
    logger.info(f"Connected to DB and Elasticsearch")
    yield
    if _pool:
        await _pool.close()
    if _es:
        await _es.close()
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
    return {"status": "healthy", "service": "hybrid-rag"}


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    """Upload and index a document."""
    import os
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {ext}")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="File is empty")

    if _pool is None or _es is None:
        raise HTTPException(status_code=503, detail="Service initializing")

    doc_id = await ingest_document(
        pool=_pool,
        es=_es,
        es_index=settings.elasticsearch_index,
        filename=file.filename or "unknown",
        content=content,
        infinity_embeddings_url=settings.infinity_embeddings_url,
        embedding_model=settings.embedding_model,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    return {"document_id": doc_id, "status": "indexed"}


@app.post("/query")
async def query(request: QueryRequest):
    """Hybrid RAG query."""
    if _pool is None or _es is None:
        raise HTTPException(status_code=503, detail="Service initializing")

    result = await query_pipeline(
        pool=_pool,
        es=_es,
        es_index=settings.elasticsearch_index,
        query=request.query,
        infinity_embeddings_url=settings.infinity_embeddings_url,
        infinity_reranker_url=settings.infinity_reranker_url,
        llm_url=settings.llm_url,
        llm_model=settings.llm_model,
        embedding_model=settings.embedding_model,
        reranker_model=settings.reranker_model,
        top_k=request.top_k,
    )
    return result


@app.get("/documents")
async def list_documents():
    """List all indexed documents."""
    if _pool is None:
        raise HTTPException(status_code=503, detail="Service initializing")
    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id::text, name, status, rag_type, created_at FROM documents WHERE rag_type = 'hybrid' ORDER BY created_at DESC"
        )
    return [dict(r) for r in rows]


@app.delete("/documents/{document_id}")
async def delete_document(document_id: str):
    """Delete a document and all its chunks."""
    if _pool is None:
        raise HTTPException(status_code=503, detail="Service initializing")
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid document ID")

    async with _pool.acquire() as conn:
        result = await conn.execute("DELETE FROM documents WHERE id = $1", doc_uuid)

    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Document not found")

    if _es:
        try:
            await _es.delete(index=settings.elasticsearch_index, id=document_id, ignore=[404])
        except Exception:
            pass

    return {"deleted": document_id}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=settings.debug)
