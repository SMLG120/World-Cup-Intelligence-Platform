"""Database setup: engine, session factory, declarative base."""
from __future__ import annotations

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

# SQLite needs check_same_thread=False for the FastAPI threadpool.
if settings.is_sqlite:
    connect_args: dict = {"check_same_thread": False}
    pool_kwargs: dict = {}
else:
    # Fail fast instead of hanging a request when the database is unreachable,
    # and recycle connections before Supabase's pooler drops idle ones.
    connect_args = {"connect_timeout": 10}
    pool_kwargs = {
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        "pool_recycle": 300,
        "pool_timeout": 15,
    }

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    connect_args=connect_args,
    future=True,
    **pool_kwargs,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False,
                            expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def get_db() -> Generator:
    """FastAPI dependency that yields a scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
