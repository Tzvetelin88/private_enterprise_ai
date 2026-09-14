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

# ── 2. Apply DB Migrations ────────────────────────────────────────────────────
# Runs the full alembic chain (includes 002, which creates mcp_tools/mcp_audit_log).
# Idempotent and safe to re-run even if a later stage already applied it.
echo ""
bash "${PROJECT_ROOT}/scripts/apply-migrations.sh" \
    || echo "   ⚠️  Could not apply migrations automatically — run manually: bash scripts/apply-migrations.sh"

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
