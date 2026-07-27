FROM python:3.11-slim

WORKDIR /app

COPY mcp-server/pyproject.toml .
COPY mcp-server/src/ ./src/
RUN pip install --no-cache-dir . && pip install --no-cache-dir uvicorn

ENV PYTHONPATH=/app

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8011"]
