#!/bin/bash
# Stage 0 — Mac/ARM64 kind cluster setup (no GPU mounts)
set -e

echo "🚀 Setting up kind cluster (Mac / CPU mode)..."

if kind get clusters 2>/dev/null | grep -q "private-ai"; then
    echo "⚠️  Cluster 'private-ai' already exists."
    echo "   Delete it and recreate? (y/n)"
    read -r response
    if [[ "$response" == "y" ]]; then
        kind delete cluster --name private-ai
    else
        echo "❌ Aborted — cluster left unchanged"
        exit 1
    fi
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "📦 Creating kind cluster with Mac config..."
kind create cluster --config "$SCRIPT_DIR/kind-config-mac.yaml"

echo ""
echo "✅ Cluster created successfully"
echo ""
echo "📊 Cluster info:"
kubectl cluster-info --context kind-private-ai
echo ""
echo "🔍 Nodes:"
kubectl get nodes
echo ""
echo "✅ Stage 0: kind cluster ready"
echo "Next: bash scripts/install-stage1.sh"
