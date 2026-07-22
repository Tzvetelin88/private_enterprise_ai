#!/bin/bash
# GPU / compute verification script
# On Mac  → shows Apple Silicon info and Metal availability
# On Linux → verifies NVIDIA GPU detection inside the kind cluster
set -e

OS="$(uname -s)"
ARCH="$(uname -m)"

echo "🔍 Compute Verification"
echo "   OS   : $OS"
echo "   Arch : $ARCH"
echo ""

# ──────────────────────────────────────────────
# Mac — Apple Silicon / Metal
# ──────────────────────────────────────────────
if [[ "$OS" == "Darwin" ]]; then
    echo "🍎 Mac detected — checking Apple Silicon / Metal GPU:"
    echo ""

    echo "1️⃣ CPU / GPU chip info:"
    sysctl -n machdep.cpu.brand_string 2>/dev/null || system_profiler SPHardwareDataType | grep "Chip"

    echo ""
    echo "2️⃣ Memory:"
    sysctl -n hw.memsize | awk '{printf "   Total RAM: %.0f GB\n", $1/1024/1024/1024}'

    echo ""
    echo "3️⃣ Metal GPU cores (via system_profiler):"
    system_profiler SPDisplaysDataType 2>/dev/null | grep -E "Chipset|Total Number of Cores|Metal" || echo "   (run: system_profiler SPDisplaysDataType)"

    echo ""
    echo "4️⃣ Ollama Metal check:"
    if command -v ollama &>/dev/null; then
        echo "   Ollama installed: $(ollama --version)"
        if pgrep -x ollama &>/dev/null; then
            echo "   Ollama service: ✅ running"
            curl -s http://localhost:11434/api/tags 2>/dev/null | python3 -c \
              "import json,sys; d=json.load(sys.stdin); [print('   Model:', m['name']) for m in d.get('models',[])]" \
              2>/dev/null || echo "   No models loaded yet"
        else
            echo "   Ollama service: ⚠️  not running (start with: ollama serve)"
        fi
    else
        echo "   Ollama: not installed (install with: brew install ollama)"
    fi

    echo ""
    echo "✅ Mac compute check complete."
    echo "   Apple Metal is always available on M-series — no extra setup needed."
    exit 0
fi

# ──────────────────────────────────────────────
# Linux — NVIDIA GPU in Kubernetes cluster
# ──────────────────────────────────────────────
echo "🟢 Linux detected — verifying NVIDIA GPU in kind cluster..."
echo ""

echo "1️⃣ Checking node labels for NVIDIA GPU:"
kubectl get nodes -o json | jq -r \
  '.items[] | .metadata.name + ": " + (.metadata.labels | to_entries | map(select(.key | contains("nvidia"))) | from_entries | tostring)'

echo ""
echo "2️⃣ Checking allocatable GPU resources:"
kubectl get nodes -o custom-columns='NODE:.metadata.name,GPU:.status.allocatable.nvidia\.com/gpu'

echo ""
echo "3️⃣ Testing GPU access with a test pod (nvidia-smi):"
kubectl apply -f - <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: gpu-test
spec:
  restartPolicy: Never
  containers:
  - name: cuda-test
    image: nvidia/cuda:12.2.0-base-ubuntu22.04
    command: ["nvidia-smi"]
    resources:
      limits:
        nvidia.com/gpu: 1
EOF

echo "⏳ Waiting for test pod to complete..."
kubectl wait --for=condition=complete pod/gpu-test --timeout=60s || true

echo ""
echo "4️⃣ nvidia-smi output from pod:"
kubectl logs gpu-test

echo ""
echo "🧹 Cleaning up test pod..."
kubectl delete pod gpu-test --ignore-not-found

echo ""
echo "✅ NVIDIA GPU verification complete."
