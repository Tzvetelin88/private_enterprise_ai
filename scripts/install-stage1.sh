#!/bin/bash
set -e

echo "🚀 Installing Stage 1: Core Infrastructure"
echo ""

cd "$(dirname "$0")/.."

echo "📦 Adding Helm repositories..."
helm repo add bitnami https://charts.bitnami.com/bitnami || true
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts || true
helm repo add grafana https://grafana.github.io/helm-charts || true
helm repo update

echo ""
echo "🔐 Creating PostgreSQL secrets..."
kubectl apply -f infra/k8s/postgresql-secret.yaml --validate=false

echo ""
echo "🗄️  Installing PostgreSQL + pgvector..."
helm upgrade --install postgresql bitnami/postgresql \
  --values infra/helm/private-ai/values-postgresql.yaml \
  --wait \
  --timeout 10m

echo ""
echo "⏳ Waiting for PostgreSQL to be ready..."
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=postgresql --timeout=300s

echo ""
echo "✅ PostgreSQL installed with pgvector extension (configured via initdb scripts)"
echo "   To verify manually: kubectl exec -it postgresql-0 -- psql -U postgres -d private_ai"

echo ""
echo "📊 Installing Prometheus..."
helm upgrade --install prometheus prometheus-community/prometheus \
  --values infra/helm/private-ai/values-prometheus.yaml \
  --wait \
  --timeout 10m

echo ""
echo "📈 Installing Grafana..."
helm upgrade --install grafana grafana/grafana \
  --values infra/helm/private-ai/values-grafana.yaml \
  --wait \
  --timeout 5m

echo ""
echo "⏳ Waiting for all pods to be ready..."
kubectl wait --for=condition=ready pod --all --timeout=300s

echo ""
echo "✅ Stage 1 Installation Complete!"
echo ""
echo "📊 Access Points:"
echo "  Grafana: http://localhost:30030"
echo "    Username: admin"
echo "    Password: admin"
echo ""
echo "  Prometheus: http://localhost:30090"
echo ""
echo "  PostgreSQL (External Access):"
echo "    Host: localhost"
echo "    Port: 30432"
echo "    Database: private_ai"
echo "    Username: postgres"
echo "    Password: changeme-postgres-admin"
echo ""
echo "🔍 Verify installation:"
echo "  kubectl get pods"
echo "  kubectl get svc"
echo ""
echo "Next: Run Stage 2 - vLLM deployment"
