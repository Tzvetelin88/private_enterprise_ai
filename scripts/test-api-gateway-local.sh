#!/bin/bash
set -e

echo "🧪 Testing API Gateway locally..."
echo ""

cd "$(dirname "$0")/../apps/api-gateway"

echo "📦 Installing dependencies..."
pip install -e .

echo ""
echo "🚀 Starting API Gateway (Ctrl+C to stop)..."
echo ""
echo "Prerequisites:"
echo "  - vLLM must be running: bash scripts/run-vllm-local.sh"
echo ""

# Create .env if doesn't exist
if [ ! -f .env ]; then
    cp .env.example .env
    echo "✅ Created .env from .env.example"
fi

# Run the application
python -m uvicorn src.main:app --host 0.0.0.0 --port 8080 --reload

# After starting, test with:
# curl http://localhost:8080/health
# curl http://localhost:8080/v1/models
