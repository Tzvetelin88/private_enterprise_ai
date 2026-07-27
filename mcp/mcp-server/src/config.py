"""Configuration for mcp-server service."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "mcp-server"
    app_version: str = "0.1.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8011

    hybrid_rag_url: str = "http://hybrid-rag:8001"
    agentic_rag_url: str = "http://agentic-rag:8002"
    graph_rag_url: str = "http://graph-rag:8003"
    llm_url: str = "http://host.docker.internal:11434"
    llm_model: str = "llama3.2:3b"
    llm_timeout: int = 120
    infinity_embeddings_url: str = "http://infinity-embeddings:7997"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    mcp_hub_url: str = "http://mcp-hub:8010"
    request_timeout: int = 120

    class Config:
        env_file = ".env"


settings = Settings()
