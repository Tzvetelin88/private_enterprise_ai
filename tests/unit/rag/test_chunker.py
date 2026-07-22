"""Unit tests for the shared chunker."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "rag"))

from shared.ingestion.chunker import chunk_text


def test_empty_text_returns_no_chunks():
    assert chunk_text("") == []


def test_short_text_single_chunk():
    chunks = chunk_text("Hello world", chunk_size=512, overlap=64)
    assert len(chunks) == 1
    assert chunks[0].content == "Hello world"
    assert chunks[0].index == 0


def test_long_text_produces_multiple_chunks():
    text = "word " * 300  # 1500 chars
    chunks = chunk_text(text, chunk_size=512, overlap=64)
    assert len(chunks) > 1


def test_overlap_produces_shared_content():
    text = "a" * 600
    chunks = chunk_text(text, chunk_size=512, overlap=100)
    assert len(chunks) >= 2
    # Second chunk should start before 512 (overlap at work)
    assert chunks[1].start_char < 512


def test_chunk_indices_sequential():
    text = "x " * 500
    chunks = chunk_text(text, chunk_size=200, overlap=20)
    for i, chunk in enumerate(chunks):
        assert chunk.index == i
