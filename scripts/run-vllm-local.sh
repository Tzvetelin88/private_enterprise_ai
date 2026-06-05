#!/bin/bash
set -e

echo "🚀 Starting vLLM server locally..."
echo ""

MODEL_NAME="meta-llama/Llama-3.2-3B-Instruct"
PORT=8000

echo "📦 Model: $MODEL_NAME"
echo "🌐 Port: $PORT"
echo ""
echo "💡 Access at: http://localhost:$PORT"
echo ""

python3 -m vllm.entrypoints.openai.api_server \
  --model "$MODEL_NAME" \
  --host 0.0.0.0 \
  --port $PORT \
  --gpu-memory-utilization 0.9 \
  --max-model-len 2048

# After starting, test with:
# curl http://localhost:8000/v1/models
# curl http://localhost:8000/v1/completions -H "Content-Type: application/json" -d '{"model": "meta-llama/Llama-3.2-3B-Instruct", "prompt": "Hello", "max_tokens": 50}'
