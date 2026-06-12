"""Application configuration.

Loaded from environment variables (or a local .env). Sensible defaults let the
app and test-suite run with zero config (SQLite + in-memory cache); production
overrides via real env vars / secrets.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- general ---
    PROJECT_NAME: str = "World Cup Intelligence Platform"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "development"  # development | staging | production
    DEBUG: bool = True

    # --- security ---
    # MUST be overridden in production via env / secret manager.
    SECRET_KEY: str = "dev-insecure-change-me-in-production-0123456789abcdef"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    # --- database ---
    # Default to SQLite so local dev / CI runs with no Postgres.
    DATABASE_URL: str = "sqlite:///./wcip.db"

    # --- redis / celery ---
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL_SECONDS: int = 300
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    # When true, Celery tasks run synchronously in-process (tests / no broker).
    CELERY_TASK_ALWAYS_EAGER: bool = False

    # --- CORS ---
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # --- rate limiting ---
    RATE_LIMIT_PER_MINUTE: int = 120

    # --- OAuth (NextAuth-compatible; optional) ---
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""

    # --- simulation guardrails ---
    MAX_MONTE_CARLO_RUNS: int = 50_000
    SYNC_SIM_RUN_THRESHOLD: int = 2_000  # above this -> dispatch to Celery

    # --- data sources ---
    FOOTBALL_DATA_API_KEY: str = ""       # football-data.org free tier key

    # --- ML ---
    ML_MODELS_DIR: str = "models"
    ML_MIN_TRAINING_SAMPLES: int = 200
    ML_FEATURE_VERSION: str = "v2"
    ETL_AUTO_RUN_ON_STARTUP: bool = False  # set True to auto-run ETL on deploy

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
