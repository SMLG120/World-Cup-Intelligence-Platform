"""RAG answer generator — assembles answers from retrieved chunks.

This module generates template-based explanations from retrieved facts.
It NEVER determines match winners — all probability figures come from
prediction endpoints. Generator only formats and explains retrieved data.
"""
from __future__ import annotations

from rag.schemas import RagChunkRef


_DISCLAIMER = (
    "Note: This analysis is based on retrieved statistical data and is for "
    "educational purposes only. Match outcomes are determined by separate "
    "Elo/ML/Monte Carlo prediction models, not by this explanation."
)


def generate_answer(
    query: str,
    chunks: list[RagChunkRef],
    *,
    context_type: str | None = None,
    team_id: int | None = None,
    simulation_id: str | None = None,
) -> tuple[str, float, list[str], list[str]]:
    """Generate an answer string from retrieved chunks.

    Returns: (answer_text, confidence, citations, warnings)
    """
    if not chunks:
        return (
            "I couldn't find relevant data for that query. "
            "Try asking about a specific team, player, or tournament group.",
            0.0,
            [],
            ["No matching documents found in the knowledge base."],
        )

    top_chunk = chunks[0]
    query_lower = query.lower()

    # Determine answer strategy by context
    if _is_prediction_query(query_lower):
        answer = _handle_prediction_query(query, chunks)
        warnings = [
            "Win/loss predictions are provided by the ML prediction engine, not RAG. "
            "Visit the Simulate page for match outcome probabilities."
        ]
    elif context_type == "player" or _is_player_query(query_lower):
        answer = _handle_player_query(query, chunks)
        warnings = []
    elif context_type == "team" or _is_team_query(query_lower):
        answer = _handle_team_query(query, chunks)
        warnings = []
    elif context_type == "model" or _is_model_query(query_lower):
        answer = _handle_model_query(query, chunks)
        warnings = []
    else:
        answer = _handle_general_query(query, chunks)
        warnings = []

    # Append disclaimer
    answer = answer.rstrip() + f"\n\n{_DISCLAIMER}"

    confidence = _estimate_confidence(chunks)
    citations = list({c.title for c in chunks[:3]})

    return answer, confidence, citations, warnings


def _is_prediction_query(q: str) -> bool:
    keywords = ["who will win", "who wins", "chance", "probability", "predict", "favorite", "favourite", "beat"]
    return any(k in q for k in keywords)


def _is_player_query(q: str) -> bool:
    keywords = ["player", "players", "striker", "goalkeeper", "midfielder", "defender", "squad", "roster", "caps", "goals"]
    return any(k in q for k in keywords)


def _is_team_query(q: str) -> bool:
    keywords = ["team", "elo", "ranking", "confederation", "coach", "formation", "attack", "defence"]
    return any(k in q for k in keywords)


def _is_model_query(q: str) -> bool:
    keywords = ["model", "ml", "machine learning", "catboost", "xgboost", "ensemble", "poisson", "monte carlo", "elo"]
    return any(k in q for k in keywords)


def _handle_prediction_query(query: str, chunks: list[RagChunkRef]) -> str:
    context = "\n\n".join(c.text for c in chunks[:3])
    return (
        f"Here is the statistical background relevant to your query:\n\n"
        f"{context}\n\n"
        f"For actual win/draw/loss probabilities, please use the Simulate or Predict pages "
        f"which run Elo-based Poisson + Monte Carlo models."
    )


def _handle_player_query(query: str, chunks: list[RagChunkRef]) -> str:
    lines = []
    for chunk in chunks[:4]:
        if chunk.doc_type == "player":
            lines.append(chunk.text)
    if not lines:
        lines = [c.text for c in chunks[:3]]
    return "\n\n---\n\n".join(lines)


def _handle_team_query(query: str, chunks: list[RagChunkRef]) -> str:
    lines = []
    for chunk in chunks[:4]:
        if chunk.doc_type in ("team", "coach", "tournament"):
            lines.append(chunk.text)
    if not lines:
        lines = [c.text for c in chunks[:3]]
    return "\n\n---\n\n".join(lines)


def _handle_model_query(query: str, chunks: list[RagChunkRef]) -> str:
    model_chunks = [c for c in chunks if c.doc_type == "model"]
    others = [c for c in chunks if c.doc_type != "model"]
    combined = (model_chunks + others)[:4]
    return "\n\n---\n\n".join(c.text for c in combined)


def _handle_general_query(query: str, chunks: list[RagChunkRef]) -> str:
    return "\n\n---\n\n".join(c.text for c in chunks[:4])


def _estimate_confidence(chunks: list[RagChunkRef]) -> float:
    if not chunks:
        return 0.0
    top_score = chunks[0].score
    if top_score >= 3.0:
        return 0.90
    if top_score >= 1.5:
        return 0.75
    if top_score >= 0.5:
        return 0.55
    if top_score > 0:
        return 0.35
    return 0.15
