from typing import Any, Literal

from pydantic import BaseModel


class ToolDefinition(BaseModel):
    name: str
    description: str
    server_type: Literal["local", "remote"]
    server_url: str | None = None
    input_schema: dict = {}
    output_schema: dict = {}
    enabled: bool = True


class ToolCallRequest(BaseModel):
    tool_name: str
    arguments: dict[str, Any] = {}


class ToolCallResult(BaseModel):
    tool_name: str
    result: Any = None
    latency_ms: int = 0
    success: bool
    error: str | None = None
