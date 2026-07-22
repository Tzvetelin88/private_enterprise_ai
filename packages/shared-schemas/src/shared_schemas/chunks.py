"""Chunk-related Pydantic models."""
from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class Chunk(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    document_id: uuid.UUID
    content: str
    chunk_index: int
    embedding: list[float] | None = None

    model_config = {"from_attributes": True}


class ChunkCreate(BaseModel):
    document_id: uuid.UUID
    content: str
    chunk_index: int
