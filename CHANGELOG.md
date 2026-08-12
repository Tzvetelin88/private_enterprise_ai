# Changelog

## [Unreleased]

### 2026-08-12

#### Added
- **Redis LLM response cache** (agentic-rag) — identical LLM prompts served from Redis instead of re-invoking the model.
- **LangChain fallback chain** (agentic-rag) — `ChatOllama` transparently retries against a fallback model if the primary is unreachable.
- **Structured output parsing** (agentic-rag) — `grade_documents` output validated via `PydanticOutputParser`, guaranteed to be `"relevant"` or `"irrelevant"`.
- **Langfuse visual tracing** (agentic-rag) — one trace per query with linked per-node spans; `trace_url` and `trace_id` in the response.
- **`POST /query/feedback`** (agentic-rag) — attach a numeric score + comment to a trace by `trace_id`.
- **LangGraph Human-in-the-Loop** (agentic-rag) — workflow pauses before `generate`; `POST /query/approve` resumes it, with real 404 handling and an `hitl_approved` audit flag.
- **`metadata.trace_id`** in `POST /query` and `POST /query/approve` responses.
- **MCP tool-call tracing** — every `mcp-hub` tool call is traced to Langfuse.
- **`scripts/health-check.sh`** (`make health-check`) — checks kind cluster/node health, Kubernetes workloads, docker-compose stacks, service HTTP endpoints, and Redis/Postgres data-plane sanity.
- **pgvector migration** (`packages/shared-db/.../migrations/003_add_pgvector_embedding.sql`) — enables `pgvector` and adds the `chunks.embedding` column + HNSW index; run automatically by `install-stage4.sh`.
- **Infinity embeddings reachable from docker-compose** — pinned `NodePort:30797` in the Helm chart, mapped in `kind-config{,-mac}.yaml`.
- **Qwen3.5:4B as the default LLM** (agentic-rag, hybrid-rag, graph-rag, mcp-server), served via Ollama alongside the existing `llama3.2:3b` (now the fallback model in agentic-rag). Switch models by setting `LLM_MODEL` (or `OLLAMA_MODEL` for the local Ollama server) — no code changes needed.

#### Known issues
- **LangGraph PostgreSQL checkpointing does not persist.** `AsyncPostgresSaver` fails to initialize; degrades gracefully to running without persistence. HITL pause/resume works within a single running process only — a mid-pause restart loses the paused state.
