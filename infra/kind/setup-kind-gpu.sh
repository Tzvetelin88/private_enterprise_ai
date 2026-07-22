#!/bin/bash
# Stage 0 — NVIDIA GPU kind cluster setup
# Requires: Linux host with NVIDIA drivers + nvidia-container-toolkit installed
# NOT compatible with Mac — use setup-kind.sh instead
set -e

echo "🚀 Setting up kind cluster with NVIDIA GPU support..."
echo "   ⚠️  This script requires a Linux host with NVIDIA drivers."
echo ""

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

echo "📦 Creating kind cluster with GPU config..."
kind create cluster --config "$SCRIPT_DIR/kind-config.yaml"

echo ""
echo "✅ Cluster created successfully"
echo ""
echo "📊 Cluster info:"
kubectl cluster-info --context kind-private-ai
echo ""
echo "🔍 Nodes:"
kubectl get nodes
echo ""
echo "✅ Stage 0: kind cluster (GPU) ready"
echo "Next: bash infra/k8s/install-gpu-operator.sh"
