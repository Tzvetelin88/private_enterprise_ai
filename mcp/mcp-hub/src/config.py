"""Configuration for mcp-hub service."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "mcp-hub"
    app_version: str = "0.1.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8010

    database_url: str = "postgresql://postgres:changeme-postgres-admin@postgres:5432/private_ai"
    mcp_server_url: str = "http://mcp-server:8011"
    mcp_client_url: str = "http://mcp-client:8012"

    class Config:
        env_file = ".env"


settings = Settings()
