FROM python:3.11-slim

WORKDIR /app

COPY mcp-hub/pyproject.toml .
COPY mcp-hub/src/ ./src/
RUN pip install --no-cache-dir . && pip install --no-cache-dir uvicorn

# Copy shared MCP utilities (observability, registry client, schemas)
COPY shared/ /app/shared

ENV PYTHONPATH=/app

EXPOSE 8010

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8010"]
