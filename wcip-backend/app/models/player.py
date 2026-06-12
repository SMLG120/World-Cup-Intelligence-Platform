"""Player and coach intelligence models."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
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
    player_rating: Mapped[float | None] = mapped_column(Float)
    ea_fc_rating: Mapped[float | None] = mapped_column(Float)
    player_rating_source: Mapped[str | None] = mapped_column(String(120))
    player_rating_version: Mapped[str | None] = mapped_column(String(80))
    player_rating_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Computed scores (populated by feature pipeline)
    recent_form_score: Mapped[float] = mapped_column(Float, default=0.5)
    fitness_score: Mapped[float] = mapped_column(Float, default=1.0)   # 0..1

    # Source tracking
    data_source: Mapped[str | None] = mapped_column(String(80))
    external_id: Mapped[str | None] = mapped_column(String(80), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class PlayerRatingImport(Base):
    """One legal player-rating import batch."""

    __tablename__ = "player_rating_imports"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_name: Mapped[str] = mapped_column(String(120), index=True)
    source_url: Mapped[str | None] = mapped_column(String(500))
    source_file: Mapped[str | None] = mapped_column(String(500))
    source_version: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(30), default="success", index=True)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, default=0)
    skipped_rows: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class PlayerRatingRecord(Base):
    """Historical player rating value from an import batch."""

    __tablename__ = "player_rating_records"
    __table_args__ = (
        UniqueConstraint(
            "import_id",
            "team_name",
            "player_name",
            name="uq_player_rating_import_team_player",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    import_id: Mapped[int] = mapped_column(ForeignKey("player_rating_imports.id"), index=True)
    player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"), index=True)
    player_name: Mapped[str] = mapped_column(String(150), index=True)
    team_name: Mapped[str] = mapped_column(String(120), index=True)
    position: Mapped[str | None] = mapped_column(String(30))
    club: Mapped[str | None] = mapped_column(String(120))
    rating: Mapped[float | None] = mapped_column(Float)
    ea_fc_rating: Mapped[float | None] = mapped_column(Float)
    recent_form_score: Mapped[float | None] = mapped_column(Float)
    source_row_hash: Mapped[str] = mapped_column(String(64), index=True)
    raw_payload: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


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
