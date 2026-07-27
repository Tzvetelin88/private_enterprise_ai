"""Configuration for mcp-client service."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "mcp-client"
    app_version: str = "0.1.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8012
    request_timeout: int = 60

    class Config:
        env_file = ".env"


settings = Settings()
