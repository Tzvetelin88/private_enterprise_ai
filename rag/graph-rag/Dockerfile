FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir -e . && pip install --no-cache-dir uvicorn

# Copy shared RAG utilities and service source
COPY ../../shared /app/shared
COPY src/ ./src/

ENV PYTHONPATH=/app

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8003"]
