"""RAG service — top-level entry point for question answering."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from rag.generator import generate_answer
from rag.retriever import retrieve
from rag.schemas import RagAnswer, RagChunkRef

logger = logging.getLogger(__name__)


def answer_question(
    db: Session,
    query: str,
    *,
    context_type: str | None = None,
    team_id: int | None = None,
    simulation_id: str | None = None,
    max_chunks: int = 5,
) -> RagAnswer:
    """Retrieve relevant context and generate a factual explanation.

    This function NEVER determines match winners. All prediction probabilities
    come from the Elo/ML/Poisson/Monte Carlo prediction engine.

    Args:
        db: Database session
        query: Natural language question (3–500 chars)
        context_type: Optional filter ("team", "player", "model", "tournament", "general")
        team_id: Optional team ID to scope results
        simulation_id: Optional simulation reference for logging
        max_chunks: Maximum number of chunks to retrieve (1–20)

    Returns:
        RagAnswer with answer text, chunk refs, citations, confidence, warnings
    """
    started = time.monotonic()
    now = datetime.now(timezone.utc)

    chunks = retrieve(
        db,
        query,
        max_chunks=max_chunks,
        context_type=context_type,
        team_id=team_id,
    )

    answer_text, confidence, citations, warnings = generate_answer(
        query,
        chunks,
        context_type=context_type,
        team_id=team_id,
        simulation_id=simulation_id,
    )

    sources = list({c.doc_type for c in chunks})
    latency_ms = int((time.monotonic() - started) * 1000)

    _log_query(
        db,
        query=query,
        context_type=context_type,
        team_id=team_id,
        simulation_id=simulation_id,
        chunks_retrieved=len(chunks),
        latency_ms=latency_ms,
        answer_text=answer_text,
        confidence=confidence,
        citations=citations,
        warnings=warnings,
        now=now,
    )

    return RagAnswer(
        answer=answer_text,
        chunks=chunks,
        citations=citations,
        sources=sources,
        confidence=confidence,
        warnings=warnings,
        context_type=context_type,
        team_id=team_id,
        simulation_id=simulation_id,
    )


def _log_query(
    db: Session,
    *,
    query: str,
    context_type: str | None,
    team_id: int | None,
    simulation_id: str | None,
    chunks_retrieved: int,
    latency_ms: int,
    answer_text: str,
    confidence: float,
    citations: list[str],
    warnings: list[str],
    now: datetime,
) -> None:
    """Persist query and answer to DB for analytics (best-effort)."""
    try:
        import json
        from app.models.rag import RagAnswer as RagAnswerModel, RagQuery

        query_row = RagQuery(
            query_text=query,
            context_type=context_type,
            team_id=team_id,
            simulation_id=simulation_id,
            chunks_retrieved=chunks_retrieved,
            latency_ms=latency_ms,
            created_at=now,
        )
        db.add(query_row)
        db.flush()

        answer_row = RagAnswerModel(
            query_id=query_row.id,
            answer_text=answer_text,
            confidence=confidence,
            citations_json=json.dumps(citations),
            warnings_json=json.dumps(warnings),
            sources_json=json.dumps([]),
            created_at=now,
        )
        db.add(answer_row)
        db.commit()
    except Exception as exc:
        logger.warning("Failed to log RAG query: %s", exc)
        db.rollback()
