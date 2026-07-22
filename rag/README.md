# RAG Pipelines — User Stories, Requirements & Test Cases

This directory contains three production-grade RAG (Retrieval-Augmented Generation) pipelines.
Each pipeline is an independently deployable FastAPI service accessible through the API Gateway.

---

## Quick Reference — Which Pipeline to Use?

| Pipeline | Best For | API Path |
|----------|----------|----------|
| **Hybrid RAG** | Documentation search, enterprise knowledge bases, support Q&A | `POST /v1/rag/hybrid/query` |
| **Agentic RAG** | Complex multi-hop questions, ambiguous queries that need retrying | `POST /v1/rag/agentic/query` |
| **Graph RAG** | Relationship questions across documents, dependency analysis | `POST /v1/rag/graph/query` |

---

## 1. Hybrid Search RAG

### When to Use

- You have a large corpus of technical documentation, wikis, or FAQs
- Queries mix exact keyword terms (product names, error codes) with semantic intent
- You need fast, predictable retrieval with reranking quality
- Latency matters — this is the fastest of the three pipelines

### How to Trigger

**Upload a document:**
```bash
curl -X POST http://localhost:30880/v1/rag/hybrid/upload \
  -F "file=@my-doc.pdf"
```

**Query:**
```bash
curl -X POST http://localhost:30880/v1/rag/hybrid/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How do I configure the connection pool?",
    "top_k": 5
  }'
```

**Response shape:**
```json
{
  "answer": "...",
  "sources": [
    {"content": "...", "document_id": "...", "score": 0.92}
  ],
  "metadata": {
    "dense_hits": 5,
    "bm25_hits": 5,
    "reranked": true,
    "latency_ms": 120
  }
}
```

### Example Use Cases

- "What are the default timeout settings for the API Gateway?"
- "Find all mentions of SSL certificate configuration"
- "Which endpoints support streaming?"

### Acceptance Test Cases

| # | Scenario | Expected Outcome |
|---|----------|-----------------|
| 1 | Upload PDF, then query it | `status: indexed`; answer contains doc content |
| 2 | Upload 0-byte file | `422 Unprocessable Entity` |
| 3 | Upload unsupported format (.exe) | `415 Unsupported Media Type` |
| 4 | Query empty collection | `sources: []`; answer contains "no information found" |
| 5 | Reranker pod down | Falls back to RRF-only order, still returns 200 |
| 6 | Reranked order differs from dense-only | Verifies reranker is active |

---

## 2. Agentic / Self-correcting RAG

### When to Use

- Query requires synthesizing information from multiple documents (multi-hop)
- The question is ambiguous and may need to be rewritten before retrieval
- You need confidence that the retrieved documents are actually relevant before generating
- You are willing to trade extra latency for higher answer quality

### How to Trigger

**Upload:**
```bash
curl -X POST http://localhost:30880/v1/rag/agentic/upload \
  -F "file=@my-doc.md"
```

**Query:**
```bash
curl -X POST http://localhost:30880/v1/rag/agentic/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the relationship between the auth service and the token expiry setting?",
    "top_k": 5
  }'
```

**Response shape:**
```json
{
  "answer": "...",
  "sources": [...],
  "metadata": {
    "iterations": 2,
    "final_grade": "relevant",
    "query_rewrites": ["..."],
    "trace_url": "http://localhost:3000/trace/..."
  }
}
```

### Example Use Cases

- "How does service A interact with service B when the database is unavailable?"
- "What changed in the authentication flow between version 1 and version 2?"
- "Explain the full lifecycle of a request from API Gateway to the LLM"

### Acceptance Test Cases

| # | Scenario | Expected Outcome |
|---|----------|-----------------|
| 1 | Clear, single-hop query | `metadata.iterations == 1` |
| 2 | Ambiguous query | `metadata.iterations >= 2`, query rewrite logged |
| 3 | Max iterations reached | Returns best available answer, `metadata.iterations == 3` |
| 4 | Langfuse trace created | `metadata.trace_url` is non-null and accessible |
| 5 | All retrieved docs graded irrelevant | Rewrites query and retries; does not return empty answer |

---

## 3. Graph RAG

### When to Use

- Questions span relationships across many documents ("which X is connected to Y?")
- You need to map dependencies, call graphs, or entity relationships
- Incident correlation: linking failures to upstream/downstream services
- Document corpus has rich entity structure (microservices, products, teams, etc.)

### How to Trigger

**Upload (triggers entity/relationship extraction):**
```bash
curl -X POST http://localhost:30880/v1/rag/graph/upload \
  -F "file=@architecture.md"
```

**Query:**
```bash
curl -X POST http://localhost:30880/v1/rag/graph/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Which services depend on the authentication service?",
    "top_k": 5
  }'
```

**Inspect entity subgraph (for debugging/visualization):**
```bash
curl http://localhost:30880/v1/rag/graph/graph/authentication-service
```

**Response shape:**
```json
{
  "answer": "...",
  "sources": [...],
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

### Example Use Cases

- "Which services depend on the payment gateway?"
- "What incidents are related to the last deployment of the recommendation engine?"
- "Who are the customers affected by failures in the billing service?"

### Acceptance Test Cases

| # | Scenario | Expected Outcome |
|---|----------|-----------------|
| 1 | Upload two related docs | Both docs indexed; entities extracted and stored in Neo4j |
| 2 | Relationship query | `metadata.graph_paths` is non-empty |
| 3 | Entity subgraph endpoint | Returns JSON with nodes and edges |
| 4 | Upload doc with no detectable entities | Indexed successfully; vector retrieval still works |
| 5 | Query with no graph path found | Falls back to vector similarity; still returns answer |

---

## Common Edge Cases (All Pipelines)

| Scenario | Expected Behaviour |
|----------|-------------------|
| `GET /documents` | Returns list of indexed documents with status |
| `DELETE /documents/{id}` | Removes document and all associated chunks |
| Query while indexing is in progress | Returns `202 Accepted` or queues query |
| Concurrent uploads of same filename | Both are accepted with distinct UUIDs |

---

## Local Dev Setup

Start all RAG dependencies (Elasticsearch, Neo4j, Langfuse) with Docker Compose:

```bash
docker compose -f rag/docker-compose.yml up -d
```

| Service | URL | Credentials |
|---------|-----|-------------|
| Elasticsearch | http://localhost:9200 | — |
| Neo4j Browser | http://localhost:7474 | neo4j / changeme-neo4j |
| Langfuse | http://localhost:3000 | Create account on first visit |
