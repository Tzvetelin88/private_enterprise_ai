# System Overview

This document provides a comprehensive view of the Private Enterprise AI Platform architecture, component relationships, and infrastructure setup.

## Project Structure

```
private_ai/
├── apps/              # Microservices
├── packages/          # Shared libraries
├── infra/
│   ├── kind/         # Local Kubernetes cluster config
│   ├── k8s/          # Kubernetes manifests
│   └── helm/         # Helm charts
├── docs/             # Documentation
├── scripts/          # Utility scripts
└── tests/            # Test suites
```

## Infrastructure Layer

### Kubernetes Platform
- **Local Development**: kind (Kubernetes IN Docker)
  - Runs real Kubernetes cluster inside Docker containers
  - Each node is a Docker container
  - Production-identical behavior
  - Configuration: `infra/kind/kind-config.yaml`

### GPU Layer
Managed by **NVIDIA GPU Operator** - automated GPU infrastructure management:

- **NVIDIA Drivers**: Auto-installs drivers in Kubernetes nodes (if needed)
- **NVIDIA Container Toolkit**: Enables containers to access GPUs
- **Device Plugin**: Exposes GPUs to Kubernetes scheduler
  - Tells K8s "this node has X GPUs available"
  - Enables resource requests like `nvidia.com/gpu: 1`
- **DCGM Exporter**: Exports GPU metrics to Prometheus
  - Temperature, utilization, memory usage
  - Power consumption, clock speeds
- **GPU Sharing/Scheduling**: Manages GPU allocation across pods
  - Multiple pods can request GPU resources
  - Time-slicing for GPU sharing

**Without GPU Operator**: Manual installation of all components on every node
**With GPU Operator**: Single installation, everything automated

Configuration: `infra/k8s/gpu-operator-values.yaml`

### Helm Chart Structure
Base chart: `infra/helm/private-ai/`
- **Chart.yaml**: Metadata and version
- **values.yaml**: Configuration (models, resources, features)
- **templates/**: Kubernetes manifests
- **_helpers.tpl**: Template functions

## Component Map

### Stage 0 Components (Completed)
- ✅ kind cluster with GPU support
- ✅ NVIDIA GPU Operator
- ✅ Base Helm chart structure
- ✅ Python development environment

### Stage 1 Components (Completed)
- ✅ PostgreSQL + pgvector (vector database)
- ✅ Prometheus (metrics collection)
- ✅ Grafana (visualization and dashboards)

### Planned Components (Future Stages)
- vLLM (LLM inference)
- Infinity (embeddings)
- API Gateway
- RAG Service
- Agent Service
- MCP Catalog
- Keycloak (auth)
- Vault (secrets)
- Loki (logs), Tempo (traces)

## Development Environment

### Python Setup
- **Version**: 3.11+
- **Build System**: setuptools
- **Dependency Management**: pip with pyproject.toml
- **Code Quality**:
  - black (formatting)
  - ruff (linting)
  - mypy (type checking)
  - pytest (testing)

### Quick Commands
```bash
make dev-install    # Install dev dependencies
make kind-up        # Create cluster
make gpu-verify     # Verify GPU detection
make test           # Run tests
make lint           # Check code quality
make format         # Format code
```

### Data Storage Layer

**PostgreSQL + pgvector**:
- **Primary Database**: All application data (documents, users, tenants)
- **Vector Storage**: Embeddings for semantic search
- **pgvector Extension**: Vector similarity search with HNSW indexing
- **Multi-tenancy**: Row-level tenant isolation

**Database Schema**:
- `tenants` - Organization/team isolation
- `documents` - Uploaded files metadata
- `chunks` - Document segments for RAG
- `embeddings` - Vector representations (384-dim for bge-small-en-v1.5)

**Vector Index**: HNSW (Hierarchical Navigable Small World)
- Fast approximate nearest neighbor search
- Optimized for large-scale vector retrieval
- Cosine similarity metric

Configuration: `infra/helm/private-ai/values-postgresql.yaml`

### Observability Stack

**Prometheus** (Metrics):
- Scrapes metrics from all services
- GPU metrics from DCGM Exporter
- PostgreSQL metrics
- Kubernetes cluster metrics
- 15-day retention
- Configuration: `infra/helm/private-ai/values-prometheus.yaml`

**Grafana** (Visualization):
- Pre-configured dashboards:
  - GPU Metrics (utilization, memory, temperature, power)
  - Kubernetes Cluster Overview (pods, CPU, memory)
- Data source: Prometheus
- Access: http://localhost:30030 (admin/admin)
- Configuration: `infra/helm/private-ai/values-grafana.yaml`

**Metrics Collected**:
- GPU: `DCGM_FI_DEV_GPU_UTIL`, `DCGM_FI_DEV_FB_USED`, `DCGM_FI_DEV_GPU_TEMP`, `DCGM_FI_DEV_POWER_USAGE`
- Kubernetes: Pod status, CPU usage, memory usage
- PostgreSQL: Connections, query performance, replication lag

## Data Flow (To Be Implemented)
Coming in future stages:
- User → API Gateway → Services
- RAG: Document → Embeddings → pgvector → Retrieval → LLM
- Agent: Request → Agent Service → MCP Tools → LLM → Response

## Service Dependencies (Current)

```
Grafana → Prometheus → DCGM Exporter (GPU Operator)
                    → PostgreSQL Metrics
                    → Kubernetes Metrics
```

## Security Architecture (To Be Implemented)
Coming in future stages

---

**Last Updated**: Stage 1 - Core Infrastructure (2026-05-24)
