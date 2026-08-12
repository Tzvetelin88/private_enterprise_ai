#!/bin/bash
# Full-stack health check for the Private Enterprise AI Platform.
#
# Checks, in order: kind cluster + nodes, core Kubernetes workloads
# (Stage 1-4), the local model server (Ollama/vLLM), the two docker-compose
# stacks (rag/, mcp/), HTTP reachability of every service's health endpoint,
# and basic data-plane sanity (pgvector extension present, Redis PING).
#
# Usage: bash scripts/health-check.sh [--quiet]
#   --quiet   only print failures/warnings and the final summary
#
# Exit code: 0 if everything passed, 1 if anything failed (warnings don't
# affect the exit code — they flag optional/skippable components).

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
QUIET=false
[[ "${1:-}" == "--quiet" ]] && QUIET=true

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[0;33m'; BOLD='\033[1m'; NC='\033[0m'

PASS=0
FAIL=0
WARN=0
FAILED_ITEMS=()
WARN_ITEMS=()

section() {
    echo ""
    echo -e "${BOLD}── $1 ────────────────────────────────────────${NC}"
}

pass() {
    PASS=$((PASS + 1))
    $QUIET || echo -e "  ${GREEN}✅ PASS${NC}  $1"
}

fail() {
    FAIL=$((FAIL + 1))
    FAILED_ITEMS+=("$1")
    echo -e "  ${RED}❌ FAIL${NC}  $1${2:+ — $2}"
}

warn() {
    WARN=$((WARN + 1))
    WARN_ITEMS+=("$1")
    echo -e "  ${YELLOW}⚠️  WARN${NC}  $1${2:+ — $2}"
}

# curl a URL, PASS if it returns one of $2 (space-separated codes, default "200")
check_http() {
    local label="$1" url="$2" ok_codes="${3:-200}"
    local code
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 4 "$url" 2>/dev/null)
    if [[ " $ok_codes " == *" $code "* ]]; then
        pass "$label ($url → $code)"
    else
        fail "$label ($url)" "got HTTP ${code:-timeout/unreachable}"
    fi
}

# ── Kind cluster ──────────────────────────────────────────────────────────────
section "Kind Cluster"

if ! command -v kind >/dev/null 2>&1; then
    fail "kind CLI installed" "not found on PATH"
elif kind get clusters 2>/dev/null | grep -qx "private-ai"; then
    pass "kind cluster 'private-ai' exists"

    if command -v kubectl >/dev/null 2>&1 && kubectl cluster-info --context kind-private-ai >/dev/null 2>&1; then
        pass "kubectl can reach the cluster"

        NOT_READY=$(kubectl get nodes --no-headers 2>/dev/null | awk '$2 != "Ready" {print $1}')
        if [[ -z "$NOT_READY" ]]; then
            pass "all kind nodes Ready"
        else
            fail "kind nodes Ready" "not ready: $NOT_READY"
        fi
    else
        fail "kubectl can reach the cluster" "cluster-info failed"
    fi
else
    fail "kind cluster 'private-ai' exists" "run: bash infra/kind/setup-kind.sh"
fi

# ── Kubernetes workloads (Stage 1-4) ─────────────────────────────────────────
section "Kubernetes Workloads (Stage 1-4)"

if command -v kubectl >/dev/null 2>&1 && kubectl get nodes >/dev/null 2>&1; then
    # Parallel arrays (name-prefix / friendly label) — avoids bash 4+
    # associative arrays, since macOS ships bash 3.2 by default and no other
    # script in this repo assumes a newer one.
    K8S_PREFIXES=(postgresql prometheus-server grafana api-gateway infinity-embeddings)
    K8S_LABELS=("PostgreSQL + pgvector (Stage 1)" "Prometheus (Stage 1)" "Grafana (Stage 1)" "API Gateway (Stage 3)" "Infinity Embeddings (Stage 4)")

    PODS="$(kubectl get pods --no-headers 2>/dev/null)"
    for i in "${!K8S_PREFIXES[@]}"; do
        prefix="${K8S_PREFIXES[$i]}"
        friendly="${K8S_LABELS[$i]}"
        line=$(echo "$PODS" | grep "^${prefix}" | head -1)
        if [[ -z "$line" ]]; then
            fail "$friendly" "no pod found (name prefix '$prefix')"
            continue
        fi
        status=$(echo "$line" | awk '{print $3}')
        ready=$(echo "$line" | awk '{print $2}')
        if [[ "$status" == "Running" && "${ready%/*}" == "${ready#*/}" ]]; then
            pass "$friendly ($ready Ready)"
        else
            fail "$friendly" "status=$status ready=$ready"
        fi
    done

    # pgvector extension actually enabled (not just the pod running)
    if kubectl exec postgresql-0 -c postgresql -- env PGPASSWORD=changeme-postgres-admin \
        psql -U postgres -d private_ai -tAc "SELECT 1 FROM pg_extension WHERE extname='vector'" 2>/dev/null | grep -q 1; then
        pass "pgvector extension enabled in private_ai DB"
    else
        fail "pgvector extension enabled in private_ai DB" "run migrations/003_add_pgvector_embedding.sql"
    fi
else
    warn "Kubernetes workloads" "cluster unreachable — skipped"
fi

# ── Model server ──────────────────────────────────────────────────────────────
section "Model Server"

check_http "Ollama API (localhost:11434)" "http://localhost:11434/api/tags"

# ── Docker Compose: RAG stack ────────────────────────────────────────────────
section "Docker Compose — RAG stack (rag/docker-compose.yml)"

RAG_CONTAINERS=(rag-hybrid rag-agentic rag-graph rag-elasticsearch rag-neo4j rag-redis rag-langfuse rag-langfuse-db)
for c in "${RAG_CONTAINERS[@]}"; do
    if ! docker inspect "$c" >/dev/null 2>&1; then
        fail "$c" "container not found — is rag/docker-compose.yml up?"
        continue
    fi
    state=$(docker inspect -f '{{.State.Status}}' "$c")
    health=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$c")
    if [[ "$state" != "running" ]]; then
        fail "$c" "state=$state"
    elif [[ "$health" == "unhealthy" ]]; then
        fail "$c" "healthcheck=unhealthy"
    elif [[ "$health" == "starting" ]]; then
        warn "$c" "healthcheck still starting"
    else
        pass "$c (running${health:+, $health})"
    fi
done

# ── Docker Compose: MCP stack ─────────────────────────────────────────────────
section "Docker Compose — MCP stack (mcp/docker-compose.yml)"

MCP_CONTAINERS=(mcp-mcp-hub-1 mcp-mcp-server-1 mcp-mcp-client-1)
for c in "${MCP_CONTAINERS[@]}"; do
    if ! docker inspect "$c" >/dev/null 2>&1; then
        warn "$c" "container not found — MCP stack not up (optional, independent of RAG)"
        continue
    fi
    state=$(docker inspect -f '{{.State.Status}}' "$c")
    if [[ "$state" == "running" ]]; then
        pass "$c (running)"
    else
        fail "$c" "state=$state"
    fi
done

# ── HTTP health endpoints ─────────────────────────────────────────────────────
section "HTTP Health Endpoints"

check_http "hybrid-rag   :8001/health" "http://localhost:8001/health"
check_http "agentic-rag  :8002/health" "http://localhost:8002/health"
check_http "graph-rag    :8003/health" "http://localhost:8003/health"
check_http "mcp-hub      :8010/health" "http://localhost:8010/health"
check_http "mcp-server   :8011/health" "http://localhost:8011/health"
check_http "mcp-client   :8012/health" "http://localhost:8012/health"
check_http "Infinity embeddings :30797/health" "http://localhost:30797/health"
check_http "API Gateway  :30880/health" "http://localhost:30880/health"
check_http "Langfuse     :3000" "http://localhost:3000"
check_http "Grafana      :30030" "http://localhost:30030" "200 302"
check_http "Prometheus   :30090/-/healthy" "http://localhost:30090/-/healthy"
check_http "Elasticsearch :9200" "http://localhost:9200"

# ── Data plane sanity ─────────────────────────────────────────────────────────
section "Data Plane Sanity"

if docker inspect rag-redis >/dev/null 2>&1; then
    if [[ "$(docker exec rag-redis redis-cli ping 2>/dev/null)" == "PONG" ]]; then
        pass "Redis PING"
    else
        fail "Redis PING" "no PONG"
    fi
else
    warn "Redis PING" "rag-redis container not found"
fi

if command -v pg_isready >/dev/null 2>&1; then
    if PGPASSWORD=changeme-postgres-admin pg_isready -h localhost -p 30432 -U postgres >/dev/null 2>&1; then
        pass "PostgreSQL accepting connections (localhost:30432)"
    else
        fail "PostgreSQL accepting connections (localhost:30432)"
    fi
else
    warn "PostgreSQL accepting connections" "pg_isready not installed locally — skipped (kubectl-based check above already covers the pod)"
fi

# ── Summary ────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  Summary:${NC}  ${GREEN}${PASS} passed${NC}, ${RED}${FAIL} failed${NC}, ${YELLOW}${WARN} warnings${NC}"
echo -e "${BOLD}════════════════════════════════════════════════${NC}"

if [[ $FAIL -gt 0 ]]; then
    echo ""
    echo -e "${RED}Failed checks:${NC}"
    for item in "${FAILED_ITEMS[@]}"; do
        echo "  - $item"
    done
fi
if [[ $WARN -gt 0 ]]; then
    echo ""
    echo -e "${YELLOW}Warnings (optional/skipped components):${NC}"
    for item in "${WARN_ITEMS[@]}"; do
        echo "  - $item"
    done
fi

echo ""
if [[ $FAIL -eq 0 ]]; then
    echo -e "${GREEN}${BOLD}Overall: HEALTHY${NC}"
    exit 0
else
    echo -e "${RED}${BOLD}Overall: UNHEALTHY${NC}"
    exit 1
fi
