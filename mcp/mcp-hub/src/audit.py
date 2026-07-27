"""Audit log — record every tool call in mcp_audit_log."""
from __future__ import annotations

import json
import logging
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)


async def log_call(
    pool: asyncpg.Pool,
    tool_name: str,
    input_data: dict[str, Any],
    output_data: Any,
    latency_ms: int,
    success: bool,
    error: str | None = None,
) -> None:
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO mcp_audit_log (tool_name, input, output, latency_ms, success, error)
                VALUES ($1, $2::jsonb, $3::jsonb, $4, $5, $6)
                """,
                tool_name,
                json.dumps(input_data),
                json.dumps(output_data),
                latency_ms,
                success,
                error,
            )
    except Exception as e:
        logger.error(f"Audit log write failed: {e}")


async def list_audit(pool: asyncpg.Pool, limit: int = 100) -> list[dict[str, Any]]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, tool_name, input, output, latency_ms, success, error, called_at::text "
            "FROM mcp_audit_log ORDER BY called_at DESC LIMIT $1",
            limit,
        )
    result = []
    for row in rows:
        d = dict(row)
        for key in ("input", "output"):
            if isinstance(d.get(key), str):
                import json as _json
                d[key] = _json.loads(d[key])
        result.append(d)
    return result
