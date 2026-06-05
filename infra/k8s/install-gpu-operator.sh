#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🎯 Installing NVIDIA GPU Operator..."

echo "📦 Adding NVIDIA Helm repository..."
helm repo add nvidia https://helm.ngc.nvidia.com/nvidia || true
helm repo update

echo "🔧 Creating gpu-operator namespace..."
kubectl create namespace gpu-operator --dry-run=client -o yaml | kubectl apply -f -

echo "⚙️  Installing GPU Operator..."
helm upgrade --install gpu-operator nvidia/gpu-operator \
  --namespace gpu-operator \
  --values "$SCRIPT_DIR/gpu-operator-values.yaml" \
  --wait \
  --timeout 10m

echo ""
echo "⏳ Waiting for GPU Operator to be ready (this may take 5-10 minutes)..."
echo "   Checking pod status every 10 seconds..."

# Wait for pods to start (up to 5 minutes)
for i in {1..30}; do
    POD_COUNT=$(kubectl get pods -n gpu-operator 2>/dev/null | grep -v NAME | wc -l)
    if [ "$POD_COUNT" -gt 0 ]; then
        echo "   ✓ GPU Operator pods are starting..."
        break
    fi
    echo "   Waiting for pods to be created... ($i/30)"
    sleep 10
done

# Wait for pods to be ready (more flexible approach)
echo "   Waiting for all pods to be ready..."
kubectl wait --for=condition=ready pod --all -n gpu-operator --timeout=600s || {
    echo "⚠️  Some pods may still be initializing. Current status:"
    kubectl get pods -n gpu-operator
    echo ""
    echo "Note: GPU Operator may take longer on first install."
    echo "Check status with: kubectl get pods -n gpu-operator"
}

echo ""
echo "📊 GPU Operator status:"
kubectl get pods -n gpu-operator

echo ""
echo "✅ Stage 0.2: GPU Operator installed"
echo "Next: Verify GPU detection"
