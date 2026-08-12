# RAG Pipelines

Three production-grade Retrieval-Augmented Generation pipelines — each an independently deployable FastAPI service, accessible through the API Gateway at `:30880`.

---

## Which Pipeline to Use?

| Pipeline | Port | Best For | Latency |
|----------|------|----------|---------|
| **Hybrid RAG** | 8001 | Documentation search, keyword + semantic queries, support Q&A | Fastest (~100–500 ms) |
| **Agentic RAG** | 8002 | Ambiguous questions, multi-hop reasoning, needs self-correction | Medium (500 ms – 3 s) |
| **Graph RAG** | 8003 | Relationship/dependency queries across documents | Medium–slow |

All three pipelines share: PostgreSQL + pgvector (chunk storage), Infinity Embeddings, Infinity Reranker.

---

## Local Dev Setup

```bash
docker compose -f rag/docker-compose.yml up -d
```

| Service | URL | Credentials |
|---------|-----|-------------|
| Elasticsearch | http://localhost:9200 | — |
| Neo4j Browser | http://localhost:7474 | neo4j / changeme-neo4j |
| Langfuse | http://localhost:3000 | Create account on first visit |

The RAG services themselves (`hybrid-rag`, `agentic-rag`, `graph-rag`) are also started by docker-compose and listen on ports 8001–8003.

> The API Gateway at `:30880` only works when deploying to Kubernetes (kind). For local testing, call the services directly on ports 8001–8003.

---

## 1. Hybrid Search RAG

Combines dense vector search (pgvector cosine similarity) with BM25 keyword search (Elasticsearch), fuses results via Reciprocal Rank Fusion (RRF), then re-scores with a cross-encoder reranker.

### When to Use

- Large corpus of technical docs, wikis, or FAQs
- Queries mix exact terms (product names, error codes) with semantic intent
- Predictable latency matters — this is the fastest pipeline

### Upload a Document

```bash
curl -X POST http://localhost:8001/upload \
  -F "file=@my-doc.pdf"
```

**Response:**
```json
{
  "status": "indexed",
  "document_id": "b5caa827-3f1a-4e89-a012-8c2d71f3990e",
  "document_name": "my-doc.pdf",
  "chunks_created": 14
}
```

### Query

```bash
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{"query": "How do I configure the connection pool?", "top_k": 5}'
```

**Response:**
```json
{
  "answer": "The connection pool is configured via the DATABASE_POOL_SIZE environment variable (default: 10). You can also set min_size and max_size in the asyncpg.create_pool() call...",
  "sources": [
    {
      "content": "Configure the connection pool by setting DATABASE_POOL_SIZE...",
      "document_id": "b5caa827-3f1a-4e89-a012-8c2d71f3990e",
      "document_name": "my-doc.pdf",
      "score": 0.016
    }
  ],
  "metadata": {
    "dense_hits": 5,
    "bm25_hits": 5,
    "reranked": false,
    "latency_ms": 342
  }
}
```

> **Score note:** When the reranker is active, `score` is a 0–1 cross-encoder relevance score. When the reranker is unavailable (fallback), score is the RRF rank score (`1/(60+rank)` ≈ 0.016 for rank 1).

### List Indexed Documents

```bash
curl http://localhost:8001/documents
```

**Response:**
```json
[
  {
    "id": "b5caa827-3f1a-4e89-a012-8c2d71f3990e",
    "filename": "my-doc.pdf",
    "status": "indexed",
    "created_at": "2026-07-27T09:12:33.000+00:00"
  }
]
```

### Delete a Document

```bash
curl -X DELETE http://localhost:8001/documents/b5caa827-3f1a-4e89-a012-8c2d71f3990e
```

**Response:** `204 No Content`

### Acceptance Test Cases

| # | Scenario | Expected |
|---|----------|----------|
| 1 | Upload PDF, then query it | `status: indexed`; `chunks_created > 0`; answer contains doc content |
| 2 | Upload 0-byte file | `422 Unprocessable Entity` |
| 3 | Upload unsupported format (`.exe`) | `415 Unsupported Media Type` |
| 4 | Query empty collection | `sources: []`; answer contains "no information found" |
| 5 | Reranker pod down | `metadata.reranked: false`; still returns `200` with RRF scores |

---

## 2. Agentic / Self-correcting RAG

A LangGraph state machine that iterates: retrieve → grade documents → rewrite query (if needed) → retrieve again → generate. Stops at 3 iterations or when all retrieved documents are graded relevant.

### When to Use

- Ambiguous queries that need query reformulation before retrieval
- Multi-hop reasoning across documents
- You need confidence the retrieved docs are actually relevant (grading step)
- Willing to trade latency for answer quality

### Upload

```bash
curl -X POST http://localhost:8002/upload \
  -F "file=@my-doc.md"
```

**Response:** Same shape as hybrid-rag upload.

### Query

```bash
curl -X POST http://localhost:8002/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the relationship between the auth service and the token expiry setting?",
    "top_k": 5
  }'
```

**Response (simple query, 1 iteration):**
```json
{
  "answer": "The auth service reads TOKEN_EXPIRY_SECONDS from the environment...",
  "sources": [
    {
      "content": "The auth service reads TOKEN_EXPIRY_SECONDS...",
      "document_id": "...",
      "document_name": "my-doc.md",
      "score": 0.89
    }
  ],
  "metadata": {
    "iterations": 1,
    "final_grade": "relevant",
    "query_rewrites": [],
    "trace_url": "http://localhost:3000/trace/abc123"
  }
}
```

**Response (ambiguous query, 2 iterations):**
```json
{
  "answer": "After comparing version 1 and version 2 of the auth flow...",
  "sources": [...],
  "metadata": {
    "iterations": 2,
    "final_grade": "relevant",
    "query_rewrites": ["What changed in the authentication flow between versions?"],
    "trace_url": "http://localhost:3000/trace/def456"
  }
}
```

### List / Delete Documents

Same endpoints as hybrid-rag: `GET /documents`, `DELETE /documents/{id}`.

### Acceptance Test Cases

| # | Scenario | Expected |
|---|----------|----------|
| 1 | Clear, single-hop query | `metadata.iterations == 1` |
| 2 | Ambiguous query | `metadata.iterations >= 2`; `query_rewrites` non-empty |
| 3 | Max iterations hit | Returns best available answer; `metadata.iterations == 3` |
| 4 | Langfuse available | `metadata.trace_url` is non-null |
| 5 | All docs graded irrelevant | Rewrites query and retries; does not return empty answer |

---

## 3. Graph RAG

On upload: extracts entities and relationships using the LLM and stores them as a knowledge graph in Neo4j. On query: traverses the graph first, then filters vector search to graph-connected chunks, then generates.

### When to Use

- Relationship queries: "which X depends on Y?", "what services call Z?"
- Dependency/call graph analysis across many documents
- Rich entity structure (microservices, products, teams, infrastructure)

### Upload (triggers entity extraction)

```bash
curl -X POST http://localhost:8003/upload \
  -F "file=@architecture.md"
```

**Response:** Same shape as hybrid-rag upload.

### Query

```bash
curl -X POST http://localhost:8003/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Which services depend on the authentication service?",
    "top_k": 5
  }'
```

**Response:**
```json
{
  "answer": "The API Gateway and the User Service both depend on the authentication service. The API Gateway calls it for every request to validate tokens, while the User Service depends on it to verify identity during account operations.",
  "sources": [
    {
      "content": "The API Gateway validates tokens by calling /auth/verify on the authentication service...",
      "document_id": "...",
      "document_name": "architecture.md",
      "score": 0.78
    }
  ],
  "metadata": {
    "entities_found": ["authentication-service", "api-gateway", "user-service"],
    "graph_paths": [
      "api-gateway --CALLS--> authentication-service",
      "user-service --DEPENDS_ON--> authentication-service"
    ],
    "traversal_depth": 2
  }
}
```

### Inspect Entity Subgraph

```bash
curl http://localhost:8003/graph/authentication-service
```

**Response:**
```json
{
  "entity": "authentication-service",
  "nodes": [
    {"id": "authentication-service", "type": "Service"},
    {"id": "api-gateway", "type": "Service"},
    {"id": "user-service", "type": "Service"},
    {"id": "postgresql", "type": "Database"}
  ],
  "edges": [
    {"from": "api-gateway", "rel": "CALLS", "to": "authentication-service"},
    {"from": "user-service", "rel": "DEPENDS_ON", "to": "authentication-service"},
    {"from": "authentication-service", "rel": "STORES_IN", "to": "postgresql"}
  ]
}
```

### List / Delete Documents

Same endpoints: `GET /documents`, `DELETE /documents/{id}`.

### Acceptance Test Cases

| # | Scenario | Expected |
|---|----------|----------|
| 1 | Upload two related docs | Entities extracted; stored in Neo4j |
| 2 | Relationship query | `metadata.graph_paths` non-empty |
| 3 | Entity subgraph endpoint | Returns `nodes` and `edges` |
| 4 | Doc with no detectable entities | Still indexed; vector retrieval still works |
| 5 | Query with no graph path found | Falls back to vector similarity; still returns answer |

---

## Common Behaviour (All Pipelines)

| Scenario | Expected |
|----------|----------|
| `GET /documents` | List of indexed documents with `filename`, `status`, `created_at` |
| `DELETE /documents/{id}` | Removes document and all associated chunks; `204 No Content` |
| Upload duplicate filename | Both accepted with distinct UUIDs |
| Supported formats | `.pdf`, `.docx`, `.txt`, `.md` |

---

## API Gateway Paths

When running in Kubernetes (via the install scripts), all endpoints are prefixed:

| Direct (Docker) | Via Gateway (Kubernetes) |
|-----------------|--------------------------|
| `http://localhost:8001/upload` | `http://localhost:30880/v1/rag/hybrid/upload` |
| `http://localhost:8001/query` | `http://localhost:30880/v1/rag/hybrid/query` |
| `http://localhost:8002/upload` | `http://localhost:30880/v1/rag/agentic/upload` |
| `http://localhost:8002/query` | `http://localhost:30880/v1/rag/agentic/query` |
| `http://localhost:8002/query/approve` | `http://localhost:30880/v1/rag/agentic/query/approve` |
| `http://localhost:8002/query/feedback` | `http://localhost:30880/v1/rag/agentic/query/feedback` |
| `http://localhost:8003/upload` | `http://localhost:30880/v1/rag/graph/upload` |
| `http://localhost:8003/query` | `http://localhost:30880/v1/rag/graph/query` |
| `http://localhost:8003/graph/{entity}` | `http://localhost:30880/v1/rag/graph/graph/{entity}` |

---

## Production Patterns (Agentic RAG)

The Agentic RAG service includes four production-grade patterns implemented on top of the base LangGraph pipeline.

### 1. Structured Output Parsing (LangChain)

**What it does:** The `grade_documents` node calls the LLM through a real LangChain `Runnable` (`llm_with_fallback`, a `ChatOllama` chain) and parses its response with `PydanticOutputParser(GradeResult)`, where `GradeResult.grade: Literal["relevant", "irrelevant"]`. On a parse failure it retries up to 2 more times before falling back to a lenient keyword heuristic — so the grade is always one of exactly two values, never freeform text like "YES" or "The documents seem relevant".

**How to observe:** `metadata.final_grade` in every `/query` response is always exactly `"relevant"` or `"irrelevant"`.

```json
{"metadata": {"final_grade": "relevant", ...}}
```

### 2. LLM Fallback Chain (LangChain)

**What it does:** `grade_documents`, `rewrite_query`, and `generate` all call `llm_with_fallback = ChatOllama(model=LLM_MODEL).with_fallbacks([ChatOllama(model=FALLBACK_LLM_MODEL)])`. If the primary model is unreachable, LangChain's own fallback mechanism transparently retries the same call against the fallback model — no manual retry loop in node code.

**How to observe:** When the primary Ollama model is unavailable, the response is still returned successfully (via `FALLBACK_LLM_MODEL`, default `llama3.2:3b`) instead of erroring out.

### 3. Redis LLM Response Cache (LangChain global cache)

**What it does:** On startup, the service sets the global LangChain LLM cache (`langchain_core.globals.set_llm_cache()`) to a Redis backend. Because every node's LLM call goes through a LangChain `Runnable` (see pattern 2), this cache actually intercepts them: identical prompts (same grading question + context, same rewrite, same generation prompt) are served from Redis in milliseconds instead of re-invoking the model.

**How to observe:**
```bash
# First call — cache miss, full LLM invoke (~2 s)
curl -X POST http://localhost:8002/query \
  -H 'Content-Type: application/json' \
  -d '{"query": "What is pgvector?", "top_k": 3}'

# Second identical call — cache hit (<50 ms)
curl -X POST http://localhost:8002/query \
  -H 'Content-Type: application/json' \
  -d '{"query": "What is pgvector?", "top_k": 3}'
```

Redis must be running (included in `docker-compose.yml`). If Redis is down, LLM calls run normally — no service interruption.

### 4. LangGraph Checkpointing (PostgreSQL)

**What it does:** Every workflow run is persisted to PostgreSQL via `AsyncPostgresSaver`. The `checkpoint_id` (LangGraph `thread_id`) appears in every `/query` response so the run can be inspected or resumed.

**How to observe:**
```json
{"metadata": {"checkpoint_id": "3f1a4e89-a012-8c2d-b5ca-a827f3990e4b", ...}}
```

Set `CHECKPOINTING_ENABLED=false` to disable (not recommended in production).

### 5. Human-in-the-Loop (HITL) — LangGraph interrupt

**What it does:** When `HITL_ENABLED=true`, the workflow pauses *after* grading documents and *before* generating the answer. The client receives `status: "paused"` with the retrieved documents and a `checkpoint_id`. A human can review the context and approve via `POST /query/approve`, which verifies the checkpoint exists (a real 404 if not, rather than string-matching an error message), records `hitl_approved: true` on the persisted state as an audit trail, and resumes the workflow — continuing the same Langfuse trace the paused run started.

**How to observe:**

```bash
# Step 1 — query pauses before generate
curl -X POST http://localhost:8002/query \
  -H 'Content-Type: application/json' \
  -d '{"query": "Explain pgvector", "top_k": 3}'
# → {"status": "paused", "checkpoint_id": "thread-abc", "documents": [...]}

# Step 2 — human reviews documents, approves
curl -X POST http://localhost:8002/query/approve \
  -H 'Content-Type: application/json' \
  -d '{"thread_id": "thread-abc"}'
# → {"answer": "...", "sources": [...], "metadata": {...}}

# Unknown thread_id → a real 404, not a 500
curl -X POST http://localhost:8002/query/approve \
  -H 'Content-Type: application/json' \
  -d '{"thread_id": "does-not-exist"}'
# → 404 {"detail": "Checkpoint not found"}
```

### 6. Langfuse Visual Tracing + User Feedback

**What it does:** Every `POST /query` call creates **one** Langfuse trace (via the low-level SDK) and threads only its `trace_id` (a plain string) through `GraphState` — not a live SDK object, since `GraphState` is checkpointed to PostgreSQL and a live client handle wouldn't survive that or a restart. Each node rehydrates a trace handle from `trace_id` (`retrieve` creates a manual span; `grade_documents`/`rewrite_query`/`generate` get automatic generation spans from a callback handler bound to that same trace_id via `get_client().trace(id=trace_id).get_langchain_handler()`) — so every node shows up nested under the **same** trace, not scattered across disconnected ones. Both `trace_url` and `trace_id` are returned in `metadata`; `POST /query/feedback` uses `trace_id` to attach a user rating.

**How to observe:**

```json
{"metadata": {"trace_url": "http://localhost:3000/trace/abc123", "trace_id": "abc123", ...}}
```

1. Open Langfuse at **http://localhost:3000** (create an account on first visit)
2. Go to **Settings → API Keys** and paste the keys into `docker-compose.yml` (`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`)
3. Send any `/query` — the `trace_url` in the response opens a single trace with all four node spans (`retrieve`, `grade_documents`, `rewrite_query`, `generate`) nested under it, each with latency and token usage
4. Record feedback against it:

```bash
curl -X POST http://localhost:8002/query/feedback \
  -H 'Content-Type: application/json' \
  -d '{"trace_id": "abc123", "score": 1, "comment": "correct and well-sourced"}'
# → {"status": "recorded", "trace_id": "abc123"}
```

The score appears on the trace in the Langfuse UI, alongside its spans.
