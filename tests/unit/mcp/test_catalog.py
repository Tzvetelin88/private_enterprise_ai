"""Unit tests for MCP Hub catalog functions with mocked asyncpg pool."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_pool():
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
    return pool, conn


@pytest.mark.asyncio
async def test_list_tools_empty(mock_pool):
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../mcp/mcp-hub/src"))
    
    pool, conn = mock_pool
    conn.fetch = AsyncMock(return_value=[])

    import importlib
    import catalog as cat
    result = await cat.list_tools(pool)
    assert result == []


@pytest.mark.asyncio
async def test_get_tool_not_found(mock_pool):
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../mcp/mcp-hub/src"))
    
    pool, conn = mock_pool
    conn.fetchrow = AsyncMock(return_value=None)

    import catalog as cat
    result = await cat.get_tool(pool, "nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_delete_tool_not_found(mock_pool):
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../mcp/mcp-hub/src"))
    
    pool, conn = mock_pool
    conn.execute = AsyncMock(return_value="DELETE 0")

    import catalog as cat
    result = await cat.delete_tool(pool, "nonexistent")
    assert result is False


@pytest.mark.asyncio
async def test_delete_tool_success(mock_pool):
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../mcp/mcp-hub/src"))
    
    pool, conn = mock_pool
    conn.execute = AsyncMock(return_value="DELETE 1")

    import catalog as cat
    result = await cat.delete_tool(pool, "rag_hybrid_query")
    assert result is True
