"""add rag tables

Revision ID: c1d2e3f4a5b6
Revises: b5c7a9e1d3f2
Create Date: 2026-06-21 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, None] = "b5c7a9e1d3f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rag_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("doc_type", sa.String(50), nullable=False, index=True),
        sa.Column("source_ref", sa.String(300), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id"), nullable=True, index=True),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id"), nullable=True, index=True),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "rag_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("rag_documents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("tokens", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_rag_chunk_doc_idx"),
    )

    op.create_table(
        "rag_embeddings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chunk_id", sa.Integer(), sa.ForeignKey("rag_chunks.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("method", sa.String(30), nullable=False),
        sa.Column("vector_json", sa.Text(), nullable=True),
        sa.Column("tfidf_terms_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "rag_queries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("context_type", sa.String(50), nullable=True),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("simulation_id", sa.String(100), nullable=True),
        sa.Column("chunks_retrieved", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "rag_answers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("query_id", sa.Integer(), sa.ForeignKey("rag_queries.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("sources_json", sa.Text(), nullable=True),
        sa.Column("citations_json", sa.Text(), nullable=True),
        sa.Column("warnings_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("rag_answers")
    op.drop_table("rag_queries")
    op.drop_table("rag_embeddings")
    op.drop_table("rag_chunks")
    op.drop_table("rag_documents")
