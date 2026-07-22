#!/bin/bash
# Stage 5 — Hybrid RAG Service
# Deploys: infinity-reranker, Elasticsearch (via Helm/ECK), hybrid-rag service
#
# Prerequisites: Stages 0-4 must be complete.
# Usage: bash scripts/install-stage5-hybrid.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "🚀 Installing Stage 5: Hybrid RAG Service"
echo "==========================================="

# ── 1. Deploy Infinity Reranker ──────────────────────────────────────────────
echo ""
echo "📦 Deploying Infinity Reranker (BAAI/bge-reranker-v2-m3)..."
helm upgrade --install infinity-reranker \
    "${PROJECT_ROOT}/infra/helm/infinity-reranker" \
    --namespace default \
    --wait=false

echo "   (First run downloads ~600MB model — this may take several minutes)"

# ── 2. Deploy Elasticsearch (single-node, for BM25) ─────────────────────────
echo ""
echo "📦 Deploying Elasticsearch (BM25 index)..."
helm repo add elastic https://helm.elastic.co 2>/dev/null || true
helm repo update
helm upgrade --install elasticsearch elastic/elasticsearch \
    --namespace default \
    --set replicas=1 \
    --set minimumMasterNodes=1 \
    --set resources.requests.memory=512Mi \
    --set resources.limits.memory=1Gi \
    --set "esConfig.elasticsearch\.yml=xpack.security.enabled: false" \
    --wait=false

# ── 3. Build hybrid-rag Docker image ─────────────────────────────────────────
echo ""
echo "🔨 Building hybrid-rag Docker image..."
docker build \
    -t hybrid-rag:latest \
    -f "${PROJECT_ROOT}/rag/hybrid-rag/Dockerfile" \
    "${PROJECT_ROOT}/rag"

echo "📤 Loading image into kind cluster..."
kind load docker-image hybrid-rag:latest --name private-ai

# ── 4. Wait for Elasticsearch to be ready ────────────────────────────────────
echo ""
echo "⏳ Waiting for Elasticsearch..."
kubectl rollout status deployment/elasticsearch-master --timeout=300s 2>/dev/null || \
kubectl rollout status statefulset/elasticsearch-master --timeout=300s || true

# ── 5. Apply DB migration ─────────────────────────────────────────────────────
echo ""
echo "🗄️  Applying database migration (documents + chunks tables)..."
kubectl exec -it deploy/private-ai-postgresql -- psql \
    -U postgres -d private_ai \
    -c "CREATE EXTENSION IF NOT EXISTS vector;" \
    2>/dev/null || echo "   ⚠️  Could not run migration automatically — run manually if needed"

# ── 6. Deploy hybrid-rag service ─────────────────────────────────────────────
echo ""
echo "📡 Deploying hybrid-rag service..."
helm upgrade --install hybrid-rag \
    "${PROJECT_ROOT}/infra/helm/hybrid-rag" \
    --namespace default \
    --wait

# ── 7. Wait for reranker ────────────────────────────────────────────────────
echo ""
echo "⏳ Waiting for Infinity Reranker..."
kubectl rollout status deployment/infinity-reranker --timeout=600s

echo ""
echo "✅ Stage 5 — Hybrid RAG Installation Complete!"
echo ""
echo "Test the hybrid RAG pipeline:"
echo "  # Upload a document"
echo "  curl -X POST http://localhost:30880/v1/rag/hybrid/upload \\"
echo "    -F 'file=@README.md'"
echo ""
echo "  # Query it"
echo "  curl -X POST http://localhost:30880/v1/rag/hybrid/query \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"query\": \"What is the project about?\"}'"
echo ""
echo "Check pod status:"
echo "  kubectl get pods | grep -E 'hybrid|elasticsearch|reranker'"
