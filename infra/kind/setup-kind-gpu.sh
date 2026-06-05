#!/bin/bash
set -e

echo "🚀 Setting up kind cluster with GPU support..."

if kind get clusters | grep -q "private-ai"; then
    echo "⚠️  Cluster 'private-ai' already exists. Delete it? (y/n)"
    read -r response
    if [[ "$response" == "y" ]]; then
        kind delete cluster --name private-ai
    else
        echo "❌ Aborted"
        exit 1
    fi
fi

echo "📦 Creating kind cluster..."
kind create cluster --config kind-config.yaml

echo "✅ Cluster created successfully"
echo ""
echo "📊 Cluster info:"
kubectl cluster-info --context kind-private-ai
echo ""
echo "🔍 Nodes:"
kubectl get nodes
echo ""
echo "✅ Stage 0.1: kind cluster ready"
echo "Next: Install GPU Operator"
