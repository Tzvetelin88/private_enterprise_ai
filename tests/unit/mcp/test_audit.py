"""Unit tests for MCP Hub audit log functions with mocked asyncpg pool."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_pool():
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
    return pool, conn


@pytest.mark.asyncio
async def test_log_call_success(mock_pool):
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../mcp/mcp-hub/src"))

    pool, conn = mock_pool
    conn.execute = AsyncMock(return_value=None)

    import audit
    await audit.log_call(pool, "rag_hybrid_query", {"query": "test"}, {"answer": "ok"}, 150, True)
    conn.execute.assert_called_once()


@pytest.mark.asyncio
async def test_log_call_failure_does_not_raise(mock_pool):
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../mcp/mcp-hub/src"))

    pool, conn = mock_pool
    conn.execute = AsyncMock(side_effect=Exception("DB down"))

    import audit
    await audit.log_call(pool, "embed_text", {}, None, 0, False, "timeout")


@pytest.mark.asyncio
async def test_list_audit_empty(mock_pool):
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../mcp/mcp-hub/src"))

    pool, conn = mock_pool
    conn.fetch = AsyncMock(return_value=[])

    import audit
    result = await audit.list_audit(pool)
    assert result == []
