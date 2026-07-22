"""Fixed-size text chunker with configurable overlap."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Chunk:
    content: str
    index: int
    start_char: int
    end_char: int
    metadata: dict = field(default_factory=dict)


def chunk_text(
    text: str,
    chunk_size: int = 512,
    overlap: int = 64,
) -> list[Chunk]:
    """Split text into fixed-size chunks with the given overlap.

    Args:
        text: Input text to chunk.
        chunk_size: Maximum number of characters per chunk.
        overlap: Number of characters to repeat at the start of the next chunk.

    Returns:
        List of Chunk objects in order.
    """
    if not text:
        return []

    chunks: list[Chunk] = []
    start = 0
    index = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))
        content = text[start:end].strip()
        if content:
            chunks.append(Chunk(content=content, index=index, start_char=start, end_char=end))
            index += 1
        start += chunk_size - overlap

    return chunks
