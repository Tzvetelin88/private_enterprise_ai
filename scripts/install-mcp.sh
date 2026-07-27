#!/bin/bash
# Install MCP Subsystem
# Deploys: mcp-hub, mcp-server, mcp-client
#
# Usage: bash scripts/install-mcp.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "🚀 Installing MCP Subsystem"
echo "==========================="

# ── 1. Build and Load Docker Images ──────────────────────────────────────────

for service in mcp-hub mcp-server mcp-client; do
    echo ""
    echo "🔨 Building ${service} Docker image..."
    docker build \
        -t ${service}:latest \
        -f "${PROJECT_ROOT}/mcp/${service}/Dockerfile" \
        "${PROJECT_ROOT}/mcp/${service}"

    echo "📤 Loading ${service} image into kind cluster..."
    kind load docker-image ${service}:latest --name private-ai
done

# ── 2. Apply DB Migration ─────────────────────────────────────────────────────
echo ""
echo "🗄️  Applying database migration (MCP tables)..."
MIGRATION_FILE="${PROJECT_ROOT}/packages/shared-db/src/shared_db/migrations/002_create_mcp_tables.sql"
if [ -f "$MIGRATION_FILE" ]; then
    kubectl exec -i deploy/private-ai-postgresql -- psql \
        -U postgres -d private_ai < "$MIGRATION_FILE" \
        || echo "   ⚠️  Could not run migration automatically — run manually if needed"
else
    echo "   ⚠️  Migration file not found at $MIGRATION_FILE"
fi

# ── 3. Deploy Helm Charts ─────────────────────────────────────────────────────

for service in mcp-hub mcp-server mcp-client; do
    echo ""
    echo "📡 Deploying ${service}..."
    helm upgrade --install ${service} \
        "${PROJECT_ROOT}/infra/helm/${service}" \
        --namespace default \
        --wait
done

echo ""
echo "✅ MCP Subsystem Installation Complete!"
echo ""
echo "Test the MCP Hub:"
echo "  curl http://localhost:30880/v1/mcp/tools"
echo ""
echo "Check pod status:"
echo "  kubectl get pods | grep mcp"
