FROM python:3.11-slim

WORKDIR /app

# System deps for pypdf, python-docx
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Copy pyproject and src before install (src layout requires src/ present at install time)
COPY hybrid-rag/pyproject.toml .
COPY hybrid-rag/src/ ./src/
RUN pip install --no-cache-dir . && pip install --no-cache-dir uvicorn

# Copy shared RAG utilities
COPY shared/ /app/shared

ENV PYTHONPATH=/app

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8001"]
