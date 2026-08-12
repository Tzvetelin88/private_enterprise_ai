"""Unit tests for the Redis LLM response cache helper.

Tests that setup_llm_cache() correctly configures the LangChain global
cache via langchain_core.globals.set_llm_cache() — NOT the old
`langchain.llm_cache` module attribute, which is a silent no-op on
langchain>=1.0 (the attribute doesn't exist there; langchain.globals was
removed too). Also tests that it handles a missing Redis connection
gracefully, and returns the right boolean result in each scenario.
"""
import sys
import os
from unittest.mock import MagicMock, patch

import pytest

# Ensure shared module is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../rag"))

from shared.cache.redis_cache import setup_llm_cache  # noqa: E402


class TestSetupLlmCache:
    """setup_llm_cache() — configures global LangChain cache via set_llm_cache()."""

    def test_returns_true_on_success(self):
        """When Redis is reachable, setup_llm_cache returns True."""
        mock_redis_instance = MagicMock()
        mock_redis_instance.ping.return_value = True

        mock_redis_class = MagicMock(return_value=mock_redis_instance)
        mock_redis_class.from_url = MagicMock(return_value=mock_redis_instance)

        mock_redis_cache = MagicMock()
        mock_set_llm_cache = MagicMock()

        with patch.dict("sys.modules", {
            "redis": MagicMock(Redis=mock_redis_class),
            "langchain_community.cache": MagicMock(RedisCache=MagicMock(return_value=mock_redis_cache)),
            "langchain_core.globals": MagicMock(set_llm_cache=mock_set_llm_cache),
        }):
            result = setup_llm_cache("redis://localhost:6379", ttl=60)

        assert result is True

    def test_calls_set_llm_cache_with_redis_cache_instance(self):
        """When Redis is reachable, set_llm_cache() is called with the RedisCache instance.

        This is the actual fix: langchain>=1.0 removed `langchain.llm_cache`
        and the `langchain.globals` compat module — the only way to register
        a global cache that chat models will consult is set_llm_cache() from
        langchain_core.globals. Directly assigning an attribute on the
        `langchain` module (the old approach) is a silent no-op there.
        """
        mock_redis_instance = MagicMock()
        mock_redis_instance.ping.return_value = True

        mock_redis_class = MagicMock()
        mock_redis_class.from_url = MagicMock(return_value=mock_redis_instance)

        mock_redis_cache_instance = MagicMock()
        mock_redis_cache_class = MagicMock(return_value=mock_redis_cache_instance)
        mock_set_llm_cache = MagicMock()

        with patch.dict("sys.modules", {
            "redis": MagicMock(Redis=mock_redis_class),
            "langchain_community.cache": MagicMock(RedisCache=mock_redis_cache_class),
            "langchain_core.globals": MagicMock(set_llm_cache=mock_set_llm_cache),
        }):
            setup_llm_cache("redis://localhost:6379", ttl=300)

        mock_set_llm_cache.assert_called_once_with(mock_redis_cache_instance)

    def test_returns_false_when_redis_unreachable(self):
        """When Redis ping raises, setup_llm_cache returns False without raising."""
        mock_redis_instance = MagicMock()
        mock_redis_instance.ping.side_effect = ConnectionError("Connection refused")

        mock_redis_class = MagicMock()
        mock_redis_class.from_url = MagicMock(return_value=mock_redis_instance)

        with patch.dict("sys.modules", {
            "redis": MagicMock(Redis=mock_redis_class),
            "langchain_community.cache": MagicMock(),
            "langchain_core.globals": MagicMock(set_llm_cache=MagicMock()),
        }):
            result = setup_llm_cache("redis://localhost:6379")

        assert result is False

    def test_returns_false_when_redis_not_installed(self):
        """When redis package is not installed, returns False gracefully."""
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "redis":
                raise ImportError("No module named 'redis'")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = setup_llm_cache("redis://localhost:6379")

        assert result is False

    def test_does_not_raise_on_any_exception(self):
        """setup_llm_cache never propagates exceptions — always returns bool."""
        mock_redis_class = MagicMock()
        mock_redis_class.from_url = MagicMock(side_effect=RuntimeError("unexpected error"))

        with patch.dict("sys.modules", {
            "redis": MagicMock(Redis=mock_redis_class),
            "langchain_community.cache": MagicMock(),
            "langchain_core.globals": MagicMock(set_llm_cache=MagicMock()),
        }):
            result = setup_llm_cache("redis://localhost:6379")

        assert result is False

    def test_custom_ttl_passed_to_redis_cache(self):
        """TTL parameter is forwarded to RedisCache constructor."""
        mock_redis_instance = MagicMock()
        mock_redis_instance.ping.return_value = True

        mock_redis_class = MagicMock()
        mock_redis_class.from_url = MagicMock(return_value=mock_redis_instance)

        mock_redis_cache_class = MagicMock(return_value=MagicMock())

        with patch.dict("sys.modules", {
            "redis": MagicMock(Redis=mock_redis_class),
            "langchain_community.cache": MagicMock(RedisCache=mock_redis_cache_class),
            "langchain_core.globals": MagicMock(set_llm_cache=MagicMock()),
        }):
            setup_llm_cache("redis://localhost:6379", ttl=7200)

        # Verify RedisCache was constructed with ttl=7200
        mock_redis_cache_class.assert_called_once_with(
            redis_=mock_redis_instance, ttl=7200
        )
