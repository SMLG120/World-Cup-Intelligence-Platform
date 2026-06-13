"""FastAPI application entrypoint."""
from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.cache import cache
from app.core.config import settings
from app.core.ratelimit import RateLimitMiddleware

logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("wcip")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables / seed on startup (safe + idempotent for dev & SQLite).
    from app.db.init_db import init_db
    init_db()
    _log_startup_diagnostics()
    logger.info("Startup complete (cache backend: %s)", cache.kind)
    yield
    logger.info("Shutdown")


def _log_startup_diagnostics() -> None:
    """Log local startup state without failing the app if diagnostics fail."""

    try:
        from sqlalchemy import text
        from app.db.base import SessionLocal
        from app.models.match_result import QualifiedTeam
        from app.models.player import Player
        from app.models.team import Team

        db_url = _sanitize_database_url(settings.DATABASE_URL)
        sqlite_path = _sqlite_path(settings.DATABASE_URL)
        db = SessionLocal()
        try:
            migration = db.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar()
            team_count = db.query(Team).count()
            player_count = db.query(Player).count()
            qualified_count = db.query(QualifiedTeam).count()
        finally:
            db.close()

        logger.info(
            "Startup diagnostics database_url=%s sqlite_path=%s alembic_revision=%s "
            "teams=%s players=%s qualified_world_cup_teams=%s",
            db_url,
            sqlite_path or "n/a",
            migration or "not_recorded",
            team_count,
            player_count,
            qualified_count,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Startup diagnostics unavailable: %s", exc)


def _sanitize_database_url(url: str) -> str:
    if "@" not in url:
        return url
    parts = urlsplit(url)
    host = parts.netloc.rsplit("@", 1)[-1]
    return f"{parts.scheme}://***@{host}{parts.path}"


def _sqlite_path(url: str) -> str | None:
    if not url.startswith("sqlite:///"):
        return None
    raw_path = url.replace("sqlite:///", "", 1)
    path = Path(raw_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    return str(path.resolve())


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description=(
        "Statistical simulation API for World Cup match & tournament "
        "prediction. All output is educational analysis, not betting advice."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    return response


def _error_payload(
    request: Request,
    *,
    status_code: int,
    error_code: str,
    message: str,
    detail=None,
) -> dict:
    return {
        "status_code": status_code,
        "error_code": error_code,
        "message": message,
        "detail": detail,
        "request_id": getattr(request.state, "request_id", None),
    }


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict):
        error_code = str(detail.get("error_code") or "http_error")
        message = str(detail.get("message") or "Request failed")
        extra = detail.get("detail")
    else:
        error_code = "http_error"
        message = str(detail)
        extra = detail
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(
            request,
            status_code=exc.status_code,
            error_code=error_code,
            message=message,
            detail=extra,
        ),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=_error_payload(
            request,
            status_code=422,
            error_code="validation_error",
            message="Request validation failed",
            detail=exc.errors(),
        ),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None)
    logger.exception("Unhandled error on %s request_id=%s", request.url.path, request_id)
    return JSONResponse(
        status_code=500,
        content=_error_payload(
            request,
            status_code=500,
            error_code="internal_server_error",
            message="Internal server error",
            detail=None,
        ),
    )


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "environment": settings.ENVIRONMENT,
            "cache": cache.kind}


app.include_router(api_router, prefix=settings.API_V1_PREFIX)
