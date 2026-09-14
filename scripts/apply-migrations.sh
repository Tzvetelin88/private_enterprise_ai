#!/bin/bash
# Apply all pending Alembic migrations (packages/shared-db) against PostgreSQL.
#
# Single source of truth for "how do I run the migrations" — install-mcp.sh
# and install-stage4.sh both call this instead of duplicating the logic.
#
# Uses a dedicated .venv at the repo root rather than the system/Homebrew
# Python: a bare `pip install alembic` there only gets you alembic itself —
# not sqlalchemy's asyncio extra, asyncpg, or the greenlet it depends on —
# and a plain system-wide `pip install` is refused outright on Homebrew-managed
# Python (PEP 668, "externally-managed-environment"). Installing
# packages/shared-db itself (not just "alembic") pulls in every dependency its
# pyproject.toml actually declares, transitively, in one step.
#
# Idempotent — alembic tracks its own applied-revisions state in the target
# DB, so re-running this is always safe.
#
# Usage: bash scripts/apply-migrations.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"

if [ ! -x "${VENV_DIR}/bin/python" ]; then
    echo "🐍 Creating venv at ${VENV_DIR}..."
    python3 -m venv "${VENV_DIR}"
fi

echo "📦 Installing/updating shared-db (alembic + sqlalchemy[asyncio] + asyncpg)..."
"${VENV_DIR}/bin/python" -m pip install -q -e "${PROJECT_ROOT}/packages/shared-db"

echo "🗄️  Applying database migrations (alembic upgrade head)..."
(cd "${PROJECT_ROOT}/packages/shared-db" && "${VENV_DIR}/bin/alembic" upgrade head)

echo "✅ Migrations up to date: $(cd "${PROJECT_ROOT}/packages/shared-db" && "${VENV_DIR}/bin/alembic" current)"
