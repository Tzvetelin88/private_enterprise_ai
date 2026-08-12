"""Configuration for hybrid-rag service."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "hybrid-rag"
    app_version: str = "0.1.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8001

    # PostgreSQL + pgvector
    database_url: str = "postgresql://postgres:changeme-postgres-admin@postgres:5432/private_ai"

    # Elasticsearch (BM25)
    elasticsearch_url: str = "http://elasticsearch:9200"
    elasticsearch_index: str = "documents"

    # Infinity services
    infinity_embeddings_url: str = "http://infinity-embeddings:7997"
    infinity_reranker_url: str = "http://infinity-reranker:7998"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"

    # Ollama / vLLM for generation
    llm_url: str = "http://host.docker.internal:11434"
    llm_model: str = "qwen3.5:4b"
    llm_timeout: int = 120

    # Retrieval settings
    top_k: int = 5
    chunk_size: int = 512
    chunk_overlap: int = 64

    class Config:
        env_file = ".env"


settings = Settings()
