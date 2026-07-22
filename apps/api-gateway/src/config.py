"""Configuration management for API Gateway."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Application
    app_name: str = "Private AI - API Gateway"
    app_version: str = "0.1.0"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # vLLM / Ollama Backend
    vllm_url: str = "http://localhost:8000"
    vllm_timeout: int = 300

    # Infinity Embeddings Backend
    infinity_url: str = "http://infinity-embeddings:7997"
    infinity_timeout: int = 60

    # RAG Service Backends
    hybrid_rag_url: str = "http://hybrid-rag:8001"
    agentic_rag_url: str = "http://agentic-rag:8002"
    graph_rag_url: str = "http://graph-rag:8003"
    rag_timeout: int = 120

    # Observability
    enable_metrics: bool = True
    enable_tracing: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
