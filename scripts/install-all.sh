#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     Private Enterprise AI Platform - Full Installation         ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

STAGE=${1:-all}

function run_stage0() {
    echo "═══════════════════════════════════════════════════════════════"
    echo "  STAGE 0: Foundation Setup"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""

    cd "$PROJECT_ROOT/infra/kind"
    bash setup-kind-gpu.sh

    echo ""
    cd "$PROJECT_ROOT/infra/k8s"
    bash install-gpu-operator.sh

    echo ""
    cd "$PROJECT_ROOT"
    bash scripts/verify-gpu.sh

    echo ""
    echo "✅ Stage 0 Complete: Foundation Setup"
    echo ""
}

function run_stage1() {
    echo "═══════════════════════════════════════════════════════════════"
    echo "  STAGE 1: Core Infrastructure"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""

    cd "$PROJECT_ROOT"
    bash scripts/install-stage1.sh

    echo ""
    echo "✅ Stage 1 Complete: Core Infrastructure"
    echo ""
}

function run_stage2() {
    echo "═══════════════════════════════════════════════════════════════"
    echo "  STAGE 2: Model Serving (vLLM + Infinity)"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""

    cd "$PROJECT_ROOT"
    if [ -f scripts/install-stage2.sh ]; then
        bash scripts/install-stage2.sh
        echo ""
        echo "✅ Stage 2 Complete: Model Serving"
    else
        echo "⚠️  Stage 2 script not yet implemented"
    fi
    echo ""
}

function run_stage3() {
    echo "═══════════════════════════════════════════════════════════════"
    echo "  STAGE 3: API Gateway"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""

    cd "$PROJECT_ROOT"
    if [ -f scripts/install-stage3.sh ]; then
        bash scripts/install-stage3.sh
        echo ""
        echo "✅ Stage 3 Complete: API Gateway"
    else
        echo "⚠️  Stage 3 script not yet implemented"
    fi
    echo ""
}

case "$STAGE" in
    0|stage0)
        run_stage0
        ;;
    1|stage1)
        run_stage1
        ;;
    2|stage2)
        run_stage2
        ;;
    3|stage3)
        run_stage3
        ;;
    all)
        run_stage0
        read -p "Stage 0 complete. Continue to Stage 1? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            run_stage1

            read -p "Stage 1 complete. Continue to Stage 2? (y/n) " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                run_stage2

                read -p "Stage 2 complete. Continue to Stage 3? (y/n) " -n 1 -r
                echo
                if [[ $REPLY =~ ^[Yy]$ ]]; then
                    run_stage3
                fi
            fi
        fi
        ;;
    *)
        echo "Usage: $0 [stage]"
        echo ""
        echo "Stages:"
        echo "  0, stage0  - Foundation Setup (kind + GPU Operator)"
        echo "  1, stage1  - Core Infrastructure (PostgreSQL + Observability)"
        echo "  2, stage2  - Model Serving (vLLM + Infinity)"
        echo "  3, stage3  - API Gateway"
        echo "  all        - Run all stages with confirmation prompts (default)"
        echo ""
        echo "Examples:"
        echo "  $0           # Run all stages interactively"
        echo "  $0 0         # Run only Stage 0"
        echo "  $0 stage1    # Run only Stage 1"
        exit 1
        ;;
esac

echo "═══════════════════════════════════════════════════════════════"
echo "  Installation Complete!"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "📊 Access Points:"
echo "  Grafana:    http://localhost:30030 (admin/admin)"
echo "  Prometheus: http://localhost:30090"
echo "  PostgreSQL: <WSL2_IP>:30432 (postgres/changeme-postgres-admin)"
echo ""
echo "🔍 Verify installation:"
echo "  kubectl get pods --all-namespaces"
echo "  kubectl get nodes -o wide"
echo ""
