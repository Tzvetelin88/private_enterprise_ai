"""Graph RAG FastAPI service — entity extraction, Neo4j knowledge graph, hybrid traversal."""
from __future__ import annotations

import logging
import os
import uuid
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from .config import settings
from .graph import Neo4jClient
from .pipeline import ingest_document, query_pipeline

logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None
_neo4j: Neo4jClient | None = None

_ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md", ".markdown", ".rst"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pool, _neo4j
    _pool = await asyncpg.create_pool(settings.database_url, min_size=2, max_size=10)
    _neo4j = Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    neo4j_ok = await _neo4j.health_check()
    logger.info(f"Neo4j connected: {neo4j_ok}")
    yield
    if _pool:
        await _pool.close()
    if _neo4j:
        await _neo4j.close()
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
    return {"status": "healthy", "service": "graph-rag"}


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {ext}")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="File is empty")
    if _pool is None or _neo4j is None:
        raise HTTPException(status_code=503, detail="Service initializing")

    doc_id = await ingest_document(
        pool=_pool,
        neo4j=_neo4j,
        filename=file.filename or "unknown",
        content=content,
        infinity_embeddings_url=settings.infinity_embeddings_url,
        embedding_model=settings.embedding_model,
        llm_url=settings.llm_url,
        llm_model=settings.llm_model,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    return {"document_id": doc_id, "status": "indexed"}


@app.post("/query")
async def query(request: QueryRequest):
    if _pool is None or _neo4j is None:
        raise HTTPException(status_code=503, detail="Service initializing")

    return await query_pipeline(
        pool=_pool,
        neo4j=_neo4j,
        query=request.query,
        infinity_embeddings_url=settings.infinity_embeddings_url,
        llm_url=settings.llm_url,
        llm_model=settings.llm_model,
        embedding_model=settings.embedding_model,
        traversal_depth=settings.traversal_depth,
        top_k=request.top_k,
    )


@app.get("/documents")
async def list_documents():
    if _pool is None:
        raise HTTPException(status_code=503, detail="Service initializing")
    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id::text, name, status, rag_type, created_at FROM documents WHERE rag_type = 'graph' ORDER BY created_at DESC"
        )
    return [dict(r) for r in rows]


@app.delete("/documents/{document_id}")
async def delete_document(document_id: str):
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
    return {"deleted": document_id}


@app.get("/graph/{entity_name}")
async def get_entity_subgraph(entity_name: str):
    """Return entity subgraph JSON for visualization."""
    if _neo4j is None:
        raise HTTPException(status_code=503, detail="Service initializing")
    return await _neo4j.get_entity_subgraph(entity_name)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=settings.debug)
