"""Redis LLM response cache for LangChain pipelines.

Sets the global LangChain LLM cache so that identical prompts sent to any
LangChain LLM (ChatOllama, etc.) are served from Redis instead of re-invoking
the model.  This is a zero-change optimisation — no node code needs updating.

Usage (call once at service startup):

    from shared.cache.redis_cache import setup_llm_cache
    setup_llm_cache(redis_url="redis://redis:6379", ttl=3600)

If Redis is unavailable the function logs a warning and returns without raising,
so LLM calls degrade gracefully to direct model invocation.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def setup_llm_cache(redis_url: str, ttl: int = 3600) -> bool:
    """Configure the global LangChain LLM cache to use Redis.

    Args:
        redis_url: Redis connection URL, e.g. ``redis://redis:6379``.
        ttl:       Cache entry time-to-live in seconds (default: 1 hour).

    Returns:
        True if the cache was successfully configured, False otherwise.
    """
    try:
        # langchain>=1.0 removed the old `langchain.llm_cache` module attribute
        # (and the `langchain.globals` compat module entirely) — the global
        # cache now lives in langchain_core and must be set via set_llm_cache().
        # Assigning `langchain.llm_cache = ...` directly is a silent no-op on
        # langchain>=1.0: it creates an unused attribute on the module instead
        # of registering the cache anywhere a chat model actually looks it up.
        from langchain_core.globals import set_llm_cache  # type: ignore[import-untyped]
        from langchain_community.cache import RedisCache  # type: ignore[import-untyped]
        from redis import Redis  # type: ignore[import-untyped]

        client = Redis.from_url(redis_url, socket_connect_timeout=3, socket_timeout=3)
        # Verify the connection before enabling the cache
        client.ping()
        set_llm_cache(RedisCache(redis_=client, ttl=ttl))
        logger.info("Redis LLM cache enabled → %s (TTL=%ds)", redis_url, ttl)
        return True
    except ImportError as exc:
        logger.warning("Redis/langchain-community not installed — LLM cache disabled: %s", exc)
        return False
    except Exception as exc:
        logger.warning("Redis unavailable (%s) — LLM cache disabled; LLM calls will run normally", exc)
        return False
