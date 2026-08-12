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
    llm_model: str = "qwen3.5:4b"
    llm_timeout: int = 120
    # Fallback LLM model used transparently when the primary model is unreachable
    fallback_llm_model: str = "llama3.2:3b"
    # Reasoning/"thinking" mode for models that support it (e.g. Qwen3.5).
    # False disables it — grading/rewriting/generation here don't need extended
    # chain-of-thought, and thinking mode can 50-100x the token count (and
    # latency) for trivial outputs. Set LLM_REASONING_ENABLED=true to re-enable,
    # or override per-model in Ollama's Modelfile if you want it always-on.
    llm_reasoning_enabled: bool = False

    # LangGraph settings
    max_iterations: int = 3
    # HITL: pause the workflow before the generate node for human approval
    hitl_enabled: bool = False
    # Checkpointing: persist workflow state to PostgreSQL via AsyncPostgresSaver
    checkpointing_enabled: bool = True

    # Redis LLM response cache
    redis_url: str = "redis://redis:6379"
    llm_cache_ttl: int = 3600  # seconds

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
