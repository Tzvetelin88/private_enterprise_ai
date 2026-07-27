"""LLM chat tool implementation."""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


async def llm_chat(arguments: dict[str, Any], llm_url: str, llm_model: str, timeout: int) -> Any:
    messages = arguments.get("messages", [])
    if isinstance(arguments.get("message"), str):
        messages = [{"role": "user", "content": arguments["message"]}]

    payload = {
        "model": llm_model,
        "messages": messages,
        "stream": False,
    }
    async with httpx.AsyncClient(base_url=llm_url, timeout=timeout) as client:
        response = await client.post("/v1/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()
        return {"answer": data["choices"][0]["message"]["content"]}
