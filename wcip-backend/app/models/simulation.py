"""Simulation, run, and saved-scenario models."""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (JSON, DateTime, Enum, ForeignKey, Integer, String, Text,
                        Boolean)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _token() -> str:
    return uuid.uuid4().hex


class SimStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class SimKind(str, enum.Enum):
    match = "match"
    tournament = "tournament"
    monte_carlo = "monte_carlo"
    wc2026 = "wc2026"
    prediction = "prediction"
    scenario = "scenario"


class Simulation(Base):
    __tablename__ = "simulations"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_token: Mapped[str] = mapped_column(String(32), unique=True,
                                              index=True, default=_token)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(200), default="Untitled simulation")
    kind: Mapped[SimKind] = mapped_column(Enum(SimKind), default=SimKind.monte_carlo)
    status: Mapped[SimStatus] = mapped_column(Enum(SimStatus),
                                             default=SimStatus.pending, index=True)
    # Input parameters (runs, scenario overrides, edition...) and outputs.
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict | None] = mapped_column(JSON)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    task_id: Mapped[str | None] = mapped_column(String(64))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=_utcnow, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    owner: Mapped["User"] = relationship(back_populates="simulations")  # noqa: F821
    runs: Mapped[list["SimulationRun"]] = relationship(
        back_populates="simulation", cascade="all, delete-orphan")


class SimulationRun(Base):
    """A single execution attempt (supports replays / progress tracking)."""

    __tablename__ = "simulation_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    simulation_id: Mapped[int] = mapped_column(ForeignKey("simulations.id"),
                                              index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)  # 0..100
    runs_completed: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=_utcnow)

    simulation: Mapped[Simulation] = relationship(back_populates="runs")


class SavedScenario(Base):
    __tablename__ = "saved_scenarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    # Per-team overrides: {"Argentina": {"injury": 0.8, "morale": 0.95}, ...}
    overrides: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=_utcnow)
