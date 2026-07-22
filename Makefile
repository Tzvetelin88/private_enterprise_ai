.PHONY: help install dev-install test lint format clean \
        kind-up kind-up-mac kind-up-nvidia kind-down \
        model-server model-server-mac model-server-nvidia \
        gpu-verify deploy-all deploy-stage0 deploy-stage1 deploy-stage2 deploy-stage3 deploy-stage4 \
        deploy-hybrid-rag deploy-agentic-rag deploy-graph-rag \
        deploy-stage0-nvidia deploy-stage2-nvidia deploy-all-nvidia

help:
	@echo "Available commands:"
	@echo ""
	@echo "Development:"
	@echo "  make install            - Install production dependencies"
	@echo "  make dev-install        - Install development dependencies"
	@echo "  make test               - Run tests"
	@echo "  make lint               - Run linters (ruff, mypy)"
	@echo "  make format             - Format code (black, ruff)"
	@echo "  make clean              - Clean build artifacts"
	@echo ""
	@echo "Cluster Management:"
	@echo "  make kind-up            - Create kind cluster (Mac default, no GPU mounts)"
	@echo "  make kind-up-mac        - Create kind cluster for Mac / ARM64"
	@echo "  make kind-up-nvidia     - Create kind cluster with NVIDIA GPU mounts (Linux)"
	@echo "  make kind-down          - Delete kind cluster"
	@echo ""
	@echo "Model Server:"
	@echo "  make model-server       - Start model server (Mac default → Ollama)"
	@echo "  make model-server-mac   - Start Ollama (Mac / M-series, Metal accelerated)"
	@echo "  make model-server-nvidia - Start vLLM locally (NVIDIA GPU, Linux)"
	@echo ""
	@echo "Compute Verification:"
	@echo "  make gpu-verify         - Check GPU / compute (platform-aware)"
	@echo ""
	@echo "Deployment — Mac (default):"
	@echo "  make deploy-all         - Deploy all stages (Mac)"
	@echo "  make deploy-stage0      - Stage 0: kind cluster (Mac)"
	@echo "  make deploy-stage1      - Stage 1: Core Infrastructure"
	@echo "  make deploy-stage2      - Stage 2: Model server via Ollama (Mac)"
	@echo "  make deploy-stage3      - Stage 3: API Gateway"
	@echo "  make deploy-stage4      - Stage 4: Infinity Embeddings Service"
	@echo ""
	@echo "Deployment — NVIDIA GPU (Linux):"
	@echo "  make deploy-all-nvidia  - Deploy all stages (NVIDIA)"
	@echo "  make deploy-stage0-nvidia - Stage 0: kind cluster + GPU Operator"
	@echo "  make deploy-stage2-nvidia - Stage 2: vLLM in cluster (NVIDIA)"

install:
	pip install -e .

dev-install:
	pip install -e ".[dev]"
	pre-commit install

test:
	pytest

lint:
	ruff check apps packages tests
	mypy apps packages

format:
	black apps packages tests
	ruff check --fix apps packages tests

clean:
	rm -rf build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# ── Cluster ────────────────────────────────────────────────────────────────────

kind-up: kind-up-mac

kind-up-mac:
	cd infra/kind && bash setup-kind.sh

kind-up-nvidia:
	cd infra/kind && bash setup-kind-gpu.sh

kind-down:
	kind delete cluster --name private-ai

# ── Model server ───────────────────────────────────────────────────────────────

model-server: model-server-mac

model-server-mac:
	bash scripts/run-ollama-local.sh

model-server-nvidia:
	bash scripts/run-vllm-local.sh

# ── Compute check ──────────────────────────────────────────────────────────────

gpu-verify:
	bash scripts/verify-gpu.sh

# ── Deployment — Mac (default) ─────────────────────────────────────────────────

deploy-all:
	bash scripts/install-all.sh all

deploy-stage0:
	bash scripts/install-all.sh 0

deploy-stage1:
	bash scripts/install-all.sh 1

deploy-stage2:
	bash scripts/install-all.sh 2

deploy-stage3:
	bash scripts/install-all.sh 3

deploy-stage4:
	bash scripts/install-stage4.sh

# ── Deployment — NVIDIA GPU ────────────────────────────────────────────────────

deploy-hybrid-rag:
	bash scripts/install-stage5-hybrid.sh

deploy-agentic-rag:
	bash scripts/install-stage5-agentic.sh

deploy-graph-rag:
	bash scripts/install-stage5-graph.sh

deploy-all-nvidia:
	GPU_MODE=nvidia bash scripts/install-all.sh all

deploy-stage0-nvidia:
	GPU_MODE=nvidia bash scripts/install-all.sh 0

deploy-stage2-nvidia:
	GPU_MODE=nvidia bash scripts/install-all.sh 2
