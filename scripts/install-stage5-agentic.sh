#!/bin/bash
# Stage 5 — Agentic RAG Service (LangGraph self-correcting workflow)
# Prerequisites: Stage 5 Hybrid RAG must be deployed first (hybrid-rag is used as retriever).
# Usage: bash scripts/install-stage5-agentic.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "🚀 Installing Stage 5: Agentic RAG Service"
echo "============================================"

# ── 1. Build agentic-rag Docker image ────────────────────────────────────────
echo ""
echo "🔨 Building agentic-rag Docker image..."
docker build \
    -t agentic-rag:latest \
    -f "${PROJECT_ROOT}/rag/agentic-rag/Dockerfile" \
    "${PROJECT_ROOT}/rag"

echo "📤 Loading image into kind cluster..."
kind load docker-image agentic-rag:latest --name private-ai

# ── 2. Deploy agentic-rag service ─────────────────────────────────────────────
echo ""
echo "📡 Deploying agentic-rag service..."
helm upgrade --install agentic-rag \
    "${PROJECT_ROOT}/infra/helm/agentic-rag" \
    --namespace default \
    --wait

echo ""
echo "✅ Stage 5 — Agentic RAG Installation Complete!"
echo ""
echo "Test the agentic RAG pipeline:"
echo "  curl -X POST http://localhost:30880/v1/rag/agentic/query \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"query\": \"What is this project about?\"}'"
echo ""
echo "Check pod status:"
echo "  kubectl get pods | grep agentic"
