"""RAG (Retrieval-Augmented Generation) API endpoints.

These endpoints provide explanation and retrieval services.
RAG never determines match winners — predictions come exclusively from the
Elo/ML/Poisson/Monte Carlo prediction engine.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status

from app.core.deps import AdminUser, DbSession
from rag.indexer import run_index
from rag.schemas import (
    RagAskRequest,
    RagAnswer,
    RagDocumentSummary,
    RagIndexStatus,
)
from rag.service import answer_question

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["rag"])
admin_router = APIRouter(prefix="/admin/rag", tags=["rag-admin"])


@admin_router.post("/index", response_model=dict)
def index_documents(
    db: DbSession,
    _admin: AdminUser,
    force: bool = False,
) -> dict:
    """Rebuild the RAG index from all safe data sources.

    Admin-only. Set force=true to re-index documents that haven't changed.
    """
    try:
        counts = run_index(db, force=force)
    except Exception as exc:
        logger.exception("RAG indexing failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Indexing failed: {exc}",
        ) from exc
    return {"status": "ok", "indexed": counts, "force": force}


@router.post("/ask", response_model=RagAnswer)
def ask_question(
    request: RagAskRequest,
    db: DbSession,
) -> RagAnswer:
    """Ask a natural language question about teams, players, or the tournament.

    Returns a factual answer assembled from indexed documents.
    This endpoint NEVER returns win/loss predictions — use /simulations for that.
    """
    return answer_question(
        db,
        request.query,
        context_type=request.context_type,
        team_id=request.team_id,
        simulation_id=request.simulation_id,
        max_chunks=request.max_chunks,
    )


@router.get("/status", response_model=RagIndexStatus)
def get_index_status(db: DbSession) -> RagIndexStatus:
    """Return counts of indexed documents and chunks."""
    from app.models.rag import RagChunk, RagDocument
    from sqlalchemy import func

    total_documents = db.query(RagDocument).count()
    total_chunks = db.query(RagChunk).count()

    type_rows = (
        db.query(RagDocument.doc_type, func.count(RagDocument.id))
        .group_by(RagDocument.doc_type)
        .all()
    )
    doc_types = {row[0]: row[1] for row in type_rows}

    last_doc = (
        db.query(RagDocument.indexed_at)
        .order_by(RagDocument.indexed_at.desc())
        .first()
    )
    last_indexed_at = last_doc[0].isoformat() if last_doc else None

    return RagIndexStatus(
        total_documents=total_documents,
        total_chunks=total_chunks,
        doc_types=doc_types,
        last_indexed_at=last_indexed_at,
        index_method="tfidf",
    )


@router.get("/documents", response_model=list[RagDocumentSummary])
def list_documents(
    db: DbSession,
    doc_type: str | None = None,
    limit: int = 50,
) -> list[RagDocumentSummary]:
    """List indexed RAG documents with metadata."""
    from app.models.rag import RagChunk, RagDocument
    from sqlalchemy import func

    q = db.query(
        RagDocument,
        func.count(RagChunk.id).label("chunk_count"),
    ).outerjoin(RagChunk, RagChunk.document_id == RagDocument.id)

    if doc_type:
        q = q.filter(RagDocument.doc_type == doc_type)

    q = q.group_by(RagDocument.id).limit(limit)
    rows = q.all()

    return [
        RagDocumentSummary(
            id=doc.id,
            doc_type=doc.doc_type,
            title=doc.title,
            source_ref=doc.source_ref,
            indexed_at=doc.indexed_at.isoformat(),
            chunk_count=chunk_count or 0,
        )
        for doc, chunk_count in rows
    ]
