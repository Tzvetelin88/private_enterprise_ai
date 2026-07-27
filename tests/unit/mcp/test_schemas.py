"""Unit tests for MCP shared schemas."""
import importlib.util
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

# Load schemas directly from file to avoid mcp package name collision with tests/unit/mcp/
_schemas_path = Path(__file__).parents[3] / "mcp" / "shared" / "schemas.py"
_spec = importlib.util.spec_from_file_location("mcp_shared_schemas", _schemas_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

ToolDefinition = _mod.ToolDefinition
ToolCallRequest = _mod.ToolCallRequest
ToolCallResult = _mod.ToolCallResult


def test_tool_definition_local():
    tool = ToolDefinition(
        name="rag_hybrid_query",
        description="Hybrid RAG pipeline",
        server_type="local",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
    )
    assert tool.server_type == "local"
    assert tool.server_url is None
    assert tool.enabled is True


def test_tool_definition_remote():
    tool = ToolDefinition(
        name="fs_read",
        description="Read files from filesystem",
        server_type="remote",
        server_url="http://mcp-fs:9000",
        input_schema={},
        output_schema={},
    )
    assert tool.server_url == "http://mcp-fs:9000"


def test_tool_definition_invalid_server_type():
    with pytest.raises(ValidationError):
        ToolDefinition(
            name="bad",
            description="bad",
            server_type="unknown",
            input_schema={},
            output_schema={},
        )


def test_tool_call_request_defaults():
    req = ToolCallRequest(tool_name="embed_text")
    assert req.arguments == {}


def test_tool_call_request_with_args():
    req = ToolCallRequest(tool_name="rag_hybrid_query", arguments={"query": "What is pgvector?", "top_k": 3})
    assert req.arguments["top_k"] == 3


def test_tool_call_result_success():
    result = ToolCallResult(tool_name="llm_chat", result={"answer": "Hello"}, latency_ms=120, success=True)
    assert result.success is True
    assert result.error is None


def test_tool_call_result_failure():
    result = ToolCallResult(tool_name="llm_chat", success=False, error="timeout")
    assert result.success is False
    assert result.error == "timeout"
