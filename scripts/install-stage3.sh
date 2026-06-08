#!/bin/bash
set -e

echo "🚀 Installing Stage 3: API Gateway"
echo ""

cd "$(dirname "$0")/.."

echo "🐳 Building API Gateway Docker image..."
docker build -t api-gateway:latest ./apps/api-gateway

echo ""
echo "📦 Loading image into kind cluster..."
kind load docker-image api-gateway:latest --name private-ai

echo ""
echo "📦 Installing API Gateway to Kubernetes..."
helm upgrade --install api-gateway infra/helm/api-gateway \
  --wait \
  --timeout 5m

echo ""
echo "⏳ Waiting for API Gateway to be ready..."
kubectl wait --for=condition=ready pod -l app=api-gateway --timeout=180s

echo ""
echo "✅ Stage 3 Installation Complete!"
echo ""
echo "📊 Access Points:"
echo "  API Gateway: http://localhost:30880"
echo ""
echo "🔍 Test endpoints:"
echo "  curl http://localhost:30880/health"
echo "  curl http://localhost:30880/v1/models"
echo ""
echo "📈 Check logs:"
echo "  kubectl logs -l app=api-gateway --tail=50 -f"
echo ""
echo "Next: Test the complete flow through API Gateway"
