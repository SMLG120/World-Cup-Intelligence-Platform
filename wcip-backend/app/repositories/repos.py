"""Repositories — encapsulate all DB access behind a typed interface."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Generic, Optional, Sequence, Type, TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.simulation import SavedScenario, Simulation, SimStatus
from app.models.team import EloHistory, Team
from app.models.user import User

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    model: Type[ModelT]

    def __init__(self, db: Session):
        self.db = db

    def get(self, id_: int) -> Optional[ModelT]:
        return self.db.get(self.model, id_)

    def add(self, obj: ModelT) -> ModelT:
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def delete(self, obj: ModelT) -> None:
        self.db.delete(obj)
        self.db.commit()


class UserRepository(BaseRepository[User]):
    model = User

    def get_by_email(self, email: str) -> Optional[User]:
        return self.db.scalar(select(User).where(User.email == email))


class TeamRepository(BaseRepository[Team]):
    model = Team

    def get_by_name(self, name: str) -> Optional[Team]:
        return self.db.scalar(select(Team).where(Team.name == name))

    def list_all(self, confederation: Optional[str] = None) -> Sequence[Team]:
        stmt = select(Team).order_by(Team.elo.desc())
        if confederation:
            stmt = stmt.where(Team.confederation == confederation)
        return self.db.scalars(stmt).all()

    def elo_history(self, team_id: int) -> Sequence[EloHistory]:
        return self.db.scalars(
            select(EloHistory)
            .where(EloHistory.team_id == team_id)
            .order_by(EloHistory.recorded_at)
        ).all()


class SimulationRepository(BaseRepository[Simulation]):
    model = Simulation

    def get_by_token(self, token: str) -> Optional[Simulation]:
        return self.db.scalar(
            select(Simulation).where(Simulation.public_token == token))

    def list_for_user(self, user_id: int, page: int, page_size: int
                      ) -> tuple[Sequence[Simulation], int]:
        base = select(Simulation).where(Simulation.owner_id == user_id)
        total = self.db.scalar(
            select(func.count()).select_from(base.subquery())) or 0
        items = self.db.scalars(
            base.order_by(Simulation.created_at.desc())
            .offset((page - 1) * page_size).limit(page_size)
        ).all()
        return items, total

    def mark_completed(self, sim: Simulation, result: dict) -> Simulation:
        sim.status = SimStatus.completed
        sim.result = result
        sim.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(sim)
        return sim

    def mark_failed(self, sim: Simulation, error: str) -> Simulation:
        sim.status = SimStatus.failed
        sim.error = error[:2000]
        self.db.commit()
        self.db.refresh(sim)
        return sim


class ScenarioRepository(BaseRepository[SavedScenario]):
    model = SavedScenario

    def list_for_user(self, user_id: int) -> Sequence[SavedScenario]:
        return self.db.scalars(
            select(SavedScenario).where(SavedScenario.owner_id == user_id)
            .order_by(SavedScenario.created_at.desc())
        ).all()
