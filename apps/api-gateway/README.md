# API Gateway

FastAPI-based API Gateway for Private Enterprise AI Platform.

## Features

- OpenAI-compatible API endpoints
- Request routing to vLLM backend
- Prometheus metrics exposed at `/metrics`
- Health checks at `/health`
- OpenTelemetry instrumentation ready

## Quick Start

### Local Development

1. **Install dependencies:**
```bash
pip install -e .
```

2. **Start vLLM backend:**
```bash
# In another terminal
bash ../../scripts/run-vllm-local.sh
```

3. **Run API Gateway:**
```bash
# Copy env example
cp .env.example .env

# Start server
python -m uvicorn src.main:app --host 0.0.0.0 --port 8080 --reload
```

4. **Test endpoints:**
```bash
# Health check
curl http://localhost:8080/health

# List models
curl http://localhost:8080/v1/models

# Chat completion
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "meta-llama/Llama-3.2-3B-Instruct",
    "messages": [{"role": "user", "content": "What is AI?"}],
    "max_tokens": 100
  }'
```

### Kubernetes Deployment

```bash
# Build Docker image
docker build -t api-gateway:latest .

# Deploy to cluster
helm install api-gateway ../../infra/helm/api-gateway

# Access via NodePort
curl http://localhost:30880/health
```

## Configuration

Environment variables (see `.env.example`):

- `VLLM_URL` - vLLM backend URL (default: `http://localhost:8000`)
- `PORT` - Server port (default: `8000`)
- `DEBUG` - Enable debug mode (default: `false`)
- `ENABLE_METRICS` - Enable Prometheus metrics (default: `true`)
- `ENABLE_TRACING` - Enable OpenTelemetry tracing (default: `true`)

## API Endpoints

### Health & Status

- `GET /health` - Health check
- `GET /metrics` - Prometheus metrics

### OpenAI-Compatible

- `GET /v1/models` - List available models
- `POST /v1/chat/completions` - Chat completions (streaming supported)
- `POST /v1/completions` - Text completions

## Architecture

```
Client Request
      ↓
API Gateway (FastAPI)
      ↓
vLLM Backend
      ↓
Llama-3.2-3B Model
      ↓
Response
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check .
mypy .
```
