"""RAG retriever — keyword/TF-IDF search over indexed chunks."""
from __future__ import annotations

import json
import logging
import re
from collections import Counter

from sqlalchemy.orm import Session

from rag.schemas import RagChunkRef

logger = logging.getLogger(__name__)

_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "has", "have", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "this", "that", "these", "those", "it", "its",
    "not", "as", "if", "so",
})


_TERM_EXPANSION: dict[str, list[str]] = {
    "goalkeeper": ["gk", "goalkeeper"],
    "goalkeepers": ["gk", "goalkeeper"],
    "keeper": ["gk"],
    "striker": ["fwd", "striker", "forward"],
    "strikers": ["fwd", "striker", "forward"],
    "forward": ["fwd", "forward"],
    "forwards": ["fwd", "forward"],
    "midfielder": ["mid", "midfielder"],
    "midfielders": ["mid", "midfielder"],
    "defender": ["def", "defender"],
    "defenders": ["def", "defender"],
    "attack": ["attack", "fwd"],
    "defence": ["defence", "def"],
    "defense": ["defence", "def"],
    "ranking": ["rank", "ranking", "fifa"],
    "ratings": ["rating", "elo"],
    "elo": ["elo", "rating"],
    "coach": ["coach", "manager"],
    "manager": ["coach", "manager"],
    "formation": ["formation", "tactical"],
    "squad": ["squad", "players", "team"],
    "roster": ["squad", "players", "team"],
    "chance": ["probability", "champion"],
    "chances": ["probability", "champion"],
    "win": ["champion", "probability", "win"],
    "probability": ["probability", "champion", "win"],
}


def _expand_query(tokens: list[str]) -> list[str]:
    """Expand query tokens with domain synonyms."""
    expanded: list[str] = []
    for t in tokens:
        expanded.append(t)
        if t in _TERM_EXPANSION:
            expanded.extend(_TERM_EXPANSION[t])
    return expanded


def _tokenize_query(query: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", query.lower())
    filtered = [t for t in tokens if t not in _STOPWORDS and len(t) > 1]
    return _expand_query(filtered)


def retrieve(
    db: Session,
    query: str,
    *,
    max_chunks: int = 5,
    context_type: str | None = None,
    team_id: int | None = None,
) -> list[RagChunkRef]:
    """Return top-k chunks ranked by TF-IDF cosine-like score against the query."""
    from app.models.rag import RagChunk, RagDocument, RagEmbedding

    query_terms = _tokenize_query(query)
    if not query_terms:
        return []

    q = (
        db.query(RagChunk, RagDocument, RagEmbedding)
        .join(RagDocument, RagChunk.document_id == RagDocument.id)
        .join(RagEmbedding, RagEmbedding.chunk_id == RagChunk.id)
    )

    if context_type and context_type != "general":
        q = q.filter(RagDocument.doc_type == context_type)

    if team_id is not None:
        q = q.filter(
            (RagDocument.team_id == team_id) |
            (RagDocument.doc_type.in_(["model", "tournament"]))
        )

    rows = q.all()
    if not rows:
        # Fallback: no filter
        rows = (
            db.query(RagChunk, RagDocument, RagEmbedding)
            .join(RagDocument, RagChunk.document_id == RagDocument.id)
            .join(RagEmbedding, RagEmbedding.chunk_id == RagChunk.id)
            .all()
        )

    scored: list[tuple[float, RagChunk, RagDocument]] = []
    query_counter = Counter(query_terms)

    for chunk, doc, emb in rows:
        tfidf: dict[str, float] = {}
        if emb.tfidf_terms_json:
            try:
                tfidf = json.loads(emb.tfidf_terms_json)
            except Exception:
                pass

        score = sum(
            tfidf.get(term, 0.0) * count
            for term, count in query_counter.items()
        )

        # Boost exact phrase match
        if query.lower() in chunk.text.lower():
            score += 2.0

        # Boost by doc_type relevance to query terms
        if any(t in query.lower() for t in ["team", "squad", "coach"]) and doc.doc_type in ("team", "coach"):
            score += 0.5
        if any(t in query.lower() for t in ["player", "players", "striker", "goalkeeper", "midfielder"]) and doc.doc_type == "player":
            score += 0.5

        if score > 0:
            scored.append((score, chunk, doc))

    scored.sort(key=lambda x: -x[0])
    top = scored[:max_chunks]

    return [
        RagChunkRef(
            chunk_id=chunk.id,
            document_id=doc.id,
            doc_type=doc.doc_type,
            title=doc.title,
            text=chunk.text,
            score=round(score, 4),
        )
        for score, chunk, doc in top
    ]
