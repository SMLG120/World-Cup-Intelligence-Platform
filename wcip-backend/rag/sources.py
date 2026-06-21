"""RAG data sources — fetch DB records and convert to indexable text documents.

Security: This module NEVER reads .env files, credentials, API keys, JWT secrets,
local file paths with passwords, or any auth tokens. Only public factual data
(team stats, player rosters, match info, model metadata) is indexed.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_SECRET_FIELDS = frozenset({
    "password", "secret", "token", "api_key", "jwt", "credential",
    "database_url", "db_url", "auth", "private_key", "access_key",
})


@dataclass
class RawDocument:
    doc_type: str      # "team", "player", "coach", "match", "model", "doc"
    source_ref: str    # human-readable origin reference
    title: str
    content: str
    team_id: int | None = None
    player_id: int | None = None


def _safe(value: object) -> str:
    """Convert value to string, suppressing None."""
    return "" if value is None else str(value)


def fetch_team_documents(db: Session) -> list[RawDocument]:
    from app.models.team import Team
    docs: list[RawDocument] = []
    for team in db.query(Team).all():
        text = (
            f"Team: {team.name} ({team.code})\n"
            f"Confederation: {team.confederation}\n"
            f"Elo rating: {team.elo:.1f}\n"
            f"FIFA ranking: {team.fifa_rank}\n"
            f"Attack multiplier: {team.attack:.2f}\n"
            f"Defence multiplier: {team.defence:.2f}\n"
            f"Chemistry: {team.chemistry:.2f}\n"
            f"Coach quality score: {team.coach_quality:.2f}"
        )
        docs.append(RawDocument(
            doc_type="team",
            source_ref=f"db:teams:{team.id}",
            title=f"Team profile — {team.name}",
            content=text,
            team_id=team.id,
        ))
    return docs


def fetch_player_documents(db: Session) -> list[RawDocument]:
    from app.models.player import Player
    docs: list[RawDocument] = []
    for player in db.query(Player).all():
        injury_note = ""
        if player.injured:
            injury_note = f" [INJURED: {_safe(player.injury_notes) or 'details unavailable'}]"
        elif player.suspended:
            injury_note = " [SUSPENDED]"

        text = (
            f"Player: {player.name}\n"
            f"Team: {player.team_name}\n"
            f"Position: {player.position}\n"
            f"Club: {_safe(player.club)}\n"
            f"Age: {_safe(player.age)}\n"
            f"International caps: {player.international_caps}\n"
            f"International goals: {player.international_goals}\n"
            f"Player rating: {_safe(player.player_rating)}\n"
            f"EA FC rating: {_safe(player.ea_fc_rating)}\n"
            f"Goals this tournament: {player.goals}\n"
            f"Assists: {player.assists}\n"
            f"xG: {player.xg:.2f}, xAG: {player.xag:.2f}\n"
            f"Recent form score: {player.recent_form_score:.2f}\n"
            f"Fitness score: {player.fitness_score:.2f}"
            f"{injury_note}"
        )
        if player.profile_description:
            text += f"\nProfile: {player.profile_description}"

        docs.append(RawDocument(
            doc_type="player",
            source_ref=f"db:players:{player.id}",
            title=f"Player profile — {player.name} ({player.team_name})",
            content=text,
            player_id=player.id,
        ))
    return docs


def fetch_coach_documents(db: Session) -> list[RawDocument]:
    from app.models.player import Coach
    docs: list[RawDocument] = []
    for coach in db.query(Coach).all():
        text = (
            f"Coach: {coach.name}\n"
            f"Team: {coach.team_name}\n"
            f"Nationality: {_safe(coach.nationality)}\n"
            f"Preferred formation: {_safe(coach.preferred_formation)}\n"
            f"Win rate: {coach.win_pct:.1%}\n"
            f"Draw rate: {coach.draw_pct:.1%}\n"
            f"Loss rate: {coach.loss_pct:.1%}\n"
            f"Matches managed: {coach.matches_managed}\n"
            f"World Cup tournaments managed: {coach.tournament_experience}\n"
            f"Knockout stage win rate: {coach.knockout_record:.1%}\n"
            f"Tactical flexibility score: {coach.tactical_flexibility:.2f}\n"
            f"Recent form score: {coach.recent_form_score:.2f}\n"
            f"Impact score: {coach.impact_score:.2f}"
        )
        docs.append(RawDocument(
            doc_type="coach",
            source_ref=f"db:coaches:{coach.id}",
            title=f"Coach profile — {coach.name} ({coach.team_name})",
            content=text,
        ))
    return docs


def fetch_wc2026_group_documents(db: Session) -> list[RawDocument]:
    """Index WC2026 group stage assignments."""
    try:
        from sqlalchemy import text
        rows = db.execute(text(
            "SELECT t.name, t.code, q.group_letter, t.elo, t.fifa_rank "
            "FROM qualified_teams q JOIN teams t ON q.team_id = t.id "
            "ORDER BY q.group_letter, t.fifa_rank"
        )).fetchall()
    except Exception as exc:
        logger.warning("Could not fetch WC2026 group data: %s", exc)
        return []

    groups: dict[str, list[str]] = {}
    for row in rows:
        letter = row[2] or "?"
        groups.setdefault(letter, []).append(
            f"  {row[0]} ({row[1]}) — Elo {row[3]:.0f}, FIFA rank #{row[4]}"
        )

    docs: list[RawDocument] = []
    for letter, entries in sorted(groups.items()):
        text = f"FIFA World Cup 2026 — Group {letter}\n" + "\n".join(entries)
        docs.append(RawDocument(
            doc_type="tournament",
            source_ref=f"db:wc2026_group:{letter}",
            title=f"WC2026 Group {letter}",
            content=text,
        ))
    return docs


def fetch_model_metadata_documents() -> list[RawDocument]:
    """Index ML model metadata (names, purpose — never weights or credentials)."""
    models = [
        ("CatBoost", "Gradient boosted decision trees trained on Elo, FIFA rankings, player aggregates. Primary model."),
        ("LightGBM", "Fast gradient boosting; used in ensemble alongside CatBoost."),
        ("XGBoost", "Extreme gradient boosting; ensemble member."),
        ("Random Forest", "Bagged decision trees; stable baseline in ensemble."),
        ("Logistic Regression", "Linear baseline for win/draw/loss probability calibration."),
    ]
    docs: list[RawDocument] = []
    for name, description in models:
        text = (
            f"ML Model: {name}\n"
            f"Purpose: Match outcome prediction (Win/Draw/Loss probability)\n"
            f"Description: {description}\n"
            f"Input features: Team Elo ratings, FIFA rankings, player quality scores, "
            f"coach impact, home advantage, form\n"
            f"Output: Win probability, Draw probability, Loss probability\n"
            f"Note: All probabilities are statistical estimates for educational purposes only."
        )
        docs.append(RawDocument(
            doc_type="model",
            source_ref=f"ml:model:{name.lower().replace(' ', '_')}",
            title=f"ML Model — {name}",
            content=text,
        ))

    ensemble_text = (
        "Ensemble Prediction System\n"
        "The WCIP uses a weighted ensemble of 5 ML models (CatBoost, LightGBM, XGBoost, "
        "Random Forest, Logistic Regression) combined with:\n"
        "- Elo rating differential\n"
        "- FIFA ranking differential\n"
        "- Player quality aggregate scores\n"
        "- Coach impact multipliers\n"
        "- Poisson scoreline simulation\n"
        "- Monte Carlo tournament simulation (10,000+ runs)\n"
        "Win/Draw/Loss probabilities are calibrated and combined for final predictions.\n"
        "RAG explanations are generated from retrieved facts, not from model weights."
    )
    docs.append(RawDocument(
        doc_type="model",
        source_ref="ml:ensemble",
        title="Prediction System Overview",
        content=ensemble_text,
    ))
    return docs


def fetch_all_documents(db: Session) -> list[RawDocument]:
    """Fetch all indexable documents from all safe sources."""
    all_docs: list[RawDocument] = []
    all_docs.extend(fetch_team_documents(db))
    all_docs.extend(fetch_player_documents(db))
    all_docs.extend(fetch_coach_documents(db))
    all_docs.extend(fetch_wc2026_group_documents(db))
    all_docs.extend(fetch_model_metadata_documents())
    logger.info("RAG sources: fetched %d documents", len(all_docs))
    return all_docs
