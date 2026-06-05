#!/bin/bash
set -e

echo "🔍 Verifying GPU detection in Kubernetes..."

echo ""
echo "1️⃣ Checking node labels for GPU:"
kubectl get nodes -o json | jq -r '.items[] | .metadata.name + ": " + (.metadata.labels | to_entries | map(select(.key | contains("nvidia"))) | from_entries | tostring)'

echo ""
echo "2️⃣ Checking allocatable GPU resources:"
kubectl get nodes -o custom-columns='NODE:.metadata.name,GPU:.status.allocatable.nvidia\.com/gpu'

echo ""
echo "3️⃣ Testing GPU access with test pod:"
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: gpu-test
spec:
  restartPolicy: Never
  containers:
  - name: cuda-test
    image: nvidia/cuda:12.2.0-base-ubuntu22.04
    command: ["nvidia-smi"]
    resources:
      limits:
        nvidia.com/gpu: 1
EOF

echo "⏳ Waiting for test pod to complete..."
kubectl wait --for=condition=complete pod/gpu-test --timeout=60s || true

echo ""
echo "4️⃣ GPU test output:"
kubectl logs gpu-test

echo ""
echo "🧹 Cleaning up test pod..."
kubectl delete pod gpu-test

echo ""
echo "✅ GPU verification complete"
