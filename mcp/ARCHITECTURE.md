# MCP Subsystem Architecture

## Overview

The MCP subsystem follows the same monorepo patterns as the RAG subsystem: three independent FastAPI services deployed via Helm, accessed through the API Gateway, and sharing a PostgreSQL-backed tool catalog.

---

## Components

| Service | Port | Role |
|---------|------|------|
| **mcp-hub** | 8010 | Central routing: looks up tool in PostgreSQL, forwards call, logs result |
| **mcp-server** | 8011 | Runs built-in local tools: RAG queries, LLM chat, text embeddings |
| **mcp-client** | 8012 | Proxies calls to any registered external HTTP MCP server |

---

## Architecture Diagram

```
Client / Agent
      │
      ▼
API Gateway  :30880
      │  /v1/mcp/*
      ▼
   mcp-hub  :8010
   ┌─────────────────────────────────────────────────┐
   │  PostgreSQL                                      │
   │  ├─ mcp_tools       (catalog + routing info)    │
   │  └─ mcp_audit_log   (every call logged)         │
   └─────────────────────────────────────────────────┘
      │
      ├─ server_type=local ──► mcp-server  :8011
      │                              │
      │                              ├─► hybrid-rag  :8001
      │                              ├─► agentic-rag :8002
      │                              ├─► graph-rag   :8003
      │                              ├─► Ollama LLM
      │                              └─► Infinity Embeddings
      │
      └─ server_type=remote ──► mcp-client :8012
                                      │
                                      └─► External MCP Server (any URL)
```

---

## Data Flows

### Local Tool Call (e.g. RAG pipeline)

```
sequenceDiagram
    Agent → API Gateway: POST /v1/mcp/tools/rag_hybrid_query/call
    API Gateway → mcp-hub: forward
    mcp-hub → PostgreSQL: SELECT * FROM mcp_tools WHERE name='rag_hybrid_query'
    mcp-hub → mcp-server: POST /tools/rag_hybrid_query/call
    mcp-server → hybrid-rag: POST /query {query, top_k}
    hybrid-rag → mcp-server: {answer, sources, metadata}
    mcp-server → mcp-hub: ToolCallResult
    mcp-hub → PostgreSQL: INSERT INTO mcp_audit_log
    mcp-hub → Langfuse: trace "mcp.rag_hybrid_query" (async, batched)
    mcp-hub → API Gateway: ToolCallResult
    API Gateway → Agent: response
```

### Remote Tool Call (e.g. Confluence search)

```
sequenceDiagram
    Agent → API Gateway: POST /v1/mcp/tools/confluence_search/call
    API Gateway → mcp-hub: forward
    mcp-hub → PostgreSQL: SELECT * FROM mcp_tools WHERE name='confluence_search'
    Note over mcp-hub: server_type=remote, server_url=http://mcp-confluence:9100
    mcp-hub → mcp-client: POST /call {url, tool_name, arguments}
    mcp-client → External MCP: POST /tools/confluence_search/call
    External MCP → mcp-client: result
    mcp-client → mcp-hub: ToolCallResult
    mcp-hub → PostgreSQL: INSERT INTO mcp_audit_log
    mcp-hub → Langfuse: trace "mcp.confluence_search" (async, batched)
    mcp-hub → API Gateway: ToolCallResult
    API Gateway → Agent: response
```

---

## Routing Logic

```
POST /tools/{name}/call arrives at mcp-hub
    │
    ├─ lookup: SELECT FROM mcp_tools WHERE name = {name}
    │
    ├─ not found?  → 404 {"detail": "Tool not found"}
    ├─ enabled=false? → 403 {"detail": "Tool is disabled"}
    │
    ├─ server_type = 'local'
    │     └─ POST mcp-server/tools/{name}/call
    │           payload: {"tool_name": name, "arguments": {...}}
    │
    └─ server_type = 'remote'
          └─ POST mcp-client/call
                payload: {"url": tool.server_url, "tool_name": name, "arguments": {...}}
    │
    └─ INSERT INTO mcp_audit_log (tool_name, input, output, latency_ms, success, error)
    └─ observability.trace_tool_call(...) → Langfuse trace "mcp.{name}" (best-effort, never blocks the response)
```

---

## Wire Protocol

All communication is JSON-over-HTTP REST with `application/json`.

### ToolCallRequest (agent → hub)

```json
{
  "tool_name": "rag_hybrid_query",
  "arguments": {
    "query": "What is pgvector?",
    "top_k": 5
  }
}
```

### ToolCallResult (hub → agent)

**Success:**
```json
{
  "tool_name": "rag_hybrid_query",
  "result": {
    "answer": "pgvector is a PostgreSQL extension...",
    "sources": [
      {"content": "...", "document_name": "doc.txt", "score": 0.016}
    ],
    "metadata": {"dense_hits": 5, "bm25_hits": 5, "reranked": false, "latency_ms": 312}
  },
  "latency_ms": 318,
  "success": true,
  "error": null
}
```

**Failure (external server unreachable):**
```json
{
  "tool_name": "confluence_search",
  "result": null,
  "latency_ms": 5001,
  "success": false,
  "error": "Remote MCP server unavailable"
}
```

---

## Database Schema

### mcp_tools

Persists the tool catalog. Local tools are auto-seeded by `mcp-server` on startup. Remote tools are registered via `POST /tools`.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | Primary key |
| `name` | TEXT | Unique tool identifier |
| `description` | TEXT | Shown to agents during tool discovery |
| `server_type` | TEXT | `local` or `remote` |
| `server_url` | TEXT | URL for remote tools; null for local |
| `input_schema` | JSONB | JSON Schema describing accepted arguments |
| `output_schema` | JSONB | JSON Schema describing returned result |
| `enabled` | BOOLEAN | `false` → 403 on call; allows disabling without deleting |
| `created_at` | TIMESTAMPTZ | Auto-set on insert |

### mcp_audit_log

One row per tool call. Never modified after insert.

| Column | Type | Notes |
|--------|------|-------|
| `id` | BIGSERIAL | Auto-increment |
| `tool_name` | TEXT | Which tool was called |
| `input` | JSONB | Arguments passed |
| `output` | JSONB | Result returned (null on failure) |
| `latency_ms` | INT | End-to-end call duration |
| `success` | BOOLEAN | False if any exception was raised |
| `error` | TEXT | Error message if `success=false`; null otherwise |
| `called_at` | TIMESTAMPTZ | Indexed; used for `ORDER BY called_at DESC` |

Indexes: `idx_mcp_audit_log_called_at`, `idx_mcp_audit_log_tool_name`

---

## Tool Registration Flow

### Built-in Local Tools

`mcp-server` seeds these automatically at startup via its `lifespan` function:

```
mcp-server starts
  └─ for each tool in TOOL_DEFINITIONS:
        POST http://mcp-hub:8010/tools
        409 (already registered) → skip silently
        201 → tool is active
```

Built-in tools: `rag_hybrid_query`, `rag_agentic_query`, `rag_graph_query`, `llm_chat`, `embed_text`

### External Tool Registration

```bash
# Register once — hub routes all future calls automatically
POST /tools
{
  "name": "confluence_search",
  "server_type": "remote",
  "server_url": "http://mcp-confluence:9100",
  "input_schema": {...},
  "output_schema": {}
}
```

---

## mcp-client: External Server Connection Pool

`mcp-client` maintains a per-URL `httpx.AsyncClient` pool in memory:

```
first call to url X  → create AsyncClient(base_url=X, timeout=60s) → cache it
subsequent calls     → reuse cached client (no reconnect overhead)
shutdown             → aclose() all cached clients
```

This means: registering many external servers has no cost until they are actually called.

---

## Shared Code (`mcp/shared/`)

| Module | Purpose |
|--------|---------|
| `schemas.py` | Pydantic types: `ToolDefinition`, `ToolCallRequest`, `ToolCallResult` |
| `registry_client.py` | Async httpx wrapper for hub calls (`register_tool`, `list_tools`) |
| `observability.py` | Langfuse trace wrapper for tool calls (mirrors `rag/agentic-rag/src/tracing.py`); `get_client()` caches a single Langfuse client, `trace_tool_call()` is called from `mcp-hub`'s `router.py::call_tool()`, `flush()` runs once on shutdown |
