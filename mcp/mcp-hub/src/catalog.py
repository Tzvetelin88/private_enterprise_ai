"""CRUD for mcp_tools table."""
from __future__ import annotations

import json
import logging
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)


async def list_tools(pool: asyncpg.Pool) -> list[dict[str, Any]]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id::text, name, description, server_type, server_url, "
            "input_schema, output_schema, enabled, created_at::text FROM mcp_tools ORDER BY created_at ASC"
        )
    return [_row_to_dict(r) for r in rows]


async def get_tool(pool: asyncpg.Pool, name: str) -> dict[str, Any] | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id::text, name, description, server_type, server_url, "
            "input_schema, output_schema, enabled, created_at::text FROM mcp_tools WHERE name = $1",
            name,
        )
    return _row_to_dict(row) if row else None


async def create_tool(pool: asyncpg.Pool, tool: dict[str, Any]) -> dict[str, Any]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO mcp_tools (name, description, server_type, server_url, input_schema, output_schema, enabled)
            VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb, $7)
            RETURNING id::text, name, description, server_type, server_url,
                      input_schema, output_schema, enabled, created_at::text
            """,
            tool["name"],
            tool.get("description"),
            tool["server_type"],
            tool.get("server_url"),
            json.dumps(tool.get("input_schema", {})),
            json.dumps(tool.get("output_schema", {})),
            tool.get("enabled", True),
        )
    return _row_to_dict(row)


async def delete_tool(pool: asyncpg.Pool, name: str) -> bool:
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM mcp_tools WHERE name = $1", name)
    return result != "DELETE 0"


def _row_to_dict(row: asyncpg.Record) -> dict[str, Any]:
    d = dict(row)
    for key in ("input_schema", "output_schema"):
        if isinstance(d.get(key), str):
            d[key] = json.loads(d[key])
    return d
