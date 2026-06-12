"""Versioned FIFA ranking snapshots."""
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


class FifaRankingSnapshot(Base):
    """One immutable FIFA ranking publication."""

    __tablename__ = "fifa_ranking_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    ranking_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    gender: Mapped[str] = mapped_column(String(20), default="men")
    sport_type: Mapped[str] = mapped_column(String(30), default="football")
    ranking_date: Mapped[date] = mapped_column(Date, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_update_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_url: Mapped[str] = mapped_column(String(500))
    source_hash: Mapped[str] = mapped_column(String(64))
    team_count: Mapped[int] = mapped_column(Integer, default=0)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    entries: Mapped[list["FifaRankingEntry"]] = relationship(
        back_populates="snapshot", cascade="all, delete-orphan"
    )


class FifaRankingEntry(Base):
    """Team rank inside one FIFA ranking snapshot."""

    __tablename__ = "fifa_ranking_entries"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "team_name", name="uq_fifa_ranking_entry_team"),
        UniqueConstraint("snapshot_id", "team_code", name="uq_fifa_ranking_entry_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("fifa_ranking_snapshots.id"), index=True)
    team_name: Mapped[str] = mapped_column(String(120), index=True)
    team_code: Mapped[str | None] = mapped_column(String(3), index=True)
    confederation: Mapped[str | None] = mapped_column(String(40))
    rank: Mapped[int] = mapped_column(Integer, index=True)
    previous_rank: Mapped[int | None] = mapped_column(Integer)
    rank_change: Mapped[int | None] = mapped_column(Integer)
    points: Mapped[float | None] = mapped_column(Float)
    previous_points: Mapped[float | None] = mapped_column(Float)
    points_change: Mapped[float | None] = mapped_column(Float)
    raw_team_name: Mapped[str | None] = mapped_column(String(160))
    raw_payload: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    snapshot: Mapped[FifaRankingSnapshot] = relationship(back_populates="entries")


class TeamRanking(Base):
    """Compatibility table for point-in-time team rankings.

    `fifa_ranking_entries` remains the canonical per-snapshot table. This table
    gives downstream code and analysts a stable, provider-agnostic name for
    ranking records while preserving the same snapshot boundary.
    """

    __tablename__ = "team_rankings"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "team_name", name="uq_team_ranking_snapshot_team"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("fifa_ranking_snapshots.id"), index=True)
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), index=True)
    team_name: Mapped[str] = mapped_column(String(120), index=True)
    team_code: Mapped[str | None] = mapped_column(String(3), index=True)
    confederation: Mapped[str | None] = mapped_column(String(40))
    ranking_provider: Mapped[str] = mapped_column(String(40), default="FIFA")
    rank: Mapped[int] = mapped_column(Integer, index=True)
    points: Mapped[float | None] = mapped_column(Float)
    ranking_date: Mapped[date] = mapped_column(Date, index=True)
    source_url: Mapped[str] = mapped_column(String(500))
    data_version: Mapped[str] = mapped_column(String(80), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class RankingSourceLog(Base):
    """Fetch/load audit trail for ranking ingestion."""

    __tablename__ = "ranking_source_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_name: Mapped[str] = mapped_column(String(80), default="FIFA")
    source_url: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(30), index=True)  # started|success|failed
    ranking_id: Mapped[str | None] = mapped_column(String(80), index=True)
    data_version: Mapped[str | None] = mapped_column(String(80), index=True)
    source_hash: Mapped[str | None] = mapped_column(String(64))
    http_status: Mapped[int | None] = mapped_column(Integer)
    rows_fetched: Mapped[int | None] = mapped_column(Integer)
    rows_loaded: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


Index(
    "ix_fifa_ranking_entries_team_snapshot",
    FifaRankingEntry.team_name,
    FifaRankingEntry.snapshot_id,
)
Index(
    "ix_fifa_ranking_snapshots_current_date",
    FifaRankingSnapshot.is_current,
    FifaRankingSnapshot.ranking_date,
)
Index("ix_team_rankings_team_date", TeamRanking.team_name, TeamRanking.ranking_date)
