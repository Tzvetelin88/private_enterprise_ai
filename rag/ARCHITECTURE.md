# RAG Architecture

Technical architecture for all three RAG pipelines in this project.
Each pipeline is a separate FastAPI service deployed in Kubernetes, accessible via the API Gateway.

---

## High-Level System Architecture

```mermaid
graph LR
    Client([Client])
    GW[API Gateway :30880]
    Client --> GW

    GW -->|/v1/chat| Ollama[Ollama :11434]
    GW -->|/v1/embeddings| InfEmb[Infinity-embeddings :7997]
    GW -->|/v1/rag/hybrid/*| HR[hybrid-rag :8001]
    GW -->|/v1/rag/agentic/*| AR[agentic-rag :8002]
    GW -->|/v1/rag/graph/*| GR[graph-rag :8003]

    HR --> InfEmb
    HR --> InfRnk[Infinity-reranker :7998]
    HR --> PG[(PostgreSQL + pgvector)]
    HR --> ES[(Elasticsearch)]

    AR --> InfEmb
    AR --> InfRnk
    AR --> PG
    AR --> Ollama
    AR --> LF[Langfuse :3000]

    GR --> InfEmb
    GR --> PG
    GR --> Neo4j[(Neo4j :7687)]
    GR --> Ollama
```

---

## Shared Infrastructure

| Service | Port | Role |
|---------|------|------|
| `infinity-embeddings` | 7997 (ClusterIP) | Dense vector embeddings (`BAAI/bge-small-en-v1.5`, 384-dim) |
| `infinity-reranker` | 7998 (ClusterIP) | Cross-encoder reranking (`BAAI/bge-reranker-v2-m3`) |
| PostgreSQL + pgvector | 5432 (ClusterIP) | Document/chunk storage + HNSW vector index; LangGraph checkpoints |
| Elasticsearch | 9200 | BM25 keyword index (Hybrid RAG only) |
| Neo4j | 7687 | Knowledge graph (Graph RAG only) |
| Redis | 6379 | LLM response cache (Agentic RAG; `redis:7-alpine`) |
| Langfuse | 3000 | Agent trace observability (Agentic RAG) |
| Ollama | 11434 (host) | LLM generation (all pipelines) |

---

## Shared Code (`rag/shared/`)

All three pipelines import from the shared module:

| Module | Purpose |
|--------|---------|
| `ingestion/parsers.py` | PDF, DOCX, TXT, Markdown parsing |
| `ingestion/chunker.py` | Fixed-size chunking with overlap |
| `embeddings/client.py` | Async Infinity-embeddings wrapper (batched, retry-on-503) |
| `reranking/reranker.py` | Async Infinity-reranker wrapper (graceful fallback) |
| `observability/tracing.py` | Langfuse/LangSmith callback setup (config-driven) |
| `evaluation/metrics.py` | Lightweight faithfulness and relevance metrics |
| `cache/redis_cache.py` | Redis LLM response cache — calls `langchain_core.globals.set_llm_cache()` |

---

## 1. Hybrid Search RAG

### Data Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant GW as API Gateway
    participant HR as hybrid-rag
    participant InfE as Infinity-embeddings
    participant PG as pgvector
    participant ES as Elasticsearch
    participant InfR as Infinity-reranker
    participant LLM as Ollama

    C->>GW: POST /v1/rag/hybrid/query
    GW->>HR: forward request
    HR->>InfE: embed(query)
    par Dense retrieval
        HR->>PG: cosine similarity search (top-k)
    and BM25 retrieval
        HR->>ES: multi_match query (top-k)
    end
    HR->>HR: RRF fusion (merge + rescore)
    HR->>InfR: rerank(query, merged_docs)
    HR->>LLM: generate(query + top-k context)
    HR->>GW: {answer, sources, metadata}
    GW->>C: response
```

### Ingestion Flow

```
Upload file
  ↓ parse (PDF/DOCX/TXT/MD)
  ↓ chunk_text() → List[Chunk]
  ↓ embed_batch() → List[vector]
  ↓ pgvector INSERT (document + chunks)
  ↓ Elasticsearch INDEX (document text)
  ↓ document.status = "indexed"
```

### Key Components

| File | Responsibility |
|------|---------------|
| `main.py` | FastAPI app: `/upload`, `/query`, `/documents`, `/documents/{id}` |
| `retriever.py` | Parallel dense + BM25 fetch, RRF fusion, calls reranker |
| `pipeline.py` | Orchestrates parse → chunk → embed → store → retrieve → generate |
| `config.py` | Env-based config (DB DSN, ES URL, Infinity URLs, Ollama URL) |

### RRF Fusion Formula

```
score(doc, k=60) = Σ 1 / (k + rank_in_list)
```

Combined over the dense retrieval list and the BM25 list. Higher = better.

---

## 2. Agentic / Self-correcting RAG

### State Machine (LangGraph)

```mermaid
stateDiagram-v2
    [*] --> retrieve
    retrieve --> grade_documents
    grade_documents --> generate: all relevant
    grade_documents --> rewrite_query: some irrelevant
    rewrite_query --> retrieve: iteration < 3
    rewrite_query --> generate: iteration == 3
    generate --> [*]
    note right of grade_documents
        HITL pause point (hitl_enabled=true)
        POST /query/approve to resume
    end note
```

> **HITL pause:** When `HITL_ENABLED=true`, the graph uses `interrupt_before=["generate"]`. After grading, the workflow suspends and returns `status: "paused"` + `checkpoint_id` to the caller. Resume by calling `POST /query/approve` with the `thread_id`. Requires `CHECKPOINTING_ENABLED=true` (PostgreSQL `AsyncPostgresSaver`). `/query/approve` checks the checkpoint's existence via `aget_state()` (a real 404 if missing), sets `hitl_approved: true` on the persisted state via `update_state()` before resuming, and rebuilds the Langfuse callback handler from the checkpointed `trace_id` so the resumed `generate` span nests under the same trace as the paused run.

### Data Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant GW as API Gateway
    participant AR as agentic-rag
    participant HR as hybrid-rag (retriever)
    participant LLM as Ollama
    participant LF as Langfuse

    C->>GW: POST /v1/rag/agentic/query
    GW->>AR: forward request
    AR->>LF: start trace (low-level SDK) → trace_id
    Note over AR,LF: callback handler bound to trace_id passed into graph.ainvoke() config
    loop up to 3 iterations
        AR->>HR: retrieve(query, top_k)
        Note over AR,LF: manual span, rehydrated from trace_id
        AR->>LLM: grade_documents(query, docs) via llm_with_fallback
        Note over AR,LF: automatic generation span (bound callback handler)
        alt all relevant
            AR->>LLM: generate(query + context) via llm_with_fallback
            AR-->>AR: exit loop
        else some irrelevant
            AR->>LLM: rewrite_query(query) via llm_with_fallback
        end
    end
    AR->>LF: end trace
    AR->>GW: {answer, sources, metadata: {trace_url, trace_id, ...}}
    GW->>C: response
```

All three LLM-calling nodes (`grade_documents`, `rewrite_query`, `generate`) invoke a single module-level `llm_with_fallback = ChatOllama(model=LLM_MODEL).with_fallbacks([ChatOllama(model=FALLBACK_LLM_MODEL)])` — routing through a real LangChain `Runnable` (rather than raw `httpx`) is what makes the Redis cache (`set_llm_cache()`) and the fallback chain actually take effect, and what lets LangGraph pass per-node callbacks automatically.

### GraphState

```python
class GraphState(TypedDict):
    question: str
    documents: list[dict]
    generation: str
    iterations: int
    grade: str         # "relevant" | "irrelevant" (validated by GradeResult Pydantic model)
    query_rewrites: list[str]
    trace_url: str      # Langfuse trace URL — populated after ainvoke()
    trace_id: str        # Langfuse trace id (plain string, not the live SDK object —
                          # GraphState is checkpointed to PostgreSQL, and a live client
                          # handle would not survive that round-trip or a restart).
                          # Nodes rehydrate a trace handle via tracing.get_trace(trace_id).
    hitl_approved: bool   # True after POST /query/approve is called
    thread_id: str        # LangGraph thread_id (equals the UUID per request).
                           # NOTE: named thread_id, not checkpoint_id — LangGraph
                           # reserves "checkpoint_id" as an internal channel name
                           # and refuses to compile a graph whose state schema uses
                           # it. The public API's response field is still called
                           # checkpoint_id (unchanged contract); only this internal
                           # GraphState key differs.
```

### LangChain Patterns

| Pattern | Where | Effect |
|---------|-------|--------|
| **Structured Output** | `nodes.py: GradeResult` + `_grade_parser` (`PydanticOutputParser`) | `grade_documents` parses the LLM's raw text with `PydanticOutputParser`, retrying up to 2×; `grade` is always `"relevant"` or `"irrelevant"` — never freeform |
| **Multi-strategy parser** | `nodes.py: _parse_grade()` | Last-resort fallback only if `PydanticOutputParser` fails every retry: JSON extraction → keyword match → defaults to `"relevant"` |
| **LLM Fallback** | `nodes.py: llm_with_fallback` (`ChatOllama.with_fallbacks()`) | Used by all three LLM-calling nodes; on primary-model failure, LangChain transparently retries against `fallback_llm_model` |
| **Redis Cache** | `shared/cache/redis_cache.py` | Calls `set_llm_cache()` globally; effective because every node LLM call is a LangChain invocation |

### Key Components

| File | Responsibility |
|------|---------------|
| `state.py` | `GraphState` TypedDict — `trace_id` (serialisable), `hitl_approved`, `thread_id` fields |
| `nodes.py` | `retrieve`, `grade_documents` (Pydantic + fallback), `rewrite_query`, `generate` nodes; `llm_with_fallback` chain |
| `workflow.py` | Async `build_graph(pool)`: `StateGraph` + `AsyncPostgresSaver` checkpointer + HITL interrupt |
| `main.py` | FastAPI: `POST /query` (LangGraph + trace_url/trace_id), `POST /query/approve` (HITL resume), `POST /query/feedback` (score a trace), startup cache |
| `tracing.py` | Low-level Langfuse SDK wrapper: `start_trace`/`end_trace`, manual spans/generations, `get_trace(trace_id)` (rehydrate), `get_callback_handler(trace_id)` (trace-bound LangChain callback), `score_trace()` |
| `shared/cache/redis_cache.py` | `setup_llm_cache()`: configures global LangChain LLM cache |

---

## 3. Graph RAG

### Data Flow — Ingestion

```
Upload file
  ↓ parse → text
  ↓ chunk_text()
  ↓ embed_batch() → vectors → pgvector
  ↓ LLM extraction prompt → {entities, relationships}
  ↓ Neo4j upsert_entities() + upsert_relationships()
  ↓ document.status = "indexed"
```

### Data Flow — Query

```mermaid
sequenceDiagram
    participant C as Client
    participant GW as API Gateway
    participant GR as graph-rag
    participant InfE as Infinity-embeddings
    participant Neo as Neo4j
    participant PG as pgvector
    participant LLM as Ollama

    C->>GW: POST /v1/rag/graph/query
    GW->>GR: forward request
    GR->>InfE: embed(query)
    GR->>Neo: traverse(entities_in_query, depth=2)
    GR->>PG: similarity_search(embedding, filter_to_traversed_nodes)
    GR->>GR: merge graph context + vector context
    GR->>LLM: generate(query + combined_context)
    GR->>GW: {answer, sources, metadata.graph_paths}
    GW->>C: response
```

### Knowledge Graph Schema

```
(Document)-[:CONTAINS]->(Entity)
(Entity)-[:RELATED_TO {rel_type}]->(Entity)
```

Example:
```
(api-gateway)-[:CALLS]->(authentication-service)
(authentication-service)-[:STORES_IN]->(postgresql)
```

### Key Components

| File | Responsibility |
|------|---------------|
| `extractor.py` | LLM prompt → JSON `{entities, relationships}`; upserts to Neo4j |
| `graph.py` | Neo4j async client: `upsert_*`, `traverse(entity, depth)` |
| `pipeline.py` | Ingestion + query orchestration |
| `main.py` | FastAPI: `/upload`, `/query`, `/graph/{entity}` |

---

## Dependency Map

```
rag/hybrid-rag/
  → rag/shared/ingestion/     (parse, chunk)
  → rag/shared/embeddings/    (embed)
  → rag/shared/reranking/     (rerank)
  → Infinity-embeddings       (vectors)
  → Infinity-reranker         (cross-encoder scores)
  → pgvector                  (dense store)
  → Elasticsearch             (BM25 index)
  → Ollama                    (LLM generation)

rag/agentic-rag/
  → rag/shared/ingestion/     (parse, chunk)
  → rag/shared/embeddings/    (embed)
  → rag/shared/reranking/     (rerank)
  → rag/shared/observability/ (Langfuse/LangSmith callbacks — wired into graph.ainvoke())
  → rag/shared/cache/         (Redis LLM response cache — setup at startup)
  → hybrid-rag retriever      (via HTTP — retrieve node)
  → Ollama                    (grade, rewrite, generate — with fallback model)
  → PostgreSQL                (LangGraph AsyncPostgresSaver checkpoints)
  → Redis                     (LangChain global LLM cache)
  → Langfuse / LangSmith      (trace storage; trace_url in response metadata)

rag/graph-rag/
  → rag/shared/ingestion/     (parse, chunk)
  → rag/shared/embeddings/    (embed)
  → Infinity-embeddings       (vectors)
  → pgvector                  (dense store)
  → Neo4j                     (knowledge graph)
  → Ollama                    (extraction + generation)
```

---

## Vector Store Abstraction (Qdrant Migration Path)

The `packages/shared-db/src/shared_db/pgvector.py` layer isolates all vector store calls.
Swapping pgvector for Qdrant requires changing only:

1. `packages/shared-db/src/shared_db/pgvector.py` → implement Qdrant client
2. Helm chart values (add Qdrant chart, remove pgvector vector column)

No RAG pipeline logic files need to change.
