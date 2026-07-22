"""Configuration for graph-rag service."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "graph-rag"
    app_version: str = "0.1.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8003

    # PostgreSQL + pgvector
    database_url: str = "postgresql://postgres:changeme-postgres-admin@postgres:5432/private_ai"

    # Neo4j
    neo4j_uri: str = "bolt://neo4j:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "changeme-neo4j"

    # Infinity embeddings
    infinity_embeddings_url: str = "http://infinity-embeddings:7997"
    embedding_model: str = "BAAI/bge-small-en-v1.5"

    # Ollama / vLLM
    llm_url: str = "http://host.docker.internal:11434"
    llm_model: str = "llama3.2:3b"
    llm_timeout: int = 120

    # Graph traversal
    traversal_depth: int = 2
    top_k: int = 5

    # Ingestion
    chunk_size: int = 512
    chunk_overlap: int = 64

    class Config:
        env_file = ".env"


settings = Settings()
