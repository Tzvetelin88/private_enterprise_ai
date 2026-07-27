#!/usr/bin/env bash
# ============================================================================
# demo-langfuse-traces.sh
#
# Uploads three rich documents into every RAG pipeline, then fires a curated
# set of questions through:
#   - Graph RAG         (port 8003) — entity extraction + Neo4j traversal
#   - Agentic RAG       (port 8002) — LangGraph self-correcting loop → Langfuse
#   - MCP Hub           (port 8010) — unified tool gateway + audit log
#
# After running this script open http://localhost:3000 → Traces to see the
# full Langfuse telemetry for every agentic-rag call.
# ============================================================================

set -euo pipefail

GRAPH_RAG="http://localhost:8003"
AGENTIC_RAG="http://localhost:8002"
MCP_HUB="http://localhost:8010"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCS_DIR="$SCRIPT_DIR/demo-docs"

# Colours
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
RESET='\033[0m'

# ── helpers ──────────────────────────────────────────────────────────────────

banner() { echo -e "\n${BOLD}${CYAN}══════════════════════════════════════════${RESET}"; \
           echo -e "${BOLD}${CYAN}  $1${RESET}"; \
           echo -e "${BOLD}${CYAN}══════════════════════════════════════════${RESET}\n"; }

step()   { echo -e "${YELLOW}▶ $1${RESET}"; }

ok()     { echo -e "${GREEN}✓ $1${RESET}"; }

query_agentic() {
    local label="$1"
    local query="$2"
    local top_k="${3:-5}"

    echo -e "\n${BOLD}[AGENTIC-RAG] $label${RESET}"
    echo -e "  Query: ${CYAN}\"$query\"${RESET}"

    local result
    result=$(curl -sf -X POST "$AGENTIC_RAG/query" \
        -H "Content-Type: application/json" \
        -d "{\"query\": $(echo "$query" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read().strip()))'), \"top_k\": $top_k}" \
        2>/dev/null || echo '{"error":"request failed"}')

    local answer iterations grade rewrites
    answer=$(echo "$result"    | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("answer","(no answer)")[:300])' 2>/dev/null || echo "(parse error)")
    iterations=$(echo "$result" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("metadata",{}).get("iterations","-"))' 2>/dev/null || echo "?")
    grade=$(echo "$result"     | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("metadata",{}).get("final_grade","-"))' 2>/dev/null || echo "?")
    rewrites=$(echo "$result"  | python3 -c 'import sys,json; d=json.load(sys.stdin); rw=d.get("metadata",{}).get("query_rewrites",[]); print(len(rw))' 2>/dev/null || echo "0")

    echo "  Answer: $answer"
    echo "  Iterations: $iterations | Grade: $grade | Rewrites: $rewrites"
}

query_graph() {
    local label="$1"
    local query="$2"

    echo -e "\n${BOLD}[GRAPH-RAG] $label${RESET}"
    echo -e "  Query: ${CYAN}\"$query\"${RESET}"

    local result
    result=$(curl -sf -X POST "$GRAPH_RAG/query" \
        -H "Content-Type: application/json" \
        -d "{\"query\": $(echo "$query" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read().strip()))'), \"top_k\": 5}" \
        2>/dev/null || echo '{"error":"request failed"}')

    local answer
    answer=$(echo "$result" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("answer","(no answer)")[:250])' 2>/dev/null || echo "(parse error)")
    echo "  Answer: $answer"
}

query_mcp() {
    local tool="$1"
    local label="$2"
    local query="$3"

    echo -e "\n${BOLD}[MCP → $tool] $label${RESET}"
    echo -e "  Query: ${CYAN}\"$query\"${RESET}"

    local result
    result=$(curl -sf -X POST "$MCP_HUB/tools/$tool/call" \
        -H "Content-Type: application/json" \
        -d "{\"tool_name\": \"$tool\", \"arguments\": {\"query\": $(echo "$query" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read().strip()))'), \"top_k\": 5}}" \
        2>/dev/null || echo '{"error":"request failed"}')

    local success latency
    success=$(echo "$result" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("success","?"))' 2>/dev/null || echo "?")
    latency=$(echo "$result" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("latency_ms","?"))' 2>/dev/null || echo "?")
    echo "  Success: $success | Latency: ${latency}ms"
}

# ── check services ────────────────────────────────────────────────────────────

banner "0. Preflight — checking services"

for svc_url in "$GRAPH_RAG/health" "$AGENTIC_RAG/health" "$MCP_HUB/health"; do
    if curl -sf "$svc_url" > /dev/null 2>&1; then
        ok "$svc_url"
    else
        echo -e "  ⚠️  ${YELLOW}$svc_url not reachable — some steps may fail${RESET}"
    fi
done

# ── upload documents ──────────────────────────────────────────────────────────

banner "1. Uploading documents"

DOCS=(
    "acme-platform-architecture.md"
    "vector-search-internals.md"
    "llm-agents-patterns.md"
)

for doc in "${DOCS[@]}"; do
    filepath="$DOCS_DIR/$doc"
    if [[ ! -f "$filepath" ]]; then
        echo "  ⚠️  $doc not found at $filepath — skipping"
        continue
    fi

    step "Uploading $doc to Graph-RAG (port 8003)…"
    result=$(curl -sf -X POST "$GRAPH_RAG/upload" \
        -F "file=@$filepath" 2>/dev/null || echo '{"error":"upload failed"}')
    doc_id=$(echo "$result" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("document_id","?"))' 2>/dev/null || echo "?")
    ok "  graph-rag document_id=$doc_id"

    step "Uploading $doc to Agentic-RAG (port 8002)…"
    result=$(curl -sf -X POST "$AGENTIC_RAG/upload" \
        -F "file=@$filepath" 2>/dev/null || echo '{"error":"upload failed"}')
    doc_id=$(echo "$result" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("document_id","?"))' 2>/dev/null || echo "?")
    ok "  agentic-rag document_id=$doc_id"

    sleep 1   # let indexing settle
done

# ── list indexed documents ────────────────────────────────────────────────────

banner "2. Listing indexed documents"

step "Graph-RAG document list:"
curl -sf "$GRAPH_RAG/documents" 2>/dev/null \
    | python3 -c 'import sys,json; docs=json.load(sys.stdin); [print(f"  [{d.get(\"document_id\",\"?\")[:8]}…] {d.get(\"document_name\",\"?\")}") for d in docs]' 2>/dev/null \
    || echo "  (could not fetch)"

# ── GRAPH-RAG entity queries ──────────────────────────────────────────────────

banner "3. Graph-RAG — entity extraction queries"

query_graph "Who leads the ML Platform team?" \
    "Who is responsible for the ML Platform team and feature store?"

query_graph "HNSW vs IVF-PQ trade-offs" \
    "What are the differences between HNSW and IVF-PQ approximate nearest neighbour algorithms?"

query_graph "LangGraph and self-correcting RAG" \
    "How does LangGraph enable self-correcting retrieval augmented generation pipelines?"

query_graph "Compliance and security" \
    "What compliance certifications and security measures does ACME Corp use?"

# inspect a few entity graphs
step "Fetching entity subgraph for 'Kafka'…"
curl -sf "$GRAPH_RAG/graph/Kafka" 2>/dev/null \
    | python3 -c 'import sys,json; g=json.load(sys.stdin); print(f"  nodes={len(g.get(\"nodes\",[]))} edges={len(g.get(\"relationships\",g.get(\"edges\",[])))}")' 2>/dev/null \
    || echo "  (entity not found or endpoint unavailable)"

step "Fetching entity subgraph for 'LangGraph'…"
curl -sf "$GRAPH_RAG/graph/LangGraph" 2>/dev/null \
    | python3 -c 'import sys,json; g=json.load(sys.stdin); print(f"  nodes={len(g.get(\"nodes\",[]))} edges={len(g.get(\"relationships\",g.get(\"edges\",[])))}")' 2>/dev/null \
    || echo "  (entity not found or endpoint unavailable)"

# ── AGENTIC-RAG queries (these create Langfuse traces!) ──────────────────────

banner "4. Agentic-RAG — self-correcting loop queries  ←  watch Langfuse traces!"
echo -e "  ${CYAN}Open http://localhost:3000 → Traces after this section${RESET}\n"

# Straightforward fact retrieval — should resolve in 1 iteration
query_agentic "Straightforward fact" \
    "What is the fraud scoring latency SLA at ACME Corp?" 5

sleep 2

# Relationship query — may require a rewrite
query_agentic "Relationship query" \
    "How does Kafka connect to the Snowflake data warehouse at ACME?" 5

sleep 2

# Comparative / analytical — often triggers rewrite loop
query_agentic "Comparative analysis" \
    "Compare Pinecone and Qdrant as vector databases — what are the key differences?" 7

sleep 2

# Cross-document reasoning: agents doc + vector search doc
query_agentic "Cross-document concept" \
    "Which memory storage type is best suited for an LLM agent that needs semantic search over past episodes?" 7

sleep 2

# People & roles (tests entity recall)
query_agentic "People and roles" \
    "Which engineers at ACME Corp work on model training and who approves models for production?" 5

sleep 2

# Potential rewrite trigger: vague query about safety
query_agentic "Vague safety query (likely triggers rewrite)" \
    "What are the dangers when AI acts on its own?" 5

sleep 2

# Technical deep-dive
query_agentic "Technical deep-dive" \
    "Explain Matryoshka Representation Learning and how it reduces embedding storage costs" 5

sleep 2

# Out-of-corpus question — agent should gracefully say it doesn't know
query_agentic "Out-of-corpus question" \
    "What is the quarterly revenue of ACME Corp for Q3 2024?" 5

# ── MCP hub — all three pipelines ────────────────────────────────────────────

banner "5. MCP Hub — routing queries to all three RAG pipelines"

step "Listing available MCP tools…"
curl -sf "$MCP_HUB/tools" 2>/dev/null \
    | python3 -c 'import sys,json; tools=json.load(sys.stdin); [print(f"  • {t.get(\"name\",\"?\")} — {t.get(\"description\",\"\")[:70]}") for t in (tools if isinstance(tools,list) else tools.get("tools",[]))]' 2>/dev/null \
    || echo "  (could not list tools)"

query_mcp "rag_hybrid_query" "Hybrid RAG: HNSW parameters" \
    "What are the recommended HNSW index parameters for a production pgvector setup?"

sleep 1

query_mcp "rag_graph_query" "Graph RAG: incident history" \
    "What production incidents has ACME Corp experienced and who resolved them?"

sleep 1

query_mcp "rag_agentic_query" "Agentic RAG via MCP: ReAct vs Tree of Thoughts" \
    "When should you choose Tree of Thoughts over the ReAct pattern for LLM agents?"

sleep 1

# Direct LLM chat through MCP (no RAG — tests LLM tool)
echo -e "\n${BOLD}[MCP → llm_chat] Direct LLM — no RAG${RESET}"
result=$(curl -sf -X POST "$MCP_HUB/tools/llm_chat/call" \
    -H "Content-Type: application/json" \
    -d '{"tool_name":"llm_chat","arguments":{"message":"In one sentence: what is the difference between RAG and fine-tuning?"}}' \
    2>/dev/null || echo '{"error":"request failed"}')
answer=$(echo "$result" | python3 -c 'import sys,json; d=json.load(sys.stdin); r=d.get("result",{}); print((r.get("content") or r.get("response") or str(r))[:250])' 2>/dev/null || echo "(parse error)")
echo "  Answer: $answer"

# ── MCP audit log ─────────────────────────────────────────────────────────────

banner "6. MCP Audit Log — last 10 calls"

curl -sf "$MCP_HUB/audit?limit=10" 2>/dev/null \
    | python3 -c '
import sys, json
entries = json.load(sys.stdin)
if isinstance(entries, dict):
    entries = entries.get("entries", entries.get("items", []))
for e in entries:
    ts   = e.get("timestamp","?")[:19]
    tool = e.get("tool_name","?")
    ms   = e.get("latency_ms","?")
    ok   = "✓" if e.get("success") else "✗"
    print(f"  {ok} [{ts}] {tool:<25} {ms}ms")
' 2>/dev/null || echo "  (could not fetch audit log)"

# ── Langfuse trace summary ────────────────────────────────────────────────────

banner "7. Langfuse — trace summary"

echo -e "  Fetching recent traces from Langfuse API…\n"

LF_PK="${LANGFUSE_PUBLIC_KEY:-pk-lf-be9b9003-6d6a-419f-a04f-d6035d657db7}"
LF_SK="${LANGFUSE_SECRET_KEY:-sk-lf-fa952165-bc1a-4786-9280-a9814dc7ea32}"

curl -sf -u "$LF_PK:$LF_SK" \
    "http://localhost:3000/api/public/traces?limit=20" 2>/dev/null \
    | python3 -c '
import sys, json
data = json.load(sys.stdin)
traces = data.get("data", [])
print(f"  Total traces in Langfuse: {data.get(\"meta\",{}).get(\"totalItems\", len(traces))}")
print()
for t in traces[:12]:
    name  = t.get("name","?")
    ts    = t.get("timestamp","?")[:19]
    inp   = str(t.get("input",""))[:60].replace("\n"," ")
    print(f"  [{ts}] {name:<25} input={inp}")
' 2>/dev/null || echo "  (Langfuse API not reachable — check keys)"

echo ""
echo -e "${BOLD}${GREEN}✔  Demo complete!${RESET}"
echo ""
echo -e "  ${CYAN}→ Open http://localhost:3000${RESET} → Traces to explore the full LangGraph"
echo    "    execution tree for every agentic-rag call above."
echo ""
echo -e "  ${CYAN}→ Click any trace${RESET} to see the node-level spans:"
echo    "    retrieve → grade_documents → (rewrite_query →)* → generate"
echo ""
echo -e "  ${CYAN}→ Click a Generation observation${RESET} to see the exact prompt sent to"
echo    "    the LLM, the raw completion, and token usage."
echo ""
