"""Team and Elo-history models."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String
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
