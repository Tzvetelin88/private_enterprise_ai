"""Configuration for agentic-rag service."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "agentic-rag"
    app_version: str = "0.1.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8002

    # PostgreSQL
    database_url: str = "postgresql://postgres:changeme-postgres-admin@postgres:5432/private_ai"

    # Hybrid RAG retriever (internal service)
    hybrid_rag_url: str = "http://hybrid-rag:8001"

    # Infinity services
    infinity_embeddings_url: str = "http://infinity-embeddings:7997"
    infinity_reranker_url: str = "http://infinity-reranker:7998"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"

    # Ollama / vLLM
    llm_url: str = "http://host.docker.internal:11434"
    llm_model: str = "llama3.2:3b"
    llm_timeout: int = 120

    # LangGraph settings
    max_iterations: int = 3

    # Observability
    tracing_backend: str = "langfuse"  # "langfuse" | "langsmith" | "none"
    langfuse_host: str = "http://langfuse:3000"
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langchain_api_key: str = ""
    langchain_project: str = "private-ai"

    # Ingestion
    chunk_size: int = 512
    chunk_overlap: int = 64
    top_k: int = 5

    class Config:
        env_file = ".env"


settings = Settings()
