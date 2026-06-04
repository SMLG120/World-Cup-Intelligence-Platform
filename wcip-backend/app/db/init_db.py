"""Create tables and seed reference data (teams + initial Elo snapshot)."""
from __future__ import annotations

import logging

from sqlalchemy import select

from app.db.base import Base, SessionLocal, engine
from app.models import EloHistory, Team
from wcip.data.teams_2022 import build_teams

logger = logging.getLogger(__name__)


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)


def seed_teams() -> int:
    """Idempotently seed national teams. Returns number inserted."""
    db = SessionLocal()
    inserted = 0
    try:
        existing = set(db.scalars(select(Team.name)).all())
        for name, t in build_teams().items():
            if name in existing:
                continue
            team = Team(name=t.name, code=t.code, confederation=t.confederation,
                        elo=t.elo, fifa_rank=t.fifa_rank)
            db.add(team)
            db.flush()
            db.add(EloHistory(team_id=team.id, rating=t.elo, opponent=None))
            inserted += 1
        db.commit()
    finally:
        db.close()
    if inserted:
        logger.info("Seeded %d teams", inserted)
    return inserted


def init_db() -> None:
    create_tables()
    seed_teams()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()
    print("Database initialised and seeded.")
