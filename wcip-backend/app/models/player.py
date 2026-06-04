"""Player and coach intelligence models."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), index=True)
    team_name: Mapped[str] = mapped_column(String(120), index=True)
    position: Mapped[str] = mapped_column(String(30))          # GK, DEF, MID, FWD
    club: Mapped[str | None] = mapped_column(String(120))
    age: Mapped[int | None] = mapped_column(Integer)
    nationality: Mapped[str | None] = mapped_column(String(120))

    # Playing time
    minutes_played: Mapped[float] = mapped_column(Float, default=0.0)

    # Attacking
    goals: Mapped[float] = mapped_column(Float, default=0.0)
    assists: Mapped[float] = mapped_column(Float, default=0.0)
    xg: Mapped[float] = mapped_column(Float, default=0.0)      # expected goals
    xag: Mapped[float] = mapped_column(Float, default=0.0)     # expected assists
    key_passes: Mapped[float] = mapped_column(Float, default=0.0)
    shots_on_target: Mapped[float] = mapped_column(Float, default=0.0)

    # Progression
    progressive_passes: Mapped[float] = mapped_column(Float, default=0.0)
    progressive_carries: Mapped[float] = mapped_column(Float, default=0.0)

    # Defensive
    tackles: Mapped[float] = mapped_column(Float, default=0.0)
    interceptions: Mapped[float] = mapped_column(Float, default=0.0)
    clearances: Mapped[float] = mapped_column(Float, default=0.0)

    # Discipline
    yellow_cards: Mapped[int] = mapped_column(Integer, default=0)
    red_cards: Mapped[int] = mapped_column(Integer, default=0)

    # Status
    injured: Mapped[bool] = mapped_column(Boolean, default=False)
    suspended: Mapped[bool] = mapped_column(Boolean, default=False)
    injury_notes: Mapped[str | None] = mapped_column(Text)

    # Market / International
    market_value_eur: Mapped[float | None] = mapped_column(Float)
    international_caps: Mapped[int] = mapped_column(Integer, default=0)
    international_goals: Mapped[int] = mapped_column(Integer, default=0)

    # Computed scores (populated by feature pipeline)
    recent_form_score: Mapped[float] = mapped_column(Float, default=0.5)
    fitness_score: Mapped[float] = mapped_column(Float, default=1.0)   # 0..1

    # Source tracking
    data_source: Mapped[str | None] = mapped_column(String(80))
    external_id: Mapped[str | None] = mapped_column(String(80), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class Coach(Base):
    __tablename__ = "coaches"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), index=True)
    team_name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    nationality: Mapped[str | None] = mapped_column(String(120))
    preferred_formation: Mapped[str | None] = mapped_column(String(20))  # e.g. "4-3-3"

    # Historical record
    win_pct: Mapped[float] = mapped_column(Float, default=0.5)          # 0..1
    draw_pct: Mapped[float] = mapped_column(Float, default=0.2)
    loss_pct: Mapped[float] = mapped_column(Float, default=0.3)
    matches_managed: Mapped[int] = mapped_column(Integer, default=0)

    # Tournament metrics
    tournament_experience: Mapped[int] = mapped_column(Integer, default=0)  # WC tournaments managed
    knockout_record: Mapped[float] = mapped_column(Float, default=0.5)       # win% in KO stages
    tactical_flexibility: Mapped[float] = mapped_column(Float, default=0.5)  # 0..1 (formations used)
    recent_form_score: Mapped[float] = mapped_column(Float, default=0.5)     # last 10 matches

    # Computed impact score (populated by feature pipeline)
    impact_score: Mapped[float] = mapped_column(Float, default=1.0)  # multiplicative

    data_source: Mapped[str | None] = mapped_column(String(80))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
