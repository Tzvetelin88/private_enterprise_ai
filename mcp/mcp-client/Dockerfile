FROM python:3.11-slim

WORKDIR /app

COPY mcp-client/pyproject.toml .
COPY mcp-client/src/ ./src/
RUN pip install --no-cache-dir . && pip install --no-cache-dir uvicorn

ENV PYTHONPATH=/app

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8012"]
