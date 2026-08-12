FROM python:3.11-slim

WORKDIR /app

# curl needed for the docker-compose healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY agentic-rag/pyproject.toml .
COPY agentic-rag/src/ ./src/
RUN pip install --no-cache-dir . && pip install --no-cache-dir uvicorn

# Copy shared RAG utilities
COPY shared/ /app/shared

ENV PYTHONPATH=/app

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8002"]
