#!/bin/bash
# Stage 2 — Model Inference Runtime
#
# Default mode: Ollama (Mac / ARM64 / CPU+Metal — no CUDA required)
# NVIDIA mode:  set GPU_MODE=nvidia to deploy vLLM into the kind cluster instead
#
# Usage:
#   bash scripts/install-stage2.sh            # Mac default (Ollama)
#   GPU_MODE=nvidia bash scripts/install-stage2.sh  # NVIDIA GPU (Linux)
set -e

cd "$(dirname "$0")/.."

GPU_MODE="${GPU_MODE:-mac}"

echo "🚀 Stage 2: Model Inference Runtime (mode: $GPU_MODE)"
echo ""

# ──────────────────────────────────────────────
# Mac / CPU mode — Ollama (runs outside cluster)
# ──────────────────────────────────────────────
if [[ "$GPU_MODE" == "mac" ]]; then
    echo "🍎 Mac mode: model server runs outside the kind cluster via Ollama."
    echo "   Ollama uses Apple Metal for GPU acceleration on M-series chips."
    echo ""

    if ! command -v ollama &>/dev/null; then
        echo "📦 Installing Ollama via Homebrew..."
        brew install ollama
    else
        echo "✅ Ollama already installed: $(ollama --version)"
    fi

    echo ""
    echo "▶️  Starting Ollama service (background)..."
    # Start only if not already running
    if ! pgrep -x ollama &>/dev/null; then
        ollama serve &>/tmp/ollama.log &
        echo "   Waiting for Ollama to be ready..."
        sleep 3
    else
        echo "   Ollama already running."
    fi

    echo ""
    MODEL="llama3.2:3b"
    echo "📥 Pulling model: $MODEL (first run downloads ~2 GB)..."
    ollama pull "$MODEL"

    echo ""
    echo "✅ Stage 2 Complete — Ollama is running!"
    echo ""
    echo "📊 Access Points:"
    echo "  Ollama API: http://localhost:11434  (OpenAI-compatible)"
    echo ""
    echo "🔍 Test endpoints:"
    echo "  curl http://localhost:11434/api/tags"
    echo "  curl http://localhost:11434/v1/models"
    echo ""
    echo "💡 The API Gateway is pre-configured to reach Ollama via:"
    echo "   http://host.docker.internal:11434"
    echo ""
    echo "Next: bash scripts/install-stage3.sh"
    exit 0
fi

# ──────────────────────────────────────────────
# NVIDIA GPU mode — vLLM deployed into kind
# Requires: Linux host + NVIDIA drivers + nvidia-container-toolkit
# ──────────────────────────────────────────────
if [[ "$GPU_MODE" == "nvidia" ]]; then
    echo "🟢 NVIDIA mode: deploying vLLM into the kind cluster."
    echo "   Requires NVIDIA drivers and GPU Operator installed (Stage 0 NVIDIA path)."
    echo ""

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
    echo "🤖 Deploying vLLM Helm chart..."
    helm upgrade --install vllm infra/helm/vllm \
      --wait \
      --timeout 15m

    echo ""
    echo "⏳ Waiting for vLLM to be ready..."
    kubectl wait --for=condition=ready pod -l app=vllm --timeout=900s

    echo ""
    echo "✅ Stage 2 Complete — vLLM is running in cluster!"
    echo ""
    echo "📊 Access Points:"
    echo "  vLLM API: http://localhost:30800  (OpenAI-compatible)"
    echo ""
    echo "🔍 Test endpoints:"
    echo "  curl http://localhost:30800/v1/models"
    echo "  curl http://localhost:30800/health"
    echo ""
    echo "📈 Monitor GPU usage:"
    echo "  kubectl logs -l app=vllm --tail=50"
    echo "  Grafana GPU dashboard: http://localhost:30030"
    echo ""
    echo "Next: bash scripts/install-stage3.sh"
    exit 0
fi

echo "❌ Unknown GPU_MODE='$GPU_MODE'. Valid values: mac | nvidia"
exit 1
