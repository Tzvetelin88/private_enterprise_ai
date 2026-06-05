# Project Context & Decisions

This document captures key project context, decisions, and constraints to save tokens and API calls in future sessions.

## Project Goal

Build a production-ready private enterprise AI platform where organizations can:
- Deploy local LLM models without sending data to external providers
- Run RAG pipelines on internal documents
- Deploy AI agents with tool integration (MCP protocol)
- Maintain enterprise-grade security, multi-tenancy, and observability

## Hardware Environment

**Local Development**:
- GPU: NVIDIA GeForce RTX 4060 Laptop GPU
- VRAM: 8GB dedicated + 8GB shared (16GB total)
- Single GPU configuration

**Design Principle**: GPU-agnostic architecture
- Works with single RTX 4060 (8GB VRAM)
- Scales to multi-GPU enterprise setups (A100, H100, etc.)
- Configurable via Helm values

## Key Technology Decisions

### Infrastructure
- **Kubernetes Distribution**: kind (Kubernetes IN Docker) for local dev
  - Rationale: Real Kubernetes, runs locally in Docker, production-identical
  - Alternative considered: minikube (rejected - kind preferred for multi-node support)
- **Deployment Strategy**: Everything in Kubernetes
  - Rationale: Production parity, no Docker Compose/K8s hybrid complexity
  - All services deploy via Helm charts

### AI Stack
- **LLM Inference**: vLLM (primary), llama.cpp (fallback)
  - Rationale: vLLM optimized for throughput, llama.cpp for CPU fallback
- **Initial Model**: Llama-3.2-3B
  - Rationale: Fits in 8GB VRAM, good quality/size tradeoff
  - Configurable for larger models (7B, 13B, 70B) via Helm values
- **Embeddings**: Infinity embeddings server
  - Model: bge-small-en-v1.5 (or configurable)
- **Vector DB**: PostgreSQL + pgvector
  - Rationale: Unified data storage, simpler ops vs standalone vector DB
  - Alternative considered: Qdrant, Weaviate (rejected - added complexity)

### Backend
- **Language**: Python 3.11+
  - Rationale: Rapid development, rich AI ecosystem
  - Future: Optional Go services for performance-critical components
- **Framework**: FastAPI
  - Rationale: Async support, auto-docs, type validation, high performance

### Observability
- **Stack**: Prometheus + Grafana + Loki + Tempo
- **GPU Metrics**: NVIDIA DCGM exporter
- **Tracing**: OpenTelemetry

### Security
- **Identity**: Keycloak (OIDC/SSO)
- **Secrets**: HashiCorp Vault
- **Multi-tenancy**: Namespace isolation + row-level security in PostgreSQL

## Development Approach

### Stage-Gate Process
1. Complete one stage at a time
2. User reviews and tests
3. Approval required before next stage
4. No assumptions - ask questions if unclear

### Principles
- **Ask, Don't Hallucinate**: If something is unknown, ask for clarification
- **Production Quality**: No MVP shortcuts, build for production from day 1
- **Configuration-Driven**: Make everything configurable (model size, GPU allocation, etc.)
- **Documentation**: Keep context in files to save tokens in future sessions

### Code Quality Standards
- **Human-Readable Code**: Write code naturally, as humans would
- **Minimal Comments**: Add comments only where necessary for clarity
- **Clean & Structured**: Keep code organized, well-structured, and maintainable
- **Pythonic/Idiomatic**: Follow language best practices and conventions

## Previous Review Summary

From earlier assessment of `private_enterprise_ai_services_plan.md`:

**Strengths**:
- ✅ Well-structured microservices architecture
- ✅ Solid technology choices (vLLM, pgvector, FastAPI)
- ✅ Proper phased approach (MVP → Enterprise → Agents → Production)
- ✅ Good GPU strategy (vGPU/MIG + GPU Operator)
- ✅ Comprehensive observability stack

**Minor Suggestions Incorporated**:
- Model versioning strategy documented in Harbor section
- Ray/Ray Serve noted as future consideration for distributed inference
- Alternatives (Weaviate, Qdrant) documented but sticking with pgvector for simplicity

## Questions & Answers Log

**Q**: How many GPUs available?  
**A**: Single RTX 4060 Laptop (8GB VRAM), but design must scale to multi-GPU

**Q**: Which Kubernetes distribution?  
**A**: kind for local dev, production-ready for any K8s cluster

**Q**: Model sizes to support?  
**A**: Start with Llama-3.2-3B, configurable for larger models

**Q**: Docker Compose vs all-in-Kubernetes?  
**A**: All in Kubernetes for production readiness

**Q**: Additional service needed (K3s)?  
**A**: No, kind IS Kubernetes - no additional service needed

## File Organization

All context and decisions stored in:
- `IMPLEMENTATION_PLAN.md`: Stage-by-stage build plan
- `docs/tech/*.md`: Technology reference (3 sentences per tech)
- `docs/PROJECT_CONTEXT.md`: This file - ongoing context
- `private_enterprise_ai_services_plan.md`: Original detailed plan (reference)

## MCP Catalog & Agent Management Design

### Design Principle: API-First, UI-Ready

All agent and MCP tool management is **configuration-driven via REST API**:

**Benefits**:
- Easy to configure programmatically
- All config stored in PostgreSQL (no YAML files to manage)
- Future UI can be added without backend changes
- Audit logging built-in
- Multi-tenant isolation enforced at API level

**Key Features**:
1. **Tool Registry**: Register MCP servers (filesystem, database, web, custom)
2. **Access Control**: Enable/disable tools per tenant
3. **Agent Creation**: Create agents via API with specific tool permissions
4. **Rate Limiting**: Control tool usage per tenant
5. **Audit Log**: Track all configuration changes
6. **Validation**: Server-side validation for all configurations

**Future UI Integration**:
- Admin dashboard for tool management
- Tenant dashboard for agent creation
- Visual permission matrix (tenants × tools)
- Audit log timeline view
- Agent execution monitoring

**Example Use Cases**:
- Admin enables "filesystem" MCP tool for Engineering team only
- Data team creates agent with postgres + filesystem access
- Security team disables web-browsing MCP globally
- All changes logged and auditable

See Stage 10 in IMPLEMENTATION_PLAN.md for detailed API design.

### Agent Framework Strategy

**Multi-Framework Support with Shared RAG Layer**:

**Architecture**:
```
Agent API
  ↓
AgentExecutor (interface)
  ├─ LangChainExecutor ──┐
  └─ NeMoExecutor ───────┼─→ Both use LlamaIndex for RAG/data tasks
                         │
                    LlamaIndex
                    (Shared RAG Layer)
```

**Agent Frameworks (choose one per agent)**:
1. **LangChain** - Default, open source, mature ecosystem
2. **NVIDIA NeMo** - Enterprise option, GPU-optimized, advanced multi-agent

**RAG/Data Layer (shared by both)**:
- **LlamaIndex** - Indexing, retrieval, data connectors
- Not a framework choice, it's a shared library
- Both LangChain and NeMo agents use it for RAG operations

**Design Pattern**: Abstraction layer (AgentExecutor interface)
- Common API for all frameworks
- Framework selected when creating agent (`"framework": "langchain"` or `"nemo"`)
- LlamaIndex integration available to both
- UI shows framework selector dropdown

**When to Use Each**:
- **LangChain**: Most use cases, community support, flexibility
- **NeMo**: Enterprise deployments, GPU optimization, NVIDIA ecosystem

**Benefits**:
- Users choose best framework for their use case
- No vendor lock-in
- Shared RAG layer (no duplication)
- Can benchmark and compare frameworks

See Stage 10 (LangChain + LlamaIndex) and Stage 11 (add NeMo) in IMPLEMENTATION_PLAN.md.

## Current Status

**Stage**: Stage 0 - Foundation Setup
**Status**: Complete
**Next Action**: Review Stage 0, then proceed to Stage 1
**Last Updated**: 2026-05-24

## Notes

- Keep pgvector for now (user decision)
- No references to SVG/PNG files per user request
- All documentation tight and concise (tech docs max 3 sentences)
- Project designed for local PC but production-scalable
