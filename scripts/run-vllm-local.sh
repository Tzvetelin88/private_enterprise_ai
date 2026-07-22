#!/bin/bash
# Start vLLM server locally — NVIDIA GPU (Linux/WSL2) ONLY
# Requires: CUDA-capable GPU + vLLM installed (pip install vllm)
# NOT compatible with Mac — use run-ollama-local.sh instead
set -e

MODEL_NAME="${VLLM_MODEL:-meta-llama/Llama-3.2-3B-Instruct}"
PORT=8000

echo "🟢 Starting vLLM server (NVIDIA GPU mode)"
echo "   Model : $MODEL_NAME"
echo "   Port  : $PORT"
echo ""
echo "⚠️  This script requires a CUDA-capable NVIDIA GPU."
echo "   On Mac, use: bash scripts/run-ollama-local.sh"
echo ""

# Verify vLLM is installed
if ! python3 -c "import vllm" &>/dev/null; then
    echo "❌ vLLM not installed. Install with: pip install vllm"
    exit 1
fi

python3 -m vllm.entrypoints.openai.api_server \
  --model "$MODEL_NAME" \
  --host 0.0.0.0 \
  --port "$PORT" \
  --gpu-memory-utilization 0.9 \
  --max-model-len 2048

# After starting, test with:
# curl http://localhost:8000/v1/models
# curl http://localhost:8000/v1/completions \
#   -H "Content-Type: application/json" \
#   -d '{"model": "meta-llama/Llama-3.2-3B-Instruct", "prompt": "Hello", "max_tokens": 50}'
