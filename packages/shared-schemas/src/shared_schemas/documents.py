"""Document-related Pydantic models."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DocumentCreate(BaseModel):
    name: str
    content_type: str | None = None
    rag_type: Literal["hybrid", "agentic", "graph"] | None = None


class Document(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    content_type: str | None = None
    status: Literal["pending", "indexed", "failed"] = "pending"
    rag_type: Literal["hybrid", "agentic", "graph"] | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"from_attributes": True}
