FROM python:3.11-slim

WORKDIR /app

COPY graph-rag/pyproject.toml .
COPY graph-rag/src/ ./src/
RUN pip install --no-cache-dir . && pip install --no-cache-dir uvicorn

# Copy shared RAG utilities
COPY shared/ /app/shared

ENV PYTHONPATH=/app

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8003"]
