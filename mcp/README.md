# MCP Subsystem

Model Context Protocol (MCP) implementation for the Private Enterprise AI platform.

Exposes the platform's AI capabilities (RAG pipelines, LLM, embeddings) as discoverable MCP tools, and provides a proxy to register and call external HTTP MCP servers (Confluence, GitHub, filesystem, etc.).

---

## Core Idea

Any agent or client calls a **single hub endpoint** (`mcp-hub :8010`). The hub looks up the tool in its PostgreSQL catalog, routes the call to the right backend, and logs the result. The caller never needs to know which backend serves the tool.

```
Agent
  └─ POST /tools/rag_hybrid_query/call
        └─ mcp-hub (catalog + routing)
              ├─ server_type=local  → mcp-server → hybrid-rag
              └─ server_type=remote → mcp-client → external MCP server
```

---

## Services

| Service | Port | Role |
|---------|------|------|
| **mcp-hub** | 8010 | Tool catalog (PostgreSQL), routing, audit log |
| **mcp-server** | 8011 | Exposes local tools: RAG, LLM, embeddings |
| **mcp-client** | 8012 | Proxies calls to registered external MCP servers |

---

## Local Dev Setup

```bash
# Start all three MCP services
docker compose -f mcp/docker-compose.yml up -d

# Verify health
curl http://localhost:8010/health   # {"status":"healthy","service":"mcp-hub"}
curl http://localhost:8011/health   # {"status":"healthy","service":"mcp-server"}
curl http://localhost:8012/health   # {"status":"healthy","service":"mcp-client"}
```

The `mcp_tools` and `mcp_audit_log` tables must exist in PostgreSQL. Apply if not already done:

```bash
kubectl exec -it postgresql-0 -- env PGPASSWORD=changeme-postgres-admin \
  psql -U postgres -d private_ai -f - < packages/shared-db/src/shared_db/migrations/002_create_mcp_tables.sql
```

### Deploy to Kubernetes

```bash
./scripts/install-mcp.sh
```

---

## Built-in Tools

These are automatically registered in the hub when `mcp-server` starts:

| Tool | Description | Required Input |
|------|-------------|----------------|
| `rag_hybrid_query` | Hybrid RAG (dense + BM25) over indexed docs | `query` (string), `top_k` (int, default 5) |
| `rag_agentic_query` | Agentic self-correcting RAG with grading loop | `query` (string), `top_k` (int, default 5) |
| `rag_graph_query` | Graph RAG with Neo4j entity traversal | `query` (string), `top_k` (int, default 5) |
| `llm_chat` | Direct LLM chat completion | `message` (string) or `messages` (array) |
| `embed_text` | Generate a text embedding vector | `text` (string) |

---

## API Reference

All examples use `mcp-hub` at port 8010 directly.
Via API Gateway prefix everything with `http://localhost:30880/v1/mcp`.

### List All Tools

```bash
curl http://localhost:8010/tools
```

**Response:**
```json
[
  {
    "id": "a1b2c3d4-...",
    "name": "rag_hybrid_query",
    "description": "Hybrid (dense + BM25) RAG pipeline query",
    "server_type": "local",
    "server_url": null,
    "input_schema": {
      "type": "object",
      "properties": {
        "query": {"type": "string"},
        "top_k": {"type": "integer", "default": 5}
      },
      "required": ["query"]
    },
    "output_schema": {"type": "object"},
    "enabled": true,
    "created_at": "2026-07-27T09:00:00+00:00"
  }
]
```

---

### Call a Local RAG Tool

```bash
curl -X POST http://localhost:8010/tools/rag_hybrid_query/call \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "rag_hybrid_query", "arguments": {"query": "What is pgvector?", "top_k": 3}}'
```

**Response:**
```json
{
  "tool_name": "rag_hybrid_query",
  "result": {
    "answer": "pgvector is a PostgreSQL extension for storing and querying vector embeddings...",
    "sources": [
      {
        "content": "pgvector is a PostgreSQL extension...",
        "document_id": "a8bb1109-...",
        "document_name": "test-doc.txt",
        "score": 0.016
      }
    ],
    "metadata": {"dense_hits": 3, "bm25_hits": 3, "reranked": false, "latency_ms": 312}
  },
  "latency_ms": 318,
  "success": true,
  "error": null
}
```

---

### Call LLM Chat Tool

```bash
curl -X POST http://localhost:8010/tools/llm_chat/call \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "llm_chat", "arguments": {"message": "Explain vector databases in one sentence."}}'
```

**Response:**
```json
{
  "tool_name": "llm_chat",
  "result": {
    "answer": "Vector databases store high-dimensional embeddings and enable fast similarity search using approximate nearest-neighbor algorithms."
  },
  "latency_ms": 1850,
  "success": true,
  "error": null
}
```

---

### Call Embeddings Tool

```bash
curl -X POST http://localhost:8010/tools/embed_text/call \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "embed_text", "arguments": {"text": "Hello world"}}'
```

**Response:**
```json
{
  "tool_name": "embed_text",
  "result": {
    "embedding": [0.023, -0.147, 0.389, "...384 values total..."],
    "model": "BAAI/bge-small-en-v1.5"
  },
  "latency_ms": 45,
  "success": true,
  "error": null
}
```

---

### Register an External MCP Server

External servers expose their own tools over HTTP. Register them once; the hub routes all future calls automatically.

```bash
curl -X POST http://localhost:8010/tools \
  -H "Content-Type: application/json" \
  -d '{
    "name": "confluence_search",
    "description": "Search Confluence pages",
    "server_type": "remote",
    "server_url": "http://mcp-confluence:9100",
    "input_schema": {
      "type": "object",
      "properties": {"query": {"type": "string"}},
      "required": ["query"]
    },
    "output_schema": {"type": "object"}
  }'
```

**Response `201 Created`:**
```json
{
  "id": "e4f5a6b7-...",
  "name": "confluence_search",
  "server_type": "remote",
  "server_url": "http://mcp-confluence:9100",
  "enabled": true,
  "created_at": "2026-07-27T10:30:00+00:00"
}
```

---

### Call an External Tool

After registering, the hub routes to mcp-client → external server:

```bash
curl -X POST http://localhost:8010/tools/confluence_search/call \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "confluence_search", "arguments": {"query": "pgvector setup guide"}}'
```

**Response (proxied from external server):**
```json
{
  "tool_name": "confluence_search",
  "result": {
    "pages": [
      {"title": "pgvector Setup Guide", "url": "https://...", "excerpt": "..."}
    ]
  },
  "latency_ms": 230,
  "success": true,
  "error": null
}
```

---

### Delete a Tool

```bash
curl -X DELETE http://localhost:8010/tools/confluence_search
```

**Response:** `{"deleted": "confluence_search"}`

---

### View Audit Log

Every tool call is automatically logged. Retrieve the 100 most recent:

```bash
curl http://localhost:8010/audit
```

**Response:**
```json
[
  {
    "id": 7,
    "tool_name": "rag_hybrid_query",
    "input": {"query": "What is pgvector?", "top_k": 3},
    "output": {"answer": "pgvector is...", "sources": [...]},
    "latency_ms": 318,
    "success": true,
    "error": null,
    "called_at": "2026-07-27T10:15:30+00:00"
  }
]
```

Limit the number of results: `GET /audit?limit=10`

---

## Observability — Langfuse Tracing

Every `POST /tools/{name}/call` on `mcp-hub` also emits a Langfuse trace named `mcp.<tool_name>` (in addition to the PostgreSQL audit log above), with the call's input, output, latency, and success/error captured as a span. This mirrors the RAG stack's tracing (`rag/agentic-rag`) and reuses the same Langfuse instance — `mcp-hub` joins `rag-net` specifically to reach it.

Configure via env vars on `mcp-hub` (see `mcp/docker-compose.yml`):

| Var | Default | Purpose |
|-----|---------|---------|
| `TRACING_BACKEND` | `langfuse` | Set to `none` to disable |
| `LANGFUSE_HOST` | `http://langfuse:3000` | Langfuse instance (shared with the RAG stack) |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | *(empty — must be set)* | From Langfuse UI → Settings → API Keys |

The Langfuse client is created once and cached (`mcp/shared/observability.py::get_client()`), not per call — events are batched and sent in a background thread, and flushed once on service shutdown, so tracing adds no latency to individual tool calls. If Langfuse is unreachable or keys aren't configured, tracing silently no-ops and tool calls are unaffected.

---

## Error Responses

| Scenario | HTTP Status | Body |
|----------|-------------|------|
| Unknown tool name | `404` | `{"detail": "Tool not found"}` |
| Tool `enabled=false` | `403` | `{"detail": "Tool is disabled"}` |
| External server unreachable | `503` | `{"detail": "Remote MCP server unavailable"}` |
| Duplicate tool registration | `409` | `{"detail": "Tool already registered"}` |
| Missing required argument | `422` | Pydantic validation error |

---

## Where to Add New Tools

**External tool (Confluence, GitHub, YouTube API, etc.):**
1. Deploy (or find) a small HTTP MCP server wrapping that API
2. Register it via `POST /tools` (no code changes in this repo)
3. Call it like any other tool via `POST /tools/{name}/call`

**Platform-native tool (uses your LLM, RAG, or embeddings):**
1. Add logic to `mcp/mcp-server/src/tools/`
2. Register the tool definition in `mcp/mcp-server/src/router.py` `TOOL_DEFINITIONS`
3. Add an `elif name == "your_tool":` branch in `call_tool()`

---

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for routing logic, sequence diagrams, and database schema.
