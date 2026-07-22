"""asyncpg connection pool helper."""
from __future__ import annotations

import asyncpg

_pool: asyncpg.Pool | None = None


async def init_pool(dsn: str, min_size: int = 2, max_size: int = 10) -> asyncpg.Pool:
    """Create and store a connection pool. Call once at application startup."""
    global _pool
    _pool = await asyncpg.create_pool(dsn, min_size=min_size, max_size=max_size)
    return _pool


async def get_pool() -> asyncpg.Pool:
    """Return the active pool; raises if not initialised."""
    if _pool is None:
        raise RuntimeError("Database pool not initialised — call init_pool() first")
    return _pool


async def close_pool() -> None:
    """Close the pool on application shutdown."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
