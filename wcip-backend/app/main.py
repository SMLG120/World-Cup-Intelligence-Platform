"""FastAPI application entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
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
    logger.info("Startup complete (cache backend: %s)", cache.kind)
    yield
    logger.info("Shutdown")


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


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "environment": settings.ENVIRONMENT,
            "cache": cache.kind}


app.include_router(api_router, prefix=settings.API_V1_PREFIX)
