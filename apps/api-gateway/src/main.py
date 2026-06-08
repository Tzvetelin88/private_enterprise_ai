"""Main FastAPI application for API Gateway."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app
import httpx

from src.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# HTTP client for vLLM
http_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    global http_client

    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"vLLM backend: {settings.vllm_url}")

    http_client = httpx.AsyncClient(
        base_url=settings.vllm_url,
        timeout=settings.vllm_timeout,
    )

    yield

    # Shutdown
    if http_client:
        await http_client.aclose()
    logger.info("Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "api-gateway"}


# List models
@app.get("/v1/models")
async def list_models():
    """List available models."""
    if not http_client:
        return JSONResponse(
            status_code=503,
            content={"error": "Service initializing"}
        )

    try:
        response = await http_client.get("/v1/models")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        logger.error(f"Error fetching models: {e}")
        return JSONResponse(
            status_code=503,
            content={"error": "vLLM backend unavailable"}
        )


# Chat completions
@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """OpenAI-compatible chat completions endpoint."""
    if not http_client:
        return JSONResponse(
            status_code=503,
            content={"error": "Service initializing"}
        )

    try:
        body = await request.json()
        response = await http_client.post("/v1/chat/completions", json=body)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        logger.error(f"Error in chat completion: {e}")
        return JSONResponse(
            status_code=503,
            content={"error": "vLLM backend error"}
        )


# Text completions
@app.post("/v1/completions")
async def completions(request: Request):
    """OpenAI-compatible completions endpoint."""
    if not http_client:
        return JSONResponse(
            status_code=503,
            content={"error": "Service initializing"}
        )

    try:
        body = await request.json()
        response = await http_client.post("/v1/completions", json=body)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        logger.error(f"Error in completion: {e}")
        return JSONResponse(
            status_code=503,
            content={"error": "vLLM backend error"}
        )


# Mount Prometheus metrics
if settings.enable_metrics:
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
