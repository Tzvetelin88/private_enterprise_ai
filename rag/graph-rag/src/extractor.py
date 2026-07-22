"""LLM-based entity and relationship extraction for Graph RAG."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_EXTRACTION_PROMPT = """\
Extract all named entities and relationships from the following text.

Return ONLY a JSON object with this exact structure:
{{
  "entities": ["entity1", "entity2", ...],
  "relationships": [
    {{"src": "entity1", "rel": "RELATIONSHIP_TYPE", "dst": "entity2"}},
    ...
  ]
}}

Rules:
- Entity names must be concise (1-4 words), lowercase with hyphens for spaces
- Relationship types must be UPPERCASE with underscores (e.g. CALLS, DEPENDS_ON, CONTAINS)
- Include only clearly stated relationships, not inferred ones
- Return an empty list if no entities/relationships are found

Text:
{text}

JSON response:"""


async def extract_entities_and_relationships(
    text: str,
    llm_url: str,
    llm_model: str,
    llm_timeout: int = 120,
) -> dict[str, Any]:
    """Call the LLM to extract entities and relationships from text.

    Returns dict with keys 'entities' (list[str]) and 'relationships' (list[dict]).
    """
    prompt = _EXTRACTION_PROMPT.format(text=text[:4000])  # limit context length

    async with httpx.AsyncClient(base_url=llm_url, timeout=llm_timeout) as client:
        try:
            resp = await client.post(
                "/v1/chat/completions",
                json={
                    "model": llm_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning(f"LLM extraction failed ({e}) — returning empty")
            return {"entities": [], "relationships": []}

    return _parse_extraction(content)


def _parse_extraction(content: str) -> dict[str, Any]:
    """Parse LLM output, tolerating common formatting issues."""
    json_match = re.search(r"\{.*\}", content, re.DOTALL)
    if not json_match:
        logger.warning(f"No JSON found in LLM extraction output: {content[:200]}")
        return {"entities": [], "relationships": []}

    try:
        parsed = json.loads(json_match.group())
        entities = [str(e).lower().replace(" ", "-") for e in parsed.get("entities", [])]
        relationships = [
            {
                "src": str(r.get("src", "")).lower().replace(" ", "-"),
                "rel": str(r.get("rel", "RELATED_TO")).upper().replace(" ", "_"),
                "dst": str(r.get("dst", "")).lower().replace(" ", "-"),
            }
            for r in parsed.get("relationships", [])
            if r.get("src") and r.get("dst")
        ]
        return {"entities": entities, "relationships": relationships}
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse error in extraction: {e}")
        return {"entities": [], "relationships": []}
