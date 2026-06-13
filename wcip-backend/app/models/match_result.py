"""Historical match results and feature store."""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MatchResult(Base):
    """Historical international match results used for ML training."""
    __tablename__ = "match_results"
    __table_args__ = (UniqueConstraint("home_team", "away_team", "match_date", name="uq_match"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    match_date: Mapped[date] = mapped_column(Date, index=True)
    home_team: Mapped[str] = mapped_column(String(120), index=True)
    away_team: Mapped[str] = mapped_column(String(120), index=True)
    home_goals: Mapped[int] = mapped_column(Integer)
    away_goals: Mapped[int] = mapped_column(Integer)
    tournament: Mapped[str | None] = mapped_column(String(120))
    city: Mapped[str | None] = mapped_column(String(120))
    country: Mapped[str | None] = mapped_column(String(120))
    neutral: Mapped[bool] = mapped_column(Boolean, default=True)

    # Outcome label (0=away win, 1=draw, 2=home win) — computed on load
    outcome: Mapped[int | None] = mapped_column(Integer)

    data_source: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class MatchFeatures(Base):
    """Engineered feature vector for a specific match (pre-computed)."""
    __tablename__ = "match_features"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_result_id: Mapped[int | None] = mapped_column(Integer, index=True)  # nullable for future matches
    home_team: Mapped[str] = mapped_column(String(120), index=True)
    away_team: Mapped[str] = mapped_column(String(120), index=True)
    match_date: Mapped[date] = mapped_column(Date, index=True)

    # Core features
    elo_diff: Mapped[float] = mapped_column(Float, default=0.0)
    fifa_rank_diff: Mapped[float] = mapped_column(Float, default=0.0)
    xg_diff: Mapped[float] = mapped_column(Float, default=0.0)
    xga_diff: Mapped[float] = mapped_column(Float, default=0.0)
    goals_scored_diff: Mapped[float] = mapped_column(Float, default=0.0)
    goals_conceded_diff: Mapped[float] = mapped_column(Float, default=0.0)
    form_diff: Mapped[float] = mapped_column(Float, default=0.0)          # last-5 points diff
    avg_age_diff: Mapped[float] = mapped_column(Float, default=0.0)
    market_value_diff: Mapped[float] = mapped_column(Float, default=0.0)  # log-scaled
    injury_burden_diff: Mapped[float] = mapped_column(Float, default=0.0)
    coach_impact_diff: Mapped[float] = mapped_column(Float, default=0.0)
    squad_chemistry_diff: Mapped[float] = mapped_column(Float, default=0.0)
    travel_distance_km: Mapped[float] = mapped_column(Float, default=0.0)
    rest_days: Mapped[float] = mapped_column(Float, default=7.0)
    tournament_exp_diff: Mapped[float] = mapped_column(Float, default=0.0)
    starting_xi_strength_diff: Mapped[float] = mapped_column(Float, default=0.0)
    bench_strength_diff: Mapped[float] = mapped_column(Float, default=0.0)
    average_starting_xi_rating_diff: Mapped[float] = mapped_column(Float, default=0.0)
    average_squad_rating_diff: Mapped[float] = mapped_column(Float, default=0.0)
    top_5_player_rating_avg_diff: Mapped[float] = mapped_column(Float, default=0.0)
    goalkeeper_rating_diff: Mapped[float] = mapped_column(Float, default=0.0)
    defensive_unit_rating_diff: Mapped[float] = mapped_column(Float, default=0.0)
    midfield_unit_rating_diff: Mapped[float] = mapped_column(Float, default=0.0)
    attacking_unit_rating_diff: Mapped[float] = mapped_column(Float, default=0.0)
    squad_depth_score_diff: Mapped[float] = mapped_column(Float, default=0.0)
    star_player_score_diff: Mapped[float] = mapped_column(Float, default=0.0)
    injury_burden_score_diff: Mapped[float] = mapped_column(Float, default=0.0)
    player_form_score_diff: Mapped[float] = mapped_column(Float, default=0.0)
    player_availability_score_diff: Mapped[float] = mapped_column(Float, default=0.0)
    international_experience_score_diff: Mapped[float] = mapped_column(Float, default=0.0)
    average_caps_diff: Mapped[float] = mapped_column(Float, default=0.0)
    total_international_goals_diff: Mapped[float] = mapped_column(Float, default=0.0)
    weighted_player_strength_diff: Mapped[float] = mapped_column(Float, default=0.0)

    # Feature version for reproducibility
    feature_version: Mapped[str] = mapped_column(String(20), default="v2")
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class MLModelRecord(Base):
    """Registry of trained ML models with evaluation metrics."""
    __tablename__ = "ml_models"

    id: Mapped[int] = mapped_column(primary_key=True)
    model_name: Mapped[str] = mapped_column(String(80), index=True)  # logistic, random_forest, etc.
    version: Mapped[str] = mapped_column(String(40))
    file_path: Mapped[str] = mapped_column(String(255))

    # Evaluation metrics
    accuracy: Mapped[float | None] = mapped_column(Float)
    f1_score: Mapped[float | None] = mapped_column(Float)
    brier_score: Mapped[float | None] = mapped_column(Float)
    log_loss: Mapped[float | None] = mapped_column(Float)
    calibration_score: Mapped[float | None] = mapped_column(Float)

    # Ensemble weight (auto-calibrated from validation performance)
    ensemble_weight: Mapped[float] = mapped_column(Float, default=1.0)

    feature_version: Mapped[str] = mapped_column(String(20), default="v1")
    data_snapshot_version: Mapped[str | None] = mapped_column(String(120))
    calibration_status: Mapped[str] = mapped_column(String(40), default="unknown")
    requires_recalibration: Mapped[bool] = mapped_column(Boolean, default=False)
    training_samples: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    notes: Mapped[str | None] = mapped_column(Text)


class QualifiedTeam(Base):
    """WC 2026 qualification tracker — updated as teams qualify."""
    __tablename__ = "qualified_teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    team_name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    team_code: Mapped[str] = mapped_column(String(3))
    confederation: Mapped[str] = mapped_column(String(20))
    tournament_year: Mapped[int] = mapped_column(Integer, default=2026)
    group_label: Mapped[str | None] = mapped_column(String(5))        # A..L once drawn
    pot: Mapped[int | None] = mapped_column(Integer)                  # seeding pot
    qualified_date: Mapped[date | None] = mapped_column(Date)
    qualification_path: Mapped[str | None] = mapped_column(String(120))  # e.g. "UEFA Play-Off"
    host_nation: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
