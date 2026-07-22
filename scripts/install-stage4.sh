#!/bin/bash
# Stage 4: Infinity Embeddings Service
# Works on Mac (M-series CPU) and NVIDIA GPU nodes.
# No platform-specific changes needed — Infinity runs CPU-only by default.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "🚀 Installing Stage 4: Embedding Service"
echo "=========================================="

# Deploy Infinity Embeddings Server
echo ""
echo "📦 Deploying Infinity Embeddings Server..."
helm upgrade --install infinity-embeddings \
    "${PROJECT_ROOT}/infra/helm/infinity-embeddings" \
    --namespace default \
    --wait=false

echo ""
echo "⏳ Waiting for Infinity to be ready..."
echo "   (First run downloads ~200MB model — this may take several minutes)"
kubectl rollout status deployment/infinity-embeddings --timeout=600s

# Rebuild API Gateway image with embeddings support
echo ""
echo "🔄 Rebuilding API Gateway with embeddings support..."
docker build -t api-gateway:latest "${PROJECT_ROOT}/apps/api-gateway"
kind load docker-image api-gateway:latest --name private-ai

# Upgrade API Gateway to pick up new INFINITY_URL env var
echo ""
echo "📡 Upgrading API Gateway..."
helm upgrade --install api-gateway \
    "${PROJECT_ROOT}/infra/helm/api-gateway" \
    --namespace default \
    --wait

echo ""
echo "✅ Stage 4 Installation Complete!"
echo ""
echo "Test the embeddings endpoint:"
echo "  curl http://localhost:30880/v1/embeddings \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"input\": \"Hello world\", \"model\": \"BAAI/bge-small-en-v1.5\"}'"
echo ""
echo "Check pod status:"
echo "  kubectl get pods -l app=infinity-embeddings"
echo "  kubectl logs -l app=infinity-embeddings --tail=50"
