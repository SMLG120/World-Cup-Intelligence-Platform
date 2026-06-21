"""RAG indexer — builds and persists the document index."""
from __future__ import annotations

import hashlib
import json
import logging
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from rag.chunking import chunk_text, estimate_tokens
from rag.sources import RawDocument, fetch_all_documents

logger = logging.getLogger(__name__)

_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "has", "have", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "this", "that", "these", "those", "it", "its",
    "not", "as", "if", "so", "he", "she", "they", "we", "i", "you",
})


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 1]


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


@dataclass
class _PendingChunk:
    raw_idx: int       # index into raw_docs list
    chunk_index: int
    text: str
    tokens_list: list[str]


def run_index(db: Session, *, force: bool = False) -> dict[str, int]:
    """Two-pass indexer: collect all chunks globally, then compute TF-IDF with
    global IDF so single-chunk documents get meaningful scores.

    Returns counts by doc_type.
    """
    from app.models.rag import RagChunk, RagDocument, RagEmbedding

    raw_docs = fetch_all_documents(db)
    now = datetime.now(timezone.utc)
    counts: dict[str, int] = defaultdict(int)
    skipped = 0

    # ── Pass 1: filter already-indexed docs, create RagDocument rows, collect
    #            all pending chunks WITHOUT storing embeddings yet ─────────────
    pending: list[_PendingChunk] = []          # all chunks across all docs
    doc_rows: list[RagDocument | None] = []    # parallel to raw_docs (None = skipped)

    for raw in raw_docs:
        content_hash = _content_hash(raw.content)
        existing = db.query(RagDocument).filter_by(content_hash=content_hash).first()

        if existing and not force:
            doc_rows.append(None)
            skipped += 1
            continue
        if existing and force:
            db.delete(existing)
            db.flush()

        doc = RagDocument(
            doc_type=raw.doc_type,
            source_ref=raw.source_ref,
            title=raw.title,
            content=raw.content,
            content_hash=content_hash,
            team_id=raw.team_id,
            player_id=raw.player_id,
            indexed_at=now,
            created_at=now,
        )
        db.add(doc)
        db.flush()
        doc_rows.append(doc)
        counts[raw.doc_type] += 1

        for cidx, ctext in enumerate(chunk_text(raw.content)):
            raw_idx = len(doc_rows) - 1
            pending.append(_PendingChunk(
                raw_idx=raw_idx,
                chunk_index=cidx,
                text=ctext,
                tokens_list=_tokenize(ctext),
            ))

    # ── Pass 2: compute GLOBAL IDF across all pending chunks ─────────────────
    n_chunks = max(len(pending), 1)
    global_df: Counter[str] = Counter()
    for pc in pending:
        for term in set(pc.tokens_list):
            global_df[term] += 1

    def _tfidf_weights(tokens: list[str]) -> dict[str, float]:
        tf = Counter(tokens)
        total = max(len(tokens), 1)
        weights: dict[str, float] = {}
        for term, count in tf.items():
            idf = math.log((n_chunks + 1) / (global_df[term] + 1)) + 1.0
            weights[term] = round((count / total) * idf, 6)
        # Keep top-80 terms to preserve specificity
        return dict(sorted(weights.items(), key=lambda x: -x[1])[:80])

    # ── Pass 3: persist chunks + embeddings ──────────────────────────────────
    for pc in pending:
        doc = doc_rows[pc.raw_idx]
        if doc is None:
            continue

        chunk = RagChunk(
            document_id=doc.id,
            chunk_index=pc.chunk_index,
            text=pc.text,
            tokens=estimate_tokens(pc.text),
            created_at=now,
        )
        db.add(chunk)
        db.flush()

        emb = RagEmbedding(
            chunk_id=chunk.id,
            method="tfidf_global",
            tfidf_terms_json=json.dumps(_tfidf_weights(pc.tokens_list)),
            created_at=now,
        )
        db.add(emb)

    db.commit()
    logger.info("RAG index complete: %s new docs, %d chunks, %d skipped",
                dict(counts), len(pending), skipped)
    return dict(counts)
