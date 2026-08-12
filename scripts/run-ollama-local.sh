#!/bin/bash
# Start Ollama model server for Mac / M-series (Metal GPU accelerated)
# This is the Mac equivalent of run-vllm-local.sh
# Ollama exposes an OpenAI-compatible API on port 11434
set -e

MODEL="${OLLAMA_MODEL:-qwen3.5:4b}"
PORT=11434

echo "🍎 Starting Ollama model server (Mac / Metal)"
echo "   Model : $MODEL"
echo "   Port  : $PORT"
echo ""

if ! command -v ollama &>/dev/null; then
    echo "📦 Ollama not found — installing via Homebrew..."
    brew install ollama
fi

echo "▶️  Starting Ollama service..."
if pgrep -x ollama &>/dev/null; then
    echo "   Ollama is already running."
else
    ollama serve &
    echo "   Waiting for service to be ready..."
    sleep 3
fi

echo ""
echo "📥 Pulling model: $MODEL"
ollama pull "$MODEL"

echo ""
echo "✅ Ollama is ready!"
echo ""
echo "📊 Access (OpenAI-compatible):"
echo "  http://localhost:$PORT/v1/models"
echo "  http://localhost:$PORT/v1/chat/completions"
echo ""
echo "🔍 Quick test:"
echo "  curl http://localhost:$PORT/v1/models"
echo "  curl http://localhost:$PORT/v1/chat/completions \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Hello\"}]}'"
echo ""
echo "💡 API Gateway connects via: http://host.docker.internal:$PORT"
