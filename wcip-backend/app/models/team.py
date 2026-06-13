"""Team and Elo-history models."""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    code: Mapped[str] = mapped_column(String(3), index=True)
    confederation: Mapped[str] = mapped_column(String(20))
    elo: Mapped[float] = mapped_column(Float, default=1500.0)
    fifa_rank: Mapped[int] = mapped_column(Integer, default=0)
    # Feature multipliers (1.0 = neutral) fed into the scoreline model.
    attack: Mapped[float] = mapped_column(Float, default=1.0)
    defence: Mapped[float] = mapped_column(Float, default=1.0)
    chemistry: Mapped[float] = mapped_column(Float, default=1.0)
    coach_quality: Mapped[float] = mapped_column(Float, default=1.0)

    elo_history: Mapped[list["EloHistory"]] = relationship(
        back_populates="team", cascade="all, delete-orphan")


class EloHistory(Base):
    __tablename__ = "elo_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    rating: Mapped[float] = mapped_column(Float, nullable=False)
    opponent: Mapped[str | None] = mapped_column(String(120))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                  default=_utcnow)

    team: Mapped[Team] = relationship(back_populates="elo_history")


Index("ix_elo_history_team_time", EloHistory.team_id, EloHistory.recorded_at)


class EloRatingSnapshot(Base):
    """One immutable World Football Elo ingestion snapshot."""

    __tablename__ = "elo_rating_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    rating_date: Mapped[date] = mapped_column(Date, index=True)
    source_url: Mapped[str] = mapped_column(String(500))
    source_hash: Mapped[str] = mapped_column(String(64))
    team_count: Mapped[int] = mapped_column(Integer, default=0)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    data_version: Mapped[str] = mapped_column(String(100), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    ratings: Mapped[list["TeamEloRating"]] = relationship(
        back_populates="snapshot", cascade="all, delete-orphan"
    )


class TeamEloRating(Base):
    """Team Elo value inside one immutable snapshot."""

    __tablename__ = "team_elo_ratings"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "team_name", name="uq_team_elo_snapshot_team"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("elo_rating_snapshots.id"), index=True)
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), index=True)
    team_name: Mapped[str] = mapped_column(String(120), index=True)
    team_code: Mapped[str | None] = mapped_column(String(3), index=True)
    rank: Mapped[int | None] = mapped_column(Integer, index=True)
    rating: Mapped[float] = mapped_column(Float, nullable=False)
    rating_date: Mapped[date] = mapped_column(Date, index=True)
    source_url: Mapped[str] = mapped_column(String(500))
    data_version: Mapped[str] = mapped_column(String(100), index=True)
    raw_payload: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    snapshot: Mapped[EloRatingSnapshot] = relationship(back_populates="ratings")
    team: Mapped[Team | None] = relationship()


class EloSourceLog(Base):
    """Fetch/load audit trail for Elo ingestion."""

    __tablename__ = "elo_source_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_name: Mapped[str] = mapped_column(String(80), default="WorldFootballElo")
    source_url: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(30), index=True)
    snapshot_id: Mapped[str | None] = mapped_column(String(100), index=True)
    data_version: Mapped[str | None] = mapped_column(String(100), index=True)
    source_hash: Mapped[str | None] = mapped_column(String(64))
    http_status: Mapped[int | None] = mapped_column(Integer)
    rows_fetched: Mapped[int | None] = mapped_column(Integer)
    rows_loaded: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


Index("ix_team_elo_ratings_team_date", TeamEloRating.team_name, TeamEloRating.rating_date)
Index("ix_elo_rating_snapshots_current_date", EloRatingSnapshot.is_current, EloRatingSnapshot.rating_date)
