.PHONY: help install dev-install test lint format clean kind-up kind-down gpu-verify deploy-all deploy-stage0 deploy-stage1 deploy-stage2 deploy-stage3

help:
	@echo "Available commands:"
	@echo ""
	@echo "Development:"
	@echo "  make install       - Install production dependencies"
	@echo "  make dev-install   - Install development dependencies"
	@echo "  make test          - Run tests"
	@echo "  make lint          - Run linters (ruff, mypy)"
	@echo "  make format        - Format code (black, ruff)"
	@echo "  make clean         - Clean build artifacts"
	@echo ""
	@echo "Deployment:"
	@echo "  make deploy-all    - Deploy all stages (interactive)"
	@echo "  make deploy-stage0 - Deploy Stage 0 (Foundation)"
	@echo "  make deploy-stage1 - Deploy Stage 1 (Core Infrastructure)"
	@echo "  make deploy-stage2 - Deploy Stage 2 (Model Serving)"
	@echo "  make deploy-stage3 - Deploy Stage 3 (API Gateway)"
	@echo ""
	@echo "Cluster Management:"
	@echo "  make kind-up       - Create kind cluster with GPU support"
	@echo "  make kind-down     - Delete kind cluster"
	@echo "  make gpu-verify    - Verify GPU detection in cluster"

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

kind-up:
	cd infra/kind && bash setup-kind-gpu.sh

kind-down:
	kind delete cluster --name private-ai

gpu-verify:
	bash scripts/verify-gpu.sh

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
