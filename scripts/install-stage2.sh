#!/bin/bash
set -e

echo "🚀 Installing Stage 2: Model Inference Runtime"
echo ""

cd "$(dirname "$0")/.."

echo "📦 Creating model storage PVC..."
kubectl apply -f - <<EOF
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: model-storage
  namespace: default
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 50Gi
EOF

echo ""
echo "🤖 Installing vLLM..."
helm upgrade --install vllm infra/helm/vllm \
  --wait \
  --timeout 15m

echo ""
echo "⏳ Waiting for vLLM to be ready..."
kubectl wait --for=condition=ready pod -l app=vllm --timeout=900s

echo ""
echo "✅ Stage 2 Installation Complete!"
echo ""
echo "📊 Access Points:"
echo "  vLLM API: http://localhost:30800"
echo ""
echo "🔍 Test endpoints:"
echo "  curl http://localhost:30800/v1/models"
echo "  curl http://localhost:30800/health"
echo ""
echo "📈 Monitor GPU usage:"
echo "  kubectl logs -l app=vllm --tail=50"
echo "  Check Grafana GPU dashboard: http://localhost:30030"
echo ""
echo "Next: Test model inference with a sample prompt"
