"""Fixed-window rate-limiting middleware.

Keyed by client IP + path bucket. Uses the shared cache backend (Redis when
available, in-memory otherwise). Intentionally simple and dependency-free.
"""
from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.cache import cache
from app.core.config import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limit_per_minute: int | None = None):
        super().__init__(app)
        self.limit = limit_per_minute or settings.RATE_LIMIT_PER_MINUTE

    async def dispatch(self, request: Request, call_next):
        # Don't throttle docs / health.
        if request.url.path in ("/health", "/docs", "/openapi.json", "/redoc"):
            return await call_next(request)

        client = request.client.host if request.client else "anon"
        window = int(time.time() // 60)
        key = f"rl:{client}:{window}"
        try:
            current = cache.get_json(key) or 0
            if current >= self.limit:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded. Try again shortly."},
                    headers={"Retry-After": "60"},
                )
            cache.set_json(key, current + 1, ttl=60)
        except Exception:  # noqa: BLE001 — never let the limiter break requests
            pass
        return await call_next(request)
