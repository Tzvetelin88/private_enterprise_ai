#!/bin/bash
# Stage 5 — Graph RAG Service (entity extraction + Neo4j knowledge graph)
# Prerequisites: Stages 0-4 complete, hybrid-rag deployed (shares pgvector).
# Usage: bash scripts/install-stage5-graph.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "🚀 Installing Stage 5: Graph RAG Service"
echo "========================================="

# ── 1. Deploy Neo4j (community edition with APOC) ────────────────────────────
echo ""
echo "📦 Deploying Neo4j (community + APOC)..."
helm repo add neo4j https://helm.neo4j.com/neo4j 2>/dev/null || true
helm repo update

helm upgrade --install neo4j neo4j/neo4j \
    --namespace default \
    --set neo4j.name=neo4j \
    --set neo4j.password=changeme-neo4j \
    --set volumes.data.mode=defaultStorageClass \
    --set neo4j.edition=community \
    --set config."server\.jvm\.additional"="-Xss512k" \
    --wait=false || {
    echo "   ℹ️  Neo4j Helm chart failed — starting via docker-compose for local dev"
    echo "   Run: docker compose -f rag/docker-compose.yml up -d neo4j"
}

# ── 2. Build graph-rag Docker image ───────────────────────────────────────────
echo ""
echo "🔨 Building graph-rag Docker image..."
docker build \
    -t graph-rag:latest \
    -f "${PROJECT_ROOT}/rag/graph-rag/Dockerfile" \
    "${PROJECT_ROOT}/rag"

echo "📤 Loading image into kind cluster..."
kind load docker-image graph-rag:latest --name private-ai

# ── 3. Deploy graph-rag service ───────────────────────────────────────────────
echo ""
echo "📡 Deploying graph-rag service..."
helm upgrade --install graph-rag \
    "${PROJECT_ROOT}/infra/helm/graph-rag" \
    --namespace default \
    --wait

echo ""
echo "✅ Stage 5 — Graph RAG Installation Complete!"
echo ""
echo "Test the graph RAG pipeline:"
echo "  # Upload two related docs"
echo "  curl -X POST http://localhost:30880/v1/rag/graph/upload -F 'file=@README.md'"
echo ""
echo "  # Query relationships"
echo "  curl -X POST http://localhost:30880/v1/rag/graph/query \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"query\": \"Which services depend on the API Gateway?\"}'"
echo ""
echo "  # Inspect entity subgraph"
echo "  curl http://localhost:30880/v1/rag/graph/graph/api-gateway"
echo ""
echo "Local dev (Neo4j + all RAG deps):"
echo "  docker compose -f rag/docker-compose.yml up -d"
echo ""
echo "Check pod status:"
echo "  kubectl get pods | grep -E 'graph|neo4j'"
