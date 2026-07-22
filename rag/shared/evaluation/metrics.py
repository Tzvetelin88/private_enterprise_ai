"""RAGAS-style faithfulness and relevance evaluation helpers.

These are lightweight, LLM-free approximations suitable for unit tests and
CI-time smoke checks. For full RAGAS evaluation, install the `ragas` package
and use its official metrics.
"""
from __future__ import annotations

import math
import re
from collections import Counter


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\b\w+\b", text.lower())


def _cosine_token_similarity(a: str, b: str) -> float:
    """Token-overlap cosine similarity between two strings."""
    tokens_a = Counter(_tokenize(a))
    tokens_b = Counter(_tokenize(b))
    if not tokens_a or not tokens_b:
        return 0.0
    dot = sum(tokens_a[t] * tokens_b[t] for t in tokens_a if t in tokens_b)
    norm_a = math.sqrt(sum(v * v for v in tokens_a.values()))
    norm_b = math.sqrt(sum(v * v for v in tokens_b.values()))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


def faithfulness(answer: str, sources: list[str]) -> float:
    """Approximate faithfulness: how well the answer is grounded in the sources.

    Score in [0, 1]. Higher = more grounded.
    This is a simple token-overlap heuristic, not an LLM judge.
    """
    if not sources:
        return 0.0
    combined_source = " ".join(sources)
    return _cosine_token_similarity(answer, combined_source)


def answer_relevance(answer: str, query: str) -> float:
    """Approximate answer relevance: how well the answer addresses the query.

    Score in [0, 1]. Higher = more relevant.
    """
    return _cosine_token_similarity(answer, query)


def context_recall(retrieved: list[str], ground_truth_chunks: list[str]) -> float:
    """Approximate context recall: fraction of ground-truth chunks covered by retrieved chunks."""
    if not ground_truth_chunks:
        return 1.0
    covered = sum(
        1
        for gt in ground_truth_chunks
        if any(_cosine_token_similarity(gt, ret) > 0.5 for ret in retrieved)
    )
    return covered / len(ground_truth_chunks)
