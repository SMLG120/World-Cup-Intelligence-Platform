"""RAG edge-case tests."""
from __future__ import annotations

import json

from sqlalchemy import delete

from app.db.base import SessionLocal
from app.models.rag import RagAnswer, RagChunk, RagDocument, RagEmbedding, RagQuery


def _clear_rag_tables() -> None:
    db = SessionLocal()
    try:
        db.execute(delete(RagAnswer))
        db.execute(delete(RagQuery))
        db.execute(delete(RagEmbedding))
        db.execute(delete(RagChunk))
        db.execute(delete(RagDocument))
        db.commit()
    finally:
        db.close()


def _seed_bosnia_doc() -> None:
    db = SessionLocal()
    try:
        doc = RagDocument(
            doc_type="team",
            source_ref="test:bosnia",
            title="Team profile - Bosnia and Herzegovina",
            content=(
                "Team: Bosnia and Herzegovina (BIH)\n"
                "Coach: Sergej Barbarez\n"
                "Squad includes Edin Dzeko, Amar Dedic, and Sead Kolasinac."
            ),
            content_hash="test-bosnia-rag-doc",
        )
        db.add(doc)
        db.flush()
        chunk = RagChunk(
            document_id=doc.id,
            chunk_index=0,
            text=doc.content,
            tokens=18,
        )
        db.add(chunk)
        db.flush()
        db.add(
            RagEmbedding(
                chunk_id=chunk.id,
                method="tfidf",
                tfidf_terms_json=json.dumps({
                    "bosnia": 2.0,
                    "herzegovina": 2.0,
                    "bih": 2.0,
                    "squad": 1.5,
                    "coach": 1.5,
                    "barbarez": 1.5,
                    "dzeko": 1.5,
                }),
            )
        )
        db.commit()
    finally:
        db.close()


def test_rag_empty_index_returns_clear_low_confidence_answer(client):
    _clear_rag_tables()
    response = client.post("/api/v1/rag/ask", json={"query": "Who will win the bracket?"})
    assert response.status_code == 200
    body = response.json()
    assert body["chunks"] == []
    assert body["confidence"] == 0
    assert "No matching documents found" in body["warnings"][0]
    assert any("Predict" in warning or "Simulate" in warning for warning in body["warnings"])


def test_rag_no_matching_chunks_warns_without_crashing(client):
    _clear_rag_tables()
    _seed_bosnia_doc()
    response = client.post("/api/v1/rag/ask", json={"query": "zzzxqv impossible term"})
    assert response.status_code == 200
    body = response.json()
    assert body["chunks"] == []
    assert body["confidence"] == 0
    assert body["citations"] == []


def test_rag_bih_alias_retrieves_bosnia_document(client):
    _clear_rag_tables()
    _seed_bosnia_doc()
    response = client.post("/api/v1/rag/ask", json={"query": "BIH squad coach"})
    assert response.status_code == 200
    body = response.json()
    assert body["chunks"]
    assert body["citations"] == ["Team profile - Bosnia and Herzegovina"]
    assert "Sergej Barbarez" in body["answer"]


def test_rag_prediction_query_keeps_prediction_boundary(client):
    _clear_rag_tables()
    _seed_bosnia_doc()
    response = client.post("/api/v1/rag/ask", json={"query": "Can Bosnia win the final?"})
    assert response.status_code == 200
    body = response.json()
    assert any("prediction engine" in warning for warning in body["warnings"])
    assert "not by this explanation" in body["answer"]


def test_rag_admin_index_requires_authentication(client):
    response = client.post("/api/v1/admin/rag/index")
    assert response.status_code in {401, 403}
