"""Caching layer.

Thin wrapper over Redis with a graceful in-process fallback so the app and
tests run without a Redis server. JSON-serialises values; namespaced keys.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class _MemoryCache:
    """Tiny TTL cache used when Redis is unreachable."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[float, str]] = {}

    def get(self, key: str) -> Optional[str]:
        item = self._store.get(key)
        if not item:
            return None
        expires_at, value = item
        if expires_at < time.time():
            self._store.pop(key, None)
            return None
        return value

    def setex(self, key: str, ttl: int, value: str) -> None:
        self._store[key] = (time.time() + ttl, value)

    def delete(self, *keys: str) -> None:
        for k in keys:
            self._store.pop(k, None)


class Cache:
    def __init__(self) -> None:
        self._backend: Any
        try:
            import redis  # local import so tests don't require a server

            client = redis.Redis.from_url(settings.REDIS_URL,
                                          socket_connect_timeout=0.25,
                                          decode_responses=True)
            client.ping()
            self._backend = client
            self.kind = "redis"
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis unavailable (%s); using in-memory cache", exc)
            self._backend = _MemoryCache()
            self.kind = "memory"

    def get_json(self, key: str) -> Optional[Any]:
        raw = self._backend.get(key)
        return json.loads(raw) if raw is not None else None

    def set_json(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        self._backend.setex(key, ttl or settings.CACHE_TTL_SECONDS,
                            json.dumps(value, default=str))

    def invalidate(self, *keys: str) -> None:
        self._backend.delete(*keys)

    def invalidate_prefix(self, *prefixes: str) -> int:
        """Best-effort prefix invalidation for prediction/data refreshes."""
        deleted = 0
        if not prefixes:
            return deleted
        if isinstance(self._backend, _MemoryCache):
            keys = [
                key for key in list(self._backend._store)
                if any(key.startswith(prefix) for prefix in prefixes)
            ]
            self._backend.delete(*keys)
            return len(keys)
        try:
            keys: list[str] = []
            for prefix in prefixes:
                keys.extend(list(self._backend.scan_iter(match=f"{prefix}*")))
            if keys:
                self._backend.delete(*keys)
                deleted = len(keys)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Cache prefix invalidation failed: %s", exc)
        return deleted


cache = Cache()
