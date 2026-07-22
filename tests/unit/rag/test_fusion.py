"""Unit tests for RRF fusion logic."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "rag" / "hybrid-rag" / "src"))

from retriever import rrf_fusion, _rrf_score


def test_rrf_score_decreases_with_rank():
    assert _rrf_score([1]) > _rrf_score([2]) > _rrf_score([10])


def test_rrf_score_sums_over_lists():
    # Doc appearing in both lists gets higher score than appearing in one
    assert _rrf_score([1, 1]) > _rrf_score([1])


def test_rrf_fusion_empty_lists():
    assert rrf_fusion([], [], top_k=5) == []


def test_rrf_fusion_deduplicates():
    doc = {"id": "abc", "content": "text", "score": 0.9}
    result = rrf_fusion([doc], [doc], top_k=5)
    # Same doc in both lists → merged into one entry
    assert len(result) == 1


def test_rrf_fusion_returns_top_k():
    docs = [{"id": str(i), "content": f"doc{i}", "score": 0.5} for i in range(10)]
    result = rrf_fusion(docs, [], top_k=3)
    assert len(result) == 3


def test_rrf_fusion_higher_ranked_first():
    dense = [{"id": "a", "content": "a", "score": 0.9}, {"id": "b", "content": "b", "score": 0.1}]
    bm25 = [{"id": "a", "content": "a", "score": 5.0}]
    result = rrf_fusion(dense, bm25, top_k=2)
    # "a" appears in both lists → should score higher than "b"
    assert result[0]["id"] == "a"
