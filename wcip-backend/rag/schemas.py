"""Pydantic schemas for RAG request/response."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RagChunkRef(BaseModel):
    chunk_id: int
    document_id: int
    doc_type: str
    title: str
    text: str
    score: float = 0.0


class RagAnswer(BaseModel):
    answer: str
    chunks: list[RagChunkRef] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    warnings: list[str] = Field(default_factory=list)
    context_type: str | None = None
    team_id: int | None = None
    simulation_id: str | None = None


class RagAskRequest(BaseModel):
    query: str = Field(min_length=3, max_length=500)
    context_type: str | None = None  # "team", "player", "tournament", "model", "general"
    team_id: int | None = None
    simulation_id: str | None = None
    max_chunks: int = Field(default=5, ge=1, le=20)


class RagIndexStatus(BaseModel):
    total_documents: int
    total_chunks: int
    doc_types: dict[str, int]
    last_indexed_at: str | None = None
    index_method: str = "tfidf"


class RagDocumentSummary(BaseModel):
    id: int
    doc_type: str
    title: str
    source_ref: str
    indexed_at: str
    chunk_count: int = 0
