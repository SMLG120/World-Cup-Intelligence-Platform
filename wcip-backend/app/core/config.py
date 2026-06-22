"""Application configuration.

Loaded from environment variables (or a local .env). Sensible defaults let the
app and test-suite run with zero config (SQLite + in-memory cache); production
overrides via real env vars / secrets.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Annotated, List

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # --- general ---
    PROJECT_NAME: str = Field(
        default="World Cup Intelligence Platform",
        validation_alias=AliasChoices("APP_NAME", "PROJECT_NAME"),
    )
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = Field(
        default="development",
        validation_alias=AliasChoices("APP_ENV", "ENVIRONMENT"),
    )  # development | staging | production
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # --- security ---
    # MUST be overridden in production via env / secret manager.
    SECRET_KEY: str = Field(
        default="dev-insecure-change-me-in-production-0123456789abcdef",
        validation_alias=AliasChoices("JWT_SECRET_KEY", "SECRET_KEY"),
    )
    REFRESH_SECRET_KEY: str = Field(
        default="",
        validation_alias=AliasChoices("JWT_REFRESH_SECRET_KEY", "REFRESH_SECRET_KEY"),
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = Field(
        default="HS256",
        validation_alias=AliasChoices("JWT_ALGORITHM", "ALGORITHM"),
    )

    # --- database ---
    # Default to SQLite so local dev / CI runs with no Postgres.
    DATABASE_URL: str = "sqlite:///./wcip.db"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _normalize_database_url(cls, v):
        # Some Postgres providers (Render included) hand out `postgres://`
        # connection strings; SQLAlchemy 1.4+ only recognizes `postgresql://`.
        if isinstance(v, str) and v.startswith("postgres://"):
            return "postgresql://" + v[len("postgres://"):]
        return v

    # --- redis / celery ---
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL_SECONDS: int = 300
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    # When true, Celery tasks run synchronously in-process (tests / no broker).
    CELERY_TASK_ALWAYS_EAGER: bool = False

    # --- CORS ---
    BACKEND_CORS_ORIGINS: Annotated[List[str], NoDecode] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "https://world-cup-intelligence-platform.vercel.app",
        ],
        validation_alias=AliasChoices("ALLOWED_ORIGINS", "CORS_ORIGINS", "BACKEND_CORS_ORIGINS"),
    )
    BACKEND_CORS_ORIGIN_REGEX: str = Field(
        default=r"https://world-cup-intelligence-platform(?:-[a-z0-9-]+)?\.vercel\.app",
        validation_alias=AliasChoices("CORS_ORIGIN_REGEX", "BACKEND_CORS_ORIGIN_REGEX"),
    )

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
    API_FOOTBALL_KEY: str = ""
    FIFA_RANKING_SOURCE_URL: str = "https://inside.fifa.com/fifa-world-ranking/men"
    ELO_RATING_SOURCE_URL: str = "https://www.eloratings.net/2026_World_Cup"
    ELO_RATING_TSV_URL: str = "https://www.eloratings.net/World.tsv"

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

    @field_validator("DEBUG", mode="before")
    @classmethod
    def _parse_debug(cls, v):
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            normalized = v.strip().lower()
            if normalized in {"1", "true", "yes", "y", "on", "debug", "dev", "development"}:
                return True
            if normalized in {"0", "false", "no", "n", "off", "release", "prod", "production"}:
                return False
        return v

    @model_validator(mode="after")
    def _validate_production_secrets(self):
        env = self.ENVIRONMENT.lower()
        unsafe_values = {
            "",
            "change-me",
            "change-me-to-a-long-random-string",
            "dev-insecure-change-me",
            "dev-insecure-change-me-in-production-0123456789abcdef",
            "replace-with-generated-local-secret",
            "replace-with-generated-local-jwt-secret",
            "replace-with-generated-local-refresh-secret",
        }
        if env == "production":
            if self.SECRET_KEY in unsafe_values:
                raise ValueError(
                    "JWT_SECRET_KEY must be set to a strong production secret"
                )
            refresh_secret = self.REFRESH_SECRET_KEY or self.SECRET_KEY
            if refresh_secret in unsafe_values:
                raise ValueError(
                    "JWT_REFRESH_SECRET_KEY must be set to a strong production secret"
                )
        return self

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
